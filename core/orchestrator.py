import json
import time
from typing import Generator
import openai
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODELS
from core.conversation import ConversationHistory
from core.tool_registry import ToolRegistry

_client = openai.OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    default_headers={
        "HTTP-Referer": "https://jarvis.local",
        "X-Title": "Jarvis AI",
    },
)

TOOL_EVENT_PREFIX = "__TOOL__"


class Orchestrator:
    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry
        self.history = ConversationHistory()
        self._model_index = 0
        self._model = LLM_MODELS[0]

    def process(self, user_input: str, memory_context: str = "") -> str:
        return "".join(
            t for t in self.process_stream(user_input, memory_context)
            if not t.startswith(TOOL_EVENT_PREFIX)
        )

    def process_stream(self, user_input: str, memory_context: str = "") -> Generator[str, None, None]:
        """
        Single streaming call per round — no probe.
        Yields:
          "__TOOL__tool_name"  — tool about to execute
          "token"              — streamed response text
        """
        self.history.add_user(user_input)
        messages = self.history.get_messages(memory_context)
        loop_messages = list(messages)
        tools = self.registry.get_definitions()
        full_response = ""

        for _round in range(10):
            try:
                stream = _client.chat.completions.create(
                    model=self._model,
                    messages=loop_messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=512,
                    stream=True,
                )
            except Exception as e:
                if not self._try_next_model():
                    msg = "All models unavailable right now, sir."
                    yield msg
                    self.history.add_assistant(msg)
                    return
                time.sleep(1)
                continue

            # ── Accumulate streaming chunks ───────────────────────────────────
            text_chunks: list[str] = []
            tool_calls_acc: dict[int, dict] = {}   # index → {id, name, args}
            finish_reason = None

            for chunk in stream:
                choice = chunk.choices[0]
                delta  = choice.delta
                finish_reason = choice.finish_reason or finish_reason

                # Text token — yield immediately
                if delta.content:
                    text_chunks.append(delta.content)
                    full_response += delta.content
                    yield delta.content

                # Tool call delta — accumulate
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "args": ""}
                        if tc.id:
                            tool_calls_acc[idx]["id"] += tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["args"] += tc.function.arguments

            # ── Pure text response — done ─────────────────────────────────────
            if not tool_calls_acc:
                self.history.add_assistant(full_response)
                return

            # ── Tool calls — build history entry + execute ────────────────────
            tool_calls_raw = [
                {
                    "id":   tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"]},
                }
                for tc in tool_calls_acc.values()
            ]
            loop_messages.append({"role": "assistant", "tool_calls": tool_calls_raw})

            for tc in tool_calls_acc.values():
                yield f"{TOOL_EVENT_PREFIX}{tc['name']}"
                try:
                    args = json.loads(tc["args"]) if tc["args"] else {}
                except json.JSONDecodeError:
                    args = {}
                result = self.registry.dispatch(tc["name"], args)
                loop_messages.append({
                    "role":         "tool",
                    "tool_call_id": tc["id"],
                    "name":         tc["name"],
                    "content":      result,
                })

            # Reset full_response for next round (tool result round)
            full_response = ""

        yield "Done, sir."
        self.history.add_assistant("Done, sir.")

    def _try_next_model(self) -> bool:
        self._model_index += 1
        if self._model_index >= len(LLM_MODELS):
            self._model_index = 0
            return False
        self._model = LLM_MODELS[self._model_index]
        return True
