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

# Prefix used to signal tool events in the stream
TOOL_EVENT_PREFIX = "__TOOL__"


class Orchestrator:
    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry
        self.history = ConversationHistory()
        self._model_index = 0
        self._model = LLM_MODELS[0]

    def process(self, user_input: str, memory_context: str = "") -> str:
        """Blocking version — returns full response string."""
        return "".join(
            t for t in self.process_stream(user_input, memory_context)
            if not t.startswith(TOOL_EVENT_PREFIX)
        )

    def process_stream(self, user_input: str, memory_context: str = "") -> Generator[str, None, None]:
        """
        Yields:
          "__TOOL__tool_name"  — tool is about to run (display status)
          "token text"         — response tokens (display live)
        """
        self.history.add_user(user_input)
        messages = self.history.get_messages(memory_context)
        loop_messages = list(messages)
        tools = self.registry.get_definitions()
        full_response = ""

        for _ in range(10):
            try:
                probe = _client.chat.completions.create(
                    model=self._model,
                    messages=loop_messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=300,
                )
            except Exception as e:
                if not self._try_next_model():
                    msg = "All models unavailable right now, sir."
                    yield msg
                    self.history.add_assistant(msg)
                    return
                time.sleep(1)
                continue

            msg = probe.choices[0].message

            # ── Final answer — stream it ──────────────────────────────────────
            if not msg.tool_calls:
                try:
                    stream = _client.chat.completions.create(
                        model=self._model,
                        messages=loop_messages,
                        tools=tools,
                        tool_choice="none",
                        temperature=0.7,
                        max_tokens=512,
                        stream=True,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            full_response += delta
                            yield delta
                except Exception:
                    full_response = msg.content or ""
                    yield full_response

                self.history.add_assistant(full_response)
                return

            # ── Tool calls — emit events + execute ────────────────────────────
            tool_calls_raw = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            loop_messages.append({"role": "assistant", "tool_calls": tool_calls_raw})

            for tc in msg.tool_calls:
                name = tc.function.name
                yield f"{TOOL_EVENT_PREFIX}{name}"   # UI picks this up
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                result = self.registry.dispatch(name, args)
                loop_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": result,
                })

        full_response = "Done, sir."
        yield full_response
        self.history.add_assistant(full_response)

    def _try_next_model(self) -> bool:
        self._model_index += 1
        if self._model_index >= len(LLM_MODELS):
            self._model_index = 0
            return False
        self._model = LLM_MODELS[self._model_index]
        return True
