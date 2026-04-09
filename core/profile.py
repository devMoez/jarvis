"""
Persistent user profile — name, preferences, timezone, etc.
Stored in data/profile.json. Always injected into system prompt.
"""
import json
from pathlib import Path

PROFILE_FILE = Path("data/profile.json")

DEFAULTS = {
    "name": None,
    "timezone": None,
    "language": "English",
    "preferences": {},
}


def _load() -> dict:
    if not PROFILE_FILE.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data}
    except Exception:
        return dict(DEFAULTS)


def _save(profile: dict) -> None:
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def get_profile() -> dict:
    return _load()


def set_field(key: str, value: str) -> None:
    profile = _load()
    profile[key] = value
    _save(profile)


def set_preference(key: str, value: str) -> None:
    profile = _load()
    profile.setdefault("preferences", {})[key] = value
    _save(profile)


def clear_field(key: str) -> bool:
    profile = _load()
    if key in profile:
        profile[key] = None
        _save(profile)
        return True
    return False


def get_profile_prompt() -> str:
    """Return profile formatted for system prompt injection."""
    p = _load()
    lines = []
    if p.get("name"):
        lines.append(f"- User's name: {p['name']} (address them by name occasionally)")
    if p.get("timezone"):
        lines.append(f"- Timezone: {p['timezone']}")
    if p.get("language") and p["language"] != "English":
        lines.append(f"- Preferred language: {p['language']}")
    for k, v in p.get("preferences", {}).items():
        lines.append(f"- {k}: {v}")
    if not lines:
        return ""
    return "[User profile]\n" + "\n".join(lines)
