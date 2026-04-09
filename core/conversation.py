from typing import Any
from config import SHORT_TERM_MAX_TURNS, SYSTEM_PROMPT


class ConversationHistory:
    def __init__(self):
        self._messages: list[dict[str, Any]] = []

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def add_tool_call(self, tool_calls: list[dict]) -> None:
        """Add assistant message with tool_calls."""
        self._messages.append({"role": "assistant", "tool_calls": tool_calls})

    def add_tool_result(self, tool_call_id: str, name: str, result: str) -> None:
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": result,
        })

    def get_messages(self, memory_context: str = "") -> list[dict]:
        system = SYSTEM_PROMPT
        if memory_context:
            system += f"\n\n[Relevant memories about this user]\n{memory_context}"
        return [{"role": "system", "content": system}] + list(self._messages)

    def _trim(self) -> None:
        # Keep only last N turns (each turn = user + assistant)
        max_messages = SHORT_TERM_MAX_TURNS * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    def clear(self) -> None:
        self._messages.clear()
