import asyncio
import unittest

from services.local_voice.speech import Capture


class TestCapture(unittest.IsolatedAsyncioTestCase):
    async def test_live_hypothesis_is_replaced_and_only_final_text_is_committed(self):
        class Transcriber:
            async def transcribe(self, pcm):
                return "Isolate pump four" if len(pcm) > 10000 else "Isolate pump"

        partials = []
        capture = Capture(Transcriber(), partials.append, 2)
        self.addAsyncCleanup(capture.close)
        capture.add(bytes(8000))
        await asyncio.sleep(0.75)
        self.assertEqual(partials, ["Isolate pump"])
        capture.add(bytes(8000))
        result = await capture.finish()
        self.assertEqual(result, "Isolate pump four")
        self.assertFalse(capture.audio)
        self.assertEqual(capture.generation, 2)

    async def test_turn_buffer_is_bounded(self):
        capture = Capture(None, lambda text: None, 0)
        self.addAsyncCleanup(capture.close)
        with self.assertRaises(ValueError):
            capture.add(bytes(capture.MAX_BYTES + 1))
