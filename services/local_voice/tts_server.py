"""Chatterbox Nano CPU service; one shared, warmed model per tenant worker."""
from __future__ import annotations

import asyncio
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


token = os.environ.get("VERTO_VOICE_SERVICE_TOKEN", "")
model = None
lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app):
    global model
    if len(token) < 32 or token.startswith("REPLACE_"):
        raise RuntimeError("Set VERTO_VOICE_SERVICE_TOKEN to at least 32 characters.")
    import torch
    from chatterbox.tts_turbo import ChatterboxTurboTTS

    torch.set_num_threads(int(os.environ.get("VERTO_TTS_CPU_THREADS", "4")))
    model = await asyncio.to_thread(ChatterboxTurboTTS.from_pretrained,
                                    device=os.environ.get("VERTO_TTS_DEVICE", "cpu"), nano=True)
    reference = os.environ.get("VERTO_VOICE_REFERENCE", "")
    if reference:
        await asyncio.to_thread(model.prepare_conditionals, reference)
    if model.conds is None:
        raise RuntimeError("Set VERTO_VOICE_REFERENCE to an authorised voice recording longer than five seconds.")
    # Exercise generation before readiness rather than on the first crew call.
    await asyncio.to_thread(model.generate, "Hello, I am PERI.")
    try:
        yield
    finally:
        model = None


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return {"ready": model is not None}


@app.post("/speech")
async def speech(body: Speech, authorization: str = Header(default="")):
    if not token or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "Unauthorised speech request")
    # Generation mutates the model's sampling state; serialize it. Barge-in is
    # handled by discarding obsolete audio at the gateway, never by blocking it.
    async with lock:
        try:
            task = asyncio.create_task(asyncio.to_thread(model.generate, body.text))
            try:
                wav = await asyncio.shield(task)
            except asyncio.CancelledError:
                # A cancelled request cannot stop a running CPU inference.
                # Retain the model lock until the worker thread actually exits.
                await task
                raise
            pcm = wav.detach().cpu().numpy().reshape(-1).clip(-1, 1)
            pcm = (pcm * 32767).astype("<i2").tobytes()
        except Exception:
            raise HTTPException(503, "Local speech generation failed") from None
    return Response(pcm, media_type="audio/pcm", headers={"X-Sample-Rate": str(model.sr)})
