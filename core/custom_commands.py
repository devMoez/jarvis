"""
User-defined slash commands.
Stored in data/custom_commands.json.

Each command:
  name    — the /command trigger (without slash, lowercase)
  prompt  — the message sent to Jarvis when this command is run
  desc    — short description shown in /help

Example:
  /cmd add morning  "What's the weather and what's on my schedule today?"
  → typing /morning sends that full prompt to Jarvis
"""
import json
from pathlib import Path

COMMANDS_FILE = Path("data/custom_commands.json")


def _load() -> list[dict]:
    if not COMMANDS_FILE.exists():
        return []
    try:
        return json.loads(COMMANDS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(cmds: list[dict]) -> None:
    COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMMANDS_FILE.write_text(json.dumps(cmds, indent=2), encoding="utf-8")


def list_commands() -> list[dict]:
    return _load()


def add_command(name: str, prompt: str, desc: str = "") -> tuple[bool, str]:
    """Add a custom command. Returns (success, message)."""
    name = name.lower().strip().lstrip("/")
    if not name.isidentifier():
        return False, "Command name must be a single word (letters, numbers, underscores)."
    cmds = _load()
    if any(c["name"] == name for c in cmds):
        return False, f"/{name} already exists. Remove it first with /cmd remove {name}."
    cmds.append({"name": name, "prompt": prompt.strip(), "desc": desc.strip() or prompt[:60]})
    _save(cmds)
    return True, f"/{name} created."


def remove_command(name: str) -> bool:
    name = name.lower().strip().lstrip("/")
    cmds = _load()
    new = [c for c in cmds if c["name"] != name]
    if len(new) == len(cmds):
        return False
    _save(new)
    return True


def get_command(name: str) -> dict | None:
    name = name.lower().strip().lstrip("/")
    return next((c for c in _load() if c["name"] == name), None)
