import asyncio
import json
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import httpx
from aiortc import AudioStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription

from services.local_voice.gateway import create_app
from services.local_voice.audio import SpeechTrack
from services.local_voice.tests.test_conversation import Stream, complete


class TestGateway(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Keep the integration test on loopback rather than probing host NICs.
        addresses = patch("aioice.ice.get_host_addresses", return_value=["127.0.0.1"])
        addresses.start()
        self.addCleanup(addresses.stop)
        self.environment = patch.dict(os.environ, {"VERTO_VOICE_SERVICE_TOKEN": "t" * 48, "VERTO_VOICE_TENANT": "tenant.test", "VERTO_VOICE_MAX_SESSIONS": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.requests, self.events = [], []

        async def create(**params):
            self.requests.append(params)
            return Stream([NS(type="response.output_text.delta", delta="Which valve? "),
                           complete({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Which valve?"}]})])

        def client_factory(**params):
            return NS(responses=NS(create=create), close=AsyncMock())

        async def transcribe(pcm):
            return "Isolate the pump" if len(pcm) > 6400 else ""

        health = httpx.Response(200, json={"ready": True}, request=httpx.Request("GET", "http://tts/health"))
        speech = httpx.Response(200, content=bytes(2400), headers={"X-Sample-Rate": "24000"}, request=httpx.Request("POST", "http://tts/speech"))
        self.tts = NS(get=AsyncMock(return_value=health), post=AsyncMock(return_value=speech))
        self.app = create_app(transcriber=NS(transcribe=transcribe), tts=self.tts, client_factory=client_factory)
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.http = await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://voice"))
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.addAsyncCleanup(self.pc.close)
        self.pc.addTrack(AudioStreamTrack())
        self.channel = self.pc.createDataChannel("oai-events")
        self.channel.on("message", lambda raw: self.events.append(json.loads(raw)))
        await self.pc.setLocalDescription(await self.pc.createOffer())
        self.body = {"sdp": self.pc.localDescription.sdp, "tenant": "tenant.test", "model": "text-model",
                     "instructions": "JHA rules", "tools": [], "openai_api_key": "TEST_KEY_NOT_FOR_BROWSER"}

    async def wait_for(self, predicate):
        async with asyncio.timeout(8):
            while not predicate():
                await asyncio.sleep(0.01)

    async def test_auth_tenant_and_validation_do_not_echo_credentials(self):
        response = await self.http.post("/offer", json=self.body)
        self.assertEqual(response.status_code, 401)
        response = await self.http.post("/offer", json={**self.body, "tenant": "other.test"}, headers={"Authorization": "Bearer " + "t" * 48})
        self.assertEqual(response.status_code, 403)
        response = await self.http.post("/offer", json={**self.body, "tools": "invalid"}, headers={"Authorization": "Bearer " + "t" * 48})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("TEST_KEY", response.text)

    async def test_same_webrtc_call_handles_multiple_microphone_turns(self):
        response = await self.http.post("/offer", json=self.body, headers={"Authorization": "Bearer " + "t" * 48})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()), {"sdp", "session_reference"})
        self.assertNotIn("TEST_KEY", response.text)
        await self.pc.setRemoteDescription(RTCSessionDescription(type="answer", sdp=response.json()["sdp"]))
        await self.wait_for(lambda: self.channel.readyState == "open")
        # Capacity is an explicit rejection, not a silent fallback to cloud voice.
        busy = await self.http.post("/offer", json=self.body, headers={"Authorization": "Bearer " + "t" * 48})
        self.assertEqual(busy.status_code, 503)
        for expected in (1, 2):
            self.channel.send(json.dumps({"type": "local.input.start"}))
            await asyncio.sleep(0.5)
            self.assertEqual(len(self.requests), expected - 1)
            self.channel.send(json.dumps({"type": "local.input.commit"}))
            await self.wait_for(lambda: len([e for e in self.events if e["type"] == "response.done"]) == expected)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.pc.connectionState, "connected")
        self.assertEqual(len([e for e in self.events if e["type"] == "conversation.item.input_audio_transcription.completed"]), 2)
        self.channel.send(json.dumps({"type": "session.close"}))
        await self.wait_for(lambda: any(e["type"] == "session.closed" for e in self.events))

    async def test_interrupt_discards_queued_rtp_audio(self):
        track = SpeechTrack()
        self.addCleanup(track.stop)
        await track.add(bytes([1, 0]) * track.SAMPLES, 0)
        track.clear()
        frame = await track.recv()
        self.assertFalse(frame.to_ndarray().any())


if __name__ == "__main__":
    unittest.main()
