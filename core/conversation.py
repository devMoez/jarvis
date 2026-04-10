import json
import os
from typing import Any
from config import SHORT_TERM_MAX_TURNS, SYSTEM_PROMPT, PERSONA_PROMPTS
from core.skills import get_skills_prompt
from core.profile import get_profile_prompt

_SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "session.json")

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
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        """Load the previous session's messages from disk on startup."""
        try:
            path = os.path.abspath(_SESSION_FILE)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    # Only keep plain user/assistant messages (drop tool internals)
                    self._messages = [
                        m for m in data
                        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
                        and isinstance(m.get("content"), str)
                    ]
                    self._trim()
        except Exception:
            self._messages = []

    def save(self) -> None:
        """Overwrite the session file with the current conversation."""
        try:
            path = os.path.abspath(_SESSION_FILE)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Only persist plain user/assistant messages
            saveable = [
                m for m in self._messages
                if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
            ]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(saveable, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Mutations ─────────────────────────────────────────────────────────────
    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})
        self._trim()
        self.save()   # persist after every complete exchange

    def add_tool_call(self, tool_calls: list[dict]) -> None:
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
        max_messages = SHORT_TERM_MAX_TURNS * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    def clear(self) -> None:
        self._messages.clear()
        self.save()
