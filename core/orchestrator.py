import json
import time
from typing import Generator, Callable, Optional
from core.conversation import ConversationHistory
from core.tool_registry import ToolRegistry
from core.api_manager import APIManager
from core import stats as _stats
from core.error_log import log_error

TOOL_EVENT_PREFIX = "__TOOL__"
TOOL_RESULT_PREFIX = "__TOOL_RESULT__"
_MAX_TOKENS_BY_TIER = {
    "light": 1024,
    "heavy": 4096,
    "coder": 4096,
}


def _is_quota_or_rate_limit(error_text: str) -> bool:
    lower = error_text.lower()
    markers = (
        "402",
        "429",
        "credits",
        "quota",
        "rate limit",
        "too many requests",
        "resource_exhausted",
    )
    return any(marker in lower for marker in markers)


def _is_tool_use_unsupported(error_text: str) -> bool:
    lower = error_text.lower()
    markers = (
        "support tool use",
        "tool use",
        "tool_choice",
        "tools",
        "function calling",
    )
    return any(marker in lower for marker in markers)


def _should_retry_without_tools(error_text: str) -> bool:
    lower = error_text.lower()
    markers = (
        "prompt tokens limit exceeded",
        "context length",
        "context window",
        "maximum context length",
        "too many input tokens",
    )
    return any(marker in lower for marker in markers)


class Orchestrator:
    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry
        self.history  = ConversationHistory()
        self._api     = APIManager()

    # ── Public helpers ────────────────────────────────────────────────────────
    def process(self, user_input: str, memory_context: str = "") -> str:
        return "".join(
            t for t in self.process_stream(user_input, memory_context)
            if not t.startswith(TOOL_EVENT_PREFIX) and not t.startswith(TOOL_RESULT_PREFIX)
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
        model_tier    — "light", "heavy", "coder", or "auto"
        """
        # Reset to primary each turn, then move to tier start if specified
        self._api.reset()
        if model_tier in ("light", "heavy", "coder"):
            self._api.set_tier(model_tier)

        self.history.add_user(user_input)
        messages      = self.history.get_messages(memory_context)
        loop_messages = list(messages)
        tools         = self.registry.get_definitions()
        full_response = ""
        allow_tools   = True

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
                    max_tokens = _MAX_TOKENS_BY_TIER.get(self._api.current_tier, 400)
                    request_kwargs = {
                        "model": self._api.current_model,
                        "messages": loop_messages,
                        "temperature": 0.7,
                        "max_tokens": max_tokens,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    }
                    if allow_tools:
                        request_kwargs["tools"] = tools
                        request_kwargs["tool_choice"] = "auto"
                    stream = client.chat.completions.create(**request_kwargs)
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"
                    log_error("orchestrator", last_err)
                    err_str = str(e)
                    if allow_tools and (_is_tool_use_unsupported(err_str) or _should_retry_without_tools(err_str)):
                        allow_tools = False
                        time.sleep(0.2)
                        continue
                    retryable_quota = _is_quota_or_rate_limit(err_str)
                    if self._api.try_next():
                        allow_tools = True
                        time.sleep(0.5)
                        continue

                    if retryable_quota and ("402" in err_str or "credits" in err_str.lower()):
                        msg = (
                            "⚠  All configured model keys are out of credits or quota.\n"
                            "   Add another key with /add-api or wait for limits to reset."
                        )
                    elif retryable_quota:
                        msg = (
                            "⚠  All configured model keys are rate-limited right now.\n"
                            "   Jarvis tried the full key/model pool and ran out of fallback options."
                        )
                    else:
                        msg = f"API error — {last_err}"
                        yield msg
                        self.history.add_assistant(msg)
                        return
                    yield msg
                    self.history.add_assistant(msg)
                    return

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

                try:
                    args = json.loads(tc["args"]) if tc["args"] else {}
                except json.JSONDecodeError:
                    args = {}
                yield f"{TOOL_EVENT_PREFIX}{json.dumps({'name': tc['name'], 'args': args}, ensure_ascii=False)}"
                result = self.registry.dispatch(tc["name"], args)
                state = "failed" if result.strip().lower().startswith("error") else "done"
                yield f"{TOOL_RESULT_PREFIX}{json.dumps({'state': state, 'name': tc['name'], 'detail': result}, ensure_ascii=False)}"
                loop_messages.append({
                    "role":         "tool",
                    "tool_call_id": tc["id"],
                    "name":         tc["name"],
                    "content":      result,
                })

            full_response = ""
            allow_tools = True

        yield "Done, sir."
        self.history.add_assistant("Done, sir.")
