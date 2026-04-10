"""
Pattern tracker — watches what the user does repeatedly and surfaces skill suggestions.

Stores raw counts in data/patterns.json.
When a pattern hits the threshold, it's added to the suggestion queue so the
main loop can ask the user if they want to save it as a permanent skill.
"""
import json
import threading
from pathlib import Path

PATTERNS_FILE  = Path("data/patterns.json")
SUGGEST_THRESHOLD = 3      # occurrences before suggesting a skill
_lock = threading.Lock()

# In-memory queue of pending suggestions → shown after next Jarvis response
_suggestion_queue: list[str] = []


# ── Read / write ──────────────────────────────────────────────────────────────

def _load() -> dict:
    if not PATTERNS_FILE.exists():
        return {}
    try:
        return json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PATTERNS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────

def record(pattern_key: str, description: str) -> None:
    """
    Increment counter for a pattern.
    If it crosses the threshold for the first time, queue a skill suggestion.

    pattern_key  — stable string key (e.g. "prefers_short_answers")
    description  — human-readable text to suggest as a skill
    """
    with _lock:
        data = _load()
        entry = data.get(pattern_key, {"count": 0, "suggested": False, "description": description})
        entry["count"] += 1
        entry["description"] = description   # keep description fresh

        if entry["count"] >= SUGGEST_THRESHOLD and not entry["suggested"]:
            entry["suggested"] = True
            _suggestion_queue.append(description)

        data[pattern_key] = entry
        _save(data)


def pop_suggestions() -> list[str]:
    """Return and clear all pending suggestions."""
    with _lock:
        items = list(_suggestion_queue)
        _suggestion_queue.clear()
        return items


def reset_suggestion(pattern_key: str) -> None:
    """Re-enable suggesting for a pattern (user declined last time)."""
    with _lock:
        data = _load()
        if pattern_key in data:
            data[pattern_key]["suggested"] = False
            _save(data)


def all_patterns() -> dict:
    return _load()
