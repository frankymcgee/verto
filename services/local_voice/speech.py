"""Shared local speech models, with streaming partial hypotheses per utterance."""
from __future__ import annotations

import asyncio

import numpy as np


class LocalTranscriber:
    def __init__(self, model, *, workers=2):
        self.model = model
        self.capacity = asyncio.Semaphore(workers)

    async def transcribe(self, pcm: bytes) -> str:
        # The in-memory array is streamed from WebRTC. No audio files or OpenAI
        # audio endpoints are used. Partial passes and the final pass share the
        # same model rather than loading one model for each connected crew.
        if len(pcm) < 6400:
            return ""
        async with self.capacity:
            task = asyncio.create_task(asyncio.to_thread(self._decode, pcm))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # Cancelling a coroutine cannot stop CTranslate2's CPU thread.
                # Keep its capacity slot until inference actually finishes.
                await task
                raise

    def _decode(self, pcm):
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(audio, language="en", beam_size=1, vad_filter=True,
                                            condition_on_previous_text=False)
        return " ".join(segment.text.strip() for segment in segments).strip()


class Capture:
    """Independent utterance buffer; snapshots make barge-in safe during finalisation."""
    MAX_BYTES = 16000 * 2 * 120

    def __init__(self, transcriber, partial, generation):
        self.transcriber, self.partial, self.generation = transcriber, partial, generation
        self.audio = bytearray()
        self.active = True
        self.last_text = ""
        self.decoded_size = -1
        self.decoding = False
        self.task = asyncio.create_task(self._partials())

    def add(self, pcm):
        if len(self.audio) + len(pcm) > self.MAX_BYTES:
            raise ValueError("Release the microphone after a maximum of two minutes per turn.")
        self.audio.extend(pcm)

    async def _partials(self):
        last_size = 0
        while self.active:
            await asyncio.sleep(0.7)
            if not self.active or len(self.audio) == last_size:
                continue
            pcm = bytes(self.audio)
            last_size = len(pcm)
            try:
                self.decoding = True
                text = await self.transcriber.transcribe(pcm)
            except Exception:
                # The final pass reports a service failure; never commit a
                # partial hypothesis just because that final pass failed.
                continue
            finally:
                self.decoding = False
            self.decoded_size = len(pcm)
            self.last_text = text
            if self.active:
                self.partial(text)

    async def finish(self):
        self.active = False
        if not self.decoding:
            self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        pcm = bytes(self.audio)
        self.audio.clear()
        if self.decoded_size == len(pcm):
            return self.last_text
        return await self.transcriber.transcribe(pcm)

    async def close(self):
        self.active = False
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        self.audio.clear()
