"""WebRTC audio pacing and immediate removal of interrupted queued speech."""
from __future__ import annotations

import asyncio
import fractions
import time

import numpy as np
from aiortc import AudioStreamTrack
from av import AudioFrame


class SpeechTrack(AudioStreamTrack):
    RATE = 24000
    SAMPLES = RATE // 50

    def __init__(self):
        super().__init__()
        self.frames = asyncio.Queue(maxsize=100)  # At most two seconds ahead.
        self.generation = 0
        self.pts = 0
        self.started = None

    def clear(self):
        self.generation += 1
        while not self.frames.empty():
            self.frames.get_nowait()
            self.frames.task_done()

    async def add(self, pcm: bytes, generation: int):
        step = self.SAMPLES * 2
        for offset in range(0, len(pcm), step):
            if generation != self.generation:
                return
            chunk = pcm[offset:offset + step].ljust(step, b"\0")
            await self.frames.put((generation, chunk))

    async def recv(self):
        if self.started is None:
            self.started = time.monotonic()
        delay = self.started + self.pts / self.RATE - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        pcm = bytes(self.SAMPLES * 2)
        while not self.frames.empty():
            generation, chunk = self.frames.get_nowait()
            self.frames.task_done()
            if generation == self.generation:
                pcm = chunk
                break
        frame = AudioFrame.from_ndarray(np.frombuffer(pcm, dtype=np.int16)[None, :], format="s16", layout="mono")
        frame.sample_rate = self.RATE
        frame.pts = self.pts
        frame.time_base = fractions.Fraction(1, self.RATE)
        self.pts += self.SAMPLES
        return frame
