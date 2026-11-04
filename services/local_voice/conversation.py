"""Streaming text reasoning, ordered browser tools and interruptible speech.

No microphone audio is passed to the OpenAI client. JHA mutations are executed
by the signed-in Verto browser, using its existing CSRF/permission checks.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import re
import uuid


class SentenceBuffer:
    def __init__(self):
        self.text = ""

    def add(self, delta: str, *, flush=False) -> list[str]:
        self.text += delta
        output = []
        while self.text:
            boundary = re.search(r'[.!?](?:["\u201d])?\s', self.text)
            end = boundary.end() if boundary else 0
            # Start speaking a long clause before the complete answer arrives.
            if not end and len(self.text) > 180:
                end = self.text.rfind(" ", 0, 180) + 1
            if not end and flush:
                end = len(self.text)
            if not end:
                break
            phrase, self.text = self.text[:end].strip(), self.text[end:]
            if phrase:
                output.append(phrase)
        return output


class Conversation:
    def __init__(self, *, client, model, effort, instructions, tools, send, speak, clear_audio):
        self.client, self.model, self.effort = client, model, effort
        self.instructions, self.tools = instructions, tools
        self.send, self.speak, self.clear_audio = send, speak, clear_audio
        self.history = []
        self.generation = 0
        self.closing = False
        self.stream = None
        self.tool_results = {}
        self.turns = asyncio.Queue(maxsize=8)
        self.speech = asyncio.Queue(maxsize=16)
        self.runner = asyncio.create_task(self._run())
        self.speaker = asyncio.create_task(self._speak())

    def emit(self, event_type, **values):
        self.send({"type": event_type, **values})

    async def interrupt(self):
        self.generation += 1
        self.clear_audio()
        # Never cancel a tool already sent to Verto. Its result must be retained
        # even when speech is interrupted, so a saved change isn't replayed.
        stream, self.stream = self.stream, None
        if stream:
            with contextlib.suppress(Exception):
                await stream.close()

    def submit(self, *, text="", instructions="", generation=None):
        if self.closing:
            return
        try:
            self.turns.put_nowait((text, instructions, self.generation if generation is None else generation))
        except asyncio.QueueFull:
            self.emit("error", error={"message": "PERI has too many pending turns. Wait for the current answer."})

    def tool_result(self, item):
        future = self.tool_results.get(item.get("call_id"))
        if future and not future.done():
            output = str(item.get("output") or "{}")
            if len(output) > 150_000:
                output = json.dumps({"ok": False, "error": "The JHA tool result was too large."})
            future.set_result(output)

    async def _run(self):
        while True:
            text, extra, generation = await self.turns.get()
            try:
                if text:
                    self.history.append({"role": "user", "content": text})
                await self._respond(generation, extra)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Provider exceptions can contain request content or credentials.
                self.emit("error", error={"message": "PERI could not complete this turn. Check the saved JHA before retrying."})
            finally:
                self.turns.task_done()

    async def _respond(self, generation, extra):
        self.emit("response.created", response={"id": uuid.uuid4().hex})
        self.emit("local.status", phase="thinking")
        if not self.history:
            self.history.append({"role": "user", "content": extra or "Resume the saved JHA and ask the next missing question."})
        # Preserve whole tool exchanges. Never trim an individual call/output.
        if len(json.dumps(self.history)) > 500_000:
            raise RuntimeError("Reconnect to reload the persisted JHA context.")
        for _ in range(16):
            buffer = SentenceBuffer()
            generated = ""
            completed = None
            params = dict(
                model=self.model, instructions=self.instructions + "\n" + extra,
                input=self.history, tools=self.tools, tool_choice="auto", parallel_tool_calls=False,
                stream=True, store=False, include=["reasoning.encrypted_content"], max_output_tokens=4096,
            )
            if self.effort:
                params["reasoning"] = {"effort": self.effort}
            stream = await self.client.responses.create(**params)
            self.stream = stream
            try:
                async for event in stream:
                    if generation != self.generation:
                        break
                    if event.type == "response.output_text.delta":
                        generated += event.delta
                        for phrase in buffer.add(event.delta):
                            await self.speech.put((generation, phrase))
                    elif event.type == "response.completed":
                        completed = event.response
                    elif event.type in {"response.failed", "response.incomplete", "error"}:
                        raise RuntimeError("Incomplete text response")
            except Exception:
                if generation == self.generation:
                    raise
            finally:
                if self.stream is stream:
                    self.stream = None
                await stream.close()
            if completed is None:
                # An interrupted output must not leave orphaned function calls.
                if generated:
                    self.history.append({"role": "assistant", "content": generated + " [Interrupted by crew]"})
                return
            output = [item.model_dump(exclude_none=True) for item in completed.output]
            self.history.extend(output)
            for phrase in buffer.add("", flush=True):
                await self.speech.put((generation, phrase))
            calls = [item for item in output if item.get("type") == "function_call"]
            if not calls:
                await self.speech.put((generation, None))
                return
            for call in calls:
                if call.get("name") not in {tool["name"] for tool in self.tools}:
                    raise RuntimeError("Unknown tool")
                if generation != self.generation:
                    self.history.append({"type": "function_call_output", "call_id": call["call_id"],
                                         "output": json.dumps({"ok": False, "cancelled": True,
                                             "message": "The crew interrupted before this tool was dispatched. Read current state before continuing."})})
                    continue
                future = asyncio.get_running_loop().create_future()
                self.tool_results[call["call_id"]] = future
                self.emit("response.function_call_arguments.done", call_id=call["call_id"],
                          name=call["name"], arguments=call["arguments"])
                try:
                    result = await asyncio.wait_for(future, 30)
                except TimeoutError:
                    result = json.dumps({"ok": False, "error": "The tool result was not confirmed. Read the current JHA before repeating any change."})
                    self.emit("error", error={"message": "A JHA update was not confirmed. Check the saved draft before repeating it."})
                finally:
                    self.tool_results.pop(call["call_id"], None)
                self.history.append({"type": "function_call_output", "call_id": call["call_id"], "output": result})
            if generation != self.generation:
                return
        raise RuntimeError("Too many consecutive tool calls")

    async def _speak(self):
        spoken = ""
        previous_generation = -1
        while True:
            generation, phrase = await self.speech.get()
            try:
                if generation != self.generation:
                    continue
                if previous_generation != generation:
                    spoken, previous_generation = "", generation
                if phrase is None:
                    self.emit("response.output_audio_transcript.done", transcript=spoken)
                    self.emit("response.done")
                    self.emit("local.status", phase="idle")
                else:
                    # The synthesizer starts returning audio a phrase at a time;
                    # reasoning continues while this phrase is being spoken.
                    await self.speak(phrase, generation)
                    if generation != self.generation:
                        continue
                    spoken += (" " if spoken else "") + phrase
                    self.emit("response.output_audio_transcript.delta", delta=(" " if spoken != phrase else "") + phrase)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.emit("error", error={"message": "The local voice could not generate speech. Reconnect after checking the speech service."})
            finally:
                self.speech.task_done()

    async def finish(self):
        self.closing = True
        await self.turns.join()
        await self.speech.join()

    async def close(self):
        self.closing = True
        await self.interrupt()
        for task in (self.runner, self.speaker):
            task.cancel()
        await asyncio.gather(self.runner, self.speaker, return_exceptions=True)
        await self.client.close()
        self.history.clear()
