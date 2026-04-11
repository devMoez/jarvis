import json
import time
from typing import Generator, Callable, Optional
from core.conversation import ConversationHistory
from core.tool_registry import ToolRegistry
from core.api_manager import APIManager
from core import stats as _stats
from core.error_log import log_error

TOOL_EVENT_PREFIX = "__TOOL__"


class Orchestrator:
    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry
        self.history  = ConversationHistory()
        self._api     = APIManager()

    # ── Public helpers ────────────────────────────────────────────────────────
    def process(self, user_input: str, memory_context: str = "") -> str:
        return "".join(
            t for t in self.process_stream(user_input, memory_context)
            if not t.startswith(TOOL_EVENT_PREFIX)
        )

    # ── Streaming core ────────────────────────────────────────────────────────
    def process_stream(
        self,
        user_input:     str,
        memory_context: str = "",
        abort_check:    Optional[Callable[[], bool]] = None,
        model_tier:     str = "auto",
    ) -> Generator[str, None, None]:
        """
        Streams response tokens.  Yields:
          "__TOOL__tool_name"  — tool about to execute (display only)
          "token"              — streamed text token
        abort_check() — if callable returns True mid-stream, cancels gracefully.
        model_tier    — "light" (fast/cheap), "heavy" (smart), or "auto" (primary chain)
        """
        # Reset to primary each turn, then move to tier start if specified
        self._api.reset()
        if model_tier in ("light", "heavy"):
            self._api.set_tier(model_tier)

        self.history.add_user(user_input)
        messages      = self.history.get_messages(memory_context)
        loop_messages = list(messages)
        tools         = self.registry.get_definitions()
        full_response = ""

        for _round in range(10):
            # ── Abort checkpoint ─────────────────────────────────────────────
            if abort_check and abort_check():
                msg = "Task cancelled, sir."
                yield msg
                self.history.add_assistant(msg)
                return

            # ── Model fallback loop (separate from tool-use rounds) ──────────
            stream = None
            while stream is None:
                client = self._api.get_client()
                if client is None:
                    msg = "No API keys configured. Use /add-api <provider> <key> to add one, sir."
                    yield msg
                    self.history.add_assistant(msg)
                    return
                try:
                    stream = client.chat.completions.create(
                        model=self._api.current_model,
                        messages=loop_messages,
                        tools=tools,
                        tool_choice="auto",
                        temperature=0.7,
                        max_tokens=900,
                        stream=True,
                        stream_options={"include_usage": True},
                    )
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"
                    log_error("orchestrator", last_err)
                    # 402 = insufficient credits — give a clear message immediately
                    err_str = str(e)
                    if "402" in err_str and "credits" in err_str.lower():
                        msg = (
                            "⚠  OpenRouter credit balance too low.\n"
                            "   Top up at: https://openrouter.ai/settings/credits\n"
                            "   Or switch to a free model: /add-api openrouter <new-key>"
                        )
                        yield msg
                        self.history.add_assistant(msg)
                        return
                    if not self._api.try_next():
                        msg = f"API error — {last_err}"
                        yield msg
                        self.history.add_assistant(msg)
                        return
                    time.sleep(0.5)

            # ── Accumulate streaming chunks ───────────────────────────────────
            tool_calls_acc: dict[int, dict] = {}

            for chunk in stream:
                # Abort mid-stream
                if abort_check and abort_check():
                    msg = "\nTask cancelled, sir."
                    yield msg
                    self.history.add_assistant(full_response + msg)
                    return

                # Final usage chunk (no choices when include_usage=True)
                if not chunk.choices:
                    if chunk.usage:
                        try:
                            _stats.record(chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
                        except Exception:
                            pass
                    continue

                choice = chunk.choices[0]
                delta  = choice.delta

                if delta.content:
                    full_response += delta.content
                    yield delta.content

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "args": ""}
                        if tc.id:
                            tool_calls_acc[idx]["id"]   += tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["args"] += tc.function.arguments

            # ── Pure text response — done ─────────────────────────────────────
            if not tool_calls_acc:
                self.history.add_assistant(full_response)
                return

            # ── Tool calls — execute and loop ─────────────────────────────────
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
                if abort_check and abort_check():
                    msg = "\nTask cancelled, sir."
                    yield msg
                    self.history.add_assistant(full_response + msg)
                    return

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

            full_response = ""

        yield "Done, sir."
        self.history.add_assistant("Done, sir.")
