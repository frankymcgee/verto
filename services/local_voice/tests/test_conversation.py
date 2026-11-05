import asyncio
import copy
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

from services.local_voice.conversation import Conversation, SentenceBuffer


def complete(*items):
    return NS(type="response.completed", response=NS(output=[NS(model_dump=lambda exclude_none=True, value=item: value) for item in items]))


class Stream:
    def __init__(self, events, gate=None):
        self.events, self.gate, self.closed = events, gate, False

    async def __aiter__(self):
        for event in self.events:
            await asyncio.sleep(0)
            if self.closed:
                return
            if event.type == "response.completed" and self.gate:
                await self.gate.wait()
            yield event

    async def close(self):
        self.closed = True


class TestConversation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events, self.spoken, self.requests, self.streams = [], [], [], []

        async def create(**params):
            self.requests.append(copy.deepcopy(params))
            return self.streams.pop(0)

        async def speak(text, generation):
            self.spoken.append((text, generation))

        self.client = NS(responses=NS(create=create), close=AsyncMock())
        self.voice = Conversation(client=self.client, model="configured-text-model", effort="low", instructions="Shared JHA rules",
                                  tools=[{"name": "record_work_step", "type": "function"}],
                                  send=self.events.append, speak=speak, clear_audio=Mock())
        self.addAsyncCleanup(self.voice.close)

    async def wait_for(self, predicate):
        async with asyncio.timeout(3):
            while not predicate():
                await asyncio.sleep(0.005)

    async def test_speaks_first_sentence_before_the_full_response_completes(self):
        gate = asyncio.Event()
        self.streams.append(Stream([NS(type="response.output_text.delta", delta="Which pump are you working on? "),
                                    complete({"type": "message", "role": "assistant", "content": []})], gate))
        self.voice.submit(text="We are isolating the pump")
        await self.wait_for(lambda: self.spoken)
        self.assertFalse(gate.is_set())
        self.assertEqual(self.spoken[0][0], "Which pump are you working on?")
        self.assertFalse(any(event["type"] == "response.done" for event in self.events))
        gate.set()
        await self.voice.turns.join()
        await self.voice.speech.join()
        request = self.requests[0]
        self.assertFalse(request["store"])
        self.assertTrue(request["stream"])
        self.assertFalse(request["parallel_tool_calls"])
        self.assertEqual(request["input"], [{"role": "user", "content": "We are isolating the pump"}])

    async def test_interruption_keeps_an_already_dispatched_tool_result(self):
        self.streams.append(Stream([complete({"type": "function_call", "name": "record_work_step", "call_id": "save-1", "arguments": "{}"})]))
        self.voice.submit(text="Record the isolation step")
        await self.wait_for(lambda: self.voice.tool_results)
        await self.voice.interrupt()
        self.voice.tool_result({"call_id": "save-1", "output": json.dumps({"saved": True})})
        await self.voice.turns.join()
        self.assertEqual(self.voice.history[-1], {"type": "function_call_output", "call_id": "save-1", "output": '{"saved": true}'})
        self.assertEqual(len([event for event in self.events if event["type"] == "response.function_call_arguments.done"]), 1)
        self.assertEqual(self.spoken, [])
        self.voice.clear_audio.assert_called_once()

    async def test_tool_result_continues_reasoning_before_the_next_spoken_question(self):
        self.streams.extend([
            Stream([complete({"type": "function_call", "name": "record_work_step", "call_id": "save", "arguments": "{}"})]),
            Stream([NS(type="response.output_text.delta", delta="What is the hazard? "), complete({"type": "message", "role": "assistant", "content": []})]),
        ])
        self.voice.submit(text="Record isolation")
        await self.wait_for(lambda: self.voice.tool_results)
        self.assertEqual(self.spoken, [])
        self.voice.tool_result({"call_id": "save", "output": '{"saved":true}'})
        await self.voice.turns.join()
        await self.voice.speech.join()
        self.assertEqual(self.requests[1]["input"][-1]["type"], "function_call_output")
        self.assertEqual(self.spoken[0][0], "What is the hazard?")

    async def test_stale_speech_is_discarded_after_barge_in(self):
        self.voice.speech.put_nowait((0, "Old instructions."))
        await self.voice.interrupt()
        await self.voice.speech.join()
        self.assertEqual(self.spoken, [])

    async def test_unknown_tool_is_never_forwarded_to_the_browser(self):
        self.streams.append(Stream([complete({"type": "function_call", "name": "approve_jha", "call_id": "not-allowed", "arguments": "{}"})]))
        self.voice.submit(text="Approve this")
        await self.voice.turns.join()
        self.assertFalse(self.voice.tool_results)
        self.assertFalse(any(event["type"] == "response.function_call_arguments.done" for event in self.events))
        self.assertTrue(any(event["type"] == "error" for event in self.events))


class TestSentenceBuffer(unittest.TestCase):
    def test_partial_sentences_are_not_lost_or_repeated(self):
        buffer = SentenceBuffer()
        self.assertEqual(buffer.add("Isolate the"), [])
        self.assertEqual(buffer.add(" pump. Check"), ["Isolate the pump."])
        self.assertEqual(buffer.add(" the valve", flush=True), ["Check the valve"])

    def test_token_boundary_does_not_split_a_decimal(self):
        buffer = SentenceBuffer()
        self.assertEqual(buffer.add("Pressure is 1."), [])
        self.assertEqual(buffer.add("5 bar. Check"), ["Pressure is 1.5 bar."])
