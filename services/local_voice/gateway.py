"""Private, single-tenant Pipecat WebRTC gateway for Verto's existing voice UI."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

import httpx
from av import AudioResampler
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, SecretStr

from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from loguru import logger

from .audio import SpeechTrack
from .conversation import Conversation
from .speech import Capture, LocalTranscriber


# Pipecat's debug messages can contain application messages. Keep only our
# deliberately content-free service logs; never log SDP, keys or transcripts.
logger.disable("pipecat")
log = logging.getLogger("verto.local_voice")


class Offer(BaseModel):
    sdp: str = Field(min_length=4, max_length=64_000)
    tenant: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=128)
    reasoning_effort: str = Field(default="low", max_length=16)
    instructions: str = Field(max_length=150_000)
    tools: list[dict] = Field(max_length=64)
    openai_api_key: SecretStr
    openai_base_url: str = "https://api.openai.com/v1"
    openai_project: str | None = None
    openai_organization: str | None = None
    ice_servers: list[dict] = Field(default_factory=list, max_length=8)


class Peer:
    def __init__(self, offer, transcriber, tts, service_token, on_closed, *, client_factory=AsyncOpenAI):
        self.reference = "local_" + uuid.uuid4().hex
        self.connection = SmallWebRTCConnection(ice_servers=[IceServer(**value) for value in offer.ice_servers])
        self.track = SpeechTrack()
        self.connection.pc.addTrack(self.track)
        self.transcriber, self.tts, self.service_token = transcriber, tts, service_token
        self.on_closed = on_closed
        self.capture = None
        self.commits = set()
        self.commit_lock = asyncio.Lock()
        self.control_lock = asyncio.Lock()
        self.audio_tasks = set()
        self.closed = False
        self.finishing = False
        self.last_message = asyncio.get_running_loop().time()
        client = client_factory(api_key=offer.openai_api_key.get_secret_value(), base_url=offer.openai_base_url,
                                project=offer.openai_project, organization=offer.openai_organization,
                                max_retries=0, timeout=45)
        self.conversation = Conversation(
            client=client, model=offer.model, effort=offer.reasoning_effort,
            instructions=offer.instructions, tools=offer.tools, send=self.connection.send_app_message,
            speak=self.speak, clear_audio=self.track.clear,
        )

        @self.connection.event_handler("app-message")
        async def message(connection, event):
            try:
                if isinstance(event, dict) and event.get("type") == "conversation.item.create" and (event.get("item") or {}).get("type") == "function_call_output":
                    # A mode switch waits for outstanding tools; their replies
                    # must bypass that wait, otherwise the channel deadlocks.
                    self.conversation.tool_result(event["item"])
                else:
                    async with self.control_lock:
                        await self.message(event)
            except Exception:
                self.emit("error", error={"message": "The local voice session could not process this event."})

        @self.connection.event_handler("track-started")
        async def track_started(connection, track):
            if track.kind == "audio":
                task = asyncio.create_task(self.receive_audio(track))
                self.audio_tasks.add(task)
                task.add_done_callback(self.audio_tasks.discard)

        @self.connection.event_handler("closed")
        async def closed(connection):
            await self.close()

        @self.connection.event_handler("failed")
        async def failed(connection):
            await self.close()

    def emit(self, event_type, **values):
        self.connection.send_app_message({"type": event_type, **values})

    async def speak(self, text, generation):
        response = await self.tts.post("/speech", json={"text": text},
                                       headers={"Authorization": "Bearer " + self.service_token})
        response.raise_for_status()
        if response.headers.get("x-sample-rate") != str(self.track.RATE):
            raise ValueError("Unexpected speech sample rate")
        if generation != self.conversation.generation:
            return
        self.emit("local.status", phase="speaking")
        await self.track.add(response.content, generation)

    async def receive_audio(self, track):
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)
        try:
            while not self.closed:
                frame = await track.recv()
                for converted in resampler.resample(frame):
                    capture = self.capture
                    if capture and capture.active:
                        try:
                            capture.add(converted.to_ndarray().tobytes())
                        except ValueError:
                            self.capture = None
                            await capture.close()
                            self.emit("error", error={"message": "Release the microphone after a maximum of two minutes per turn."})
        except asyncio.CancelledError:
            raise
        except Exception:
            if not self.closed:
                self.emit("error", error={"message": "The microphone audio stream ended."})

    async def commit(self):
        # RTP and the reliable data channel have independent delivery order.
        # Retain a short tail so the final word isn't clipped by an early commit.
        await asyncio.sleep(0.12)
        capture, self.capture = self.capture, None
        if capture is None:
            return

        async def finish_turn():
            async with self.commit_lock:
                try:
                    self.emit("local.status", phase="transcribing")
                    text = await capture.finish()
                    self.emit("conversation.item.input_audio_transcription.completed", transcript=text, generation=capture.generation)
                    if text:
                        self.conversation.submit(text=text, generation=capture.generation)
                    else:
                        self.emit("local.status", phase="idle")
                except Exception:
                    self.emit("error", error={"message": "Could not finalise the transcript. Please repeat that turn."})

        task = asyncio.create_task(finish_turn())
        self.commits.add(task)
        task.add_done_callback(self.commits.discard)

    async def message(self, event):
        if not isinstance(event, dict) or len(json.dumps(event)) > 160_000:
            return
        self.last_message = asyncio.get_running_loop().time()
        event_type = event.get("type")
        if event_type == "conversation.item.create":
            item = event.get("item") or {}
            if item.get("type") == "function_call_output":
                self.conversation.tool_result(item)
            elif not self.finishing and item.get("role") == "user":
                # Active-step changes use the same authenticated frontend tool
                # context as the other engines. Supersede stale spoken replies.
                await self.conversation.interrupt()
                text = " ".join(str(part.get("text") or "") for part in item.get("content", []) if isinstance(part, dict))
                self.conversation.submit(text=text)
        elif event_type == "local.input.start" and not self.finishing:
            if self.capture:
                return
            await self.conversation.interrupt()
            capture = Capture(self.transcriber, lambda text: None, self.conversation.generation)
            capture.partial = lambda text: self.emit("local.transcript.partial", text=text, generation=capture.generation) if self.capture is capture else None
            self.capture = capture
        elif event_type == "local.input.commit":
            await self.commit()
        elif event_type == "response.cancel":
            await self.conversation.interrupt()
        elif event_type == "local.context.update" and not self.finishing:
            await self.conversation.turns.join()
            tools = event.get("tools")
            instructions = event.get("instructions")
            if not isinstance(tools, list) or not isinstance(instructions, str):
                return
            self.conversation.instructions = instructions
            self.conversation.tools = [{**tool, "strict": False} for tool in tools]
        elif event_type == "response.create" and not self.finishing:
            # Tool continuation is automatic here. The existing Realtime UI
            # also emits response.create after a tool; never duplicate a turn.
            if not self.conversation.tool_results:
                extra = str((event.get("response") or {}).get("instructions") or "")
                if extra:
                    self.conversation.submit(instructions=extra)
        elif event_type == "session.close" and not self.finishing:
            self.finishing = True
            await self.commit()
            asyncio.create_task(self.finish())

    async def finish(self):
        try:
            async with asyncio.timeout(12):
                if self.commits:
                    await asyncio.gather(*self.commits)
                await self.conversation.finish()
                await self.track.frames.join()
            self.emit("session.closed")
            await asyncio.sleep(0.1)  # Allow the reliable data channel to flush.
        except TimeoutError:
            self.emit("error", error={"message": "Pending work did not finish before disconnecting. Reconnect to check the saved JHA."})
        finally:
            await self.close()

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.capture:
            await self.capture.close()
            self.capture = None
        for task in (*self.audio_tasks, *self.commits):
            task.cancel()
        await asyncio.gather(*self.audio_tasks, *self.commits, return_exceptions=True)
        await self.conversation.close()
        self.track.stop()
        await self.connection.disconnect()
        self.on_closed(self.reference)


def create_app(*, transcriber=None, tts=None, client_factory=AsyncOpenAI):
    peers = {}
    max_sessions = int(os.environ.get("VERTO_VOICE_MAX_SESSIONS", "4"))
    token = os.environ.get("VERTO_VOICE_SERVICE_TOKEN", "")
    tenant = os.environ.get("VERTO_VOICE_TENANT", "")

    @asynccontextmanager
    async def lifespan(app):
        if len(token) < 32 or token.startswith("REPLACE_") or not tenant:
            raise RuntimeError("Set a service token of at least 32 characters and VERTO_VOICE_TENANT.")
        app.state.transcriber = transcriber
        if app.state.transcriber is None:
            from faster_whisper import WhisperModel
            model = await asyncio.to_thread(
                WhisperModel, os.environ.get("VERTO_STT_MODEL", "small.en"),
                device=os.environ.get("VERTO_STT_DEVICE", "cpu"),
                compute_type=os.environ.get("VERTO_STT_COMPUTE_TYPE", "int8"),
                cpu_threads=int(os.environ.get("VERTO_STT_CPU_THREADS", "4")), num_workers=2,
            )
            app.state.transcriber = LocalTranscriber(model)
        app.state.tts = tts or httpx.AsyncClient(base_url=os.environ.get("VERTO_TTS_URL", "http://127.0.0.1:8091"), timeout=45)
        # Warm-start readiness: don't negotiate a crew's call while downloading
        # weights or discovering that the voice service failed to start.
        health = await app.state.tts.get("/health")
        health.raise_for_status()
        if not health.json().get("ready"):
            raise RuntimeError("Speech synthesis is not ready")

        async def reap():
            while True:
                await asyncio.sleep(10)
                now = asyncio.get_running_loop().time()
                for peer in list(peers.values()):
                    if now - peer.last_message > 300:
                        await peer.close()

        reaper = asyncio.create_task(reap())
        try:
            yield
        finally:
            reaper.cancel()
            await asyncio.gather(reaper, return_exceptions=True)
            await asyncio.gather(*(peer.close() for peer in list(peers.values())), return_exceptions=True)
            if tts is None:
                await app.state.tts.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # FastAPI's default error includes input values; Offer contains a key.
        return JSONResponse({"detail": "Invalid voice session request."}, status_code=422)

    @app.get("/health")
    async def health():
        return {"ready": True}

    @app.post("/offer")
    async def offer(body: Offer, request: Request, authorization: str = Header(default="")):
        if not token or not hmac.compare_digest(authorization, "Bearer " + token):
            raise HTTPException(401, "Unauthorised voice service request")
        if body.tenant != tenant:
            raise HTTPException(403, "Wrong voice service tenant")
        if not body.sdp.startswith("v=0") or len(json.dumps(body.tools)) > 150_000:
            raise HTTPException(422, "Invalid voice session request")
        if len(peers) >= max_sessions:
            raise HTTPException(503, "The local voice service is at capacity")
        peer = None
        try:
            peer = Peer(body, request.app.state.transcriber, request.app.state.tts, token,
                        lambda reference: peers.pop(reference, None), client_factory=client_factory)
            peers[peer.reference] = peer
            await peer.connection.initialize(sdp=body.sdp, type="offer")
            await peer.connection.connect()
            answer = peer.connection.get_answer()
            return {"sdp": answer["sdp"], "session_reference": peer.reference}
        except Exception:
            if peer:
                await peer.close()
            log.warning("Local WebRTC negotiation failed")
            raise HTTPException(503, "Could not negotiate the local voice connection") from None

    return app


app = create_app()
