from typing import Any
from config import SHORT_TERM_MAX_TURNS, SYSTEM_PROMPT, PERSONA_PROMPTS
from core.skills import get_skills_prompt
from core.profile import get_profile_prompt

# Active persona — set by /funny, /stealth, /think, /roast, /normal
_active_persona: str | None = None

def set_persona(name: str | None) -> None:
    global _active_persona
    _active_persona = name

def get_persona() -> str | None:
    return _active_persona


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
        if _active_persona and _active_persona in PERSONA_PROMPTS:
            system += f"\n\n{PERSONA_PROMPTS[_active_persona]}"
        profile = get_profile_prompt()
        if profile:
            system += f"\n\n{profile}"
        skills = get_skills_prompt()
        if skills:
            system += f"\n\n{skills}"
        if memory_context:
            system += f"\n\n[Relevant memories]\n{memory_context}"
        return [{"role": "system", "content": system}] + list(self._messages)

    def _trim(self) -> None:
        # Keep only last N turns (each turn = user + assistant)
        max_messages = SHORT_TERM_MAX_TURNS * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    def clear(self) -> None:
        self._messages.clear()
