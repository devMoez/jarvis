import json
import os
from typing import Any
from pathlib import Path
from config import SHORT_TERM_MAX_TURNS, SYSTEM_PROMPT, PERSONA_PROMPTS, EXTENDED_MODES
from core.skills import get_skills_prompt
from core.profile import get_profile_prompt

_SESSION_FILE     = os.path.join(os.path.dirname(__file__), "..", "data", "session.json")
_CUSTOM_MODES_FILE = Path(__file__).parent.parent / "data" / "custom_modes.json"
_ACTIVE_MODE_FILE = Path(__file__).parent.parent / "data" / "active_mode.json"


def _load_active_mode() -> str | None:
    try:
        if _ACTIVE_MODE_FILE.exists():
            data = json.loads(_ACTIVE_MODE_FILE.read_text(encoding="utf-8"))
            name = data.get("active_mode")
            if isinstance(name, str) and name.strip():
                return name.lower().strip()
    except Exception:
        pass
    return None


def _save_active_mode(name: str | None) -> None:
    try:
        _ACTIVE_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"active_mode": name.lower().strip() if name else None}
        _ACTIVE_MODE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass

# ── Active mode (persona) ─────────────────────────────────────────────────────
_active_mode: str | None = _load_active_mode()


def set_mode(name: str | None) -> None:
    global _active_mode
    _active_mode = name.lower().strip() if name else None
    _save_active_mode(_active_mode)


def get_mode() -> str | None:
    return _active_mode


# Backward-compatible aliases used throughout the rest of the codebase
def set_persona(name: str | None) -> None:
    set_mode(name)


def get_persona() -> str | None:
    return get_mode()


# ── Custom mode persistence ───────────────────────────────────────────────────
def _load_custom_modes() -> dict[str, str]:
    try:
        if _CUSTOM_MODES_FILE.exists():
            with open(_CUSTOM_MODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_custom_modes(modes: dict[str, str]) -> None:
    _CUSTOM_MODES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CUSTOM_MODES_FILE, "w", encoding="utf-8") as f:
        json.dump(modes, f, ensure_ascii=False, indent=2)


def save_custom_mode(name: str, prompt: str) -> None:
    modes = _load_custom_modes()
    modes[name.lower()] = prompt
    _save_custom_modes(modes)


def delete_custom_mode(name: str) -> bool:
    modes = _load_custom_modes()
    if name.lower() in modes:
        del modes[name.lower()]
        _save_custom_modes(modes)
        return True
    return False


def list_all_modes() -> dict[str, str]:
    """Return every available mode: legacy PERSONA_PROMPTS + EXTENDED_MODES + custom."""
    combined: dict[str, str] = {}
    combined.update(PERSONA_PROMPTS)
    combined.update(EXTENDED_MODES)
    combined.update(_load_custom_modes())
    return combined


def get_mode_prompt(name: str | None) -> str | None:
    """Return the system-prompt overlay string for a mode name."""
    if not name:
        return None
    return list_all_modes().get(name.lower())


# ── Conversation history ──────────────────────────────────────────────────────
class ConversationHistory:
    def __init__(self):
        self._messages: list[dict[str, Any]] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            path = os.path.abspath(_SESSION_FILE)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._messages = [
                        m for m in data
                        if isinstance(m, dict)
                        and m.get("role") in ("user", "assistant")
                        and isinstance(m.get("content"), str)
                    ]
                    self._trim()
        except Exception:
            self._messages = []

    def save(self) -> None:
        try:
            path = os.path.abspath(_SESSION_FILE)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            saveable = [
                m for m in self._messages
                if m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
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
        self.save()

    def add_tool_call(self, tool_calls: list[dict]) -> None:
        self._messages.append({"role": "assistant", "tool_calls": tool_calls})

    def add_tool_result(self, tool_call_id: str, name: str, result: str) -> None:
        self._messages.append({
            "role":         "tool",
            "tool_call_id": tool_call_id,
            "name":         name,
            "content":      result,
        })

    def get_messages(self, memory_context: str = "") -> list[dict]:
        system = SYSTEM_PROMPT
        # Apply active mode (covers both legacy personas and extended modes)
        mode_prompt = get_mode_prompt(_active_mode)
        if mode_prompt:
            system += f"\n\n{mode_prompt}"
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
