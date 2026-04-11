"""
Task memory — saves every user query + Jarvis response to data/task_memory.json.
Provides the last N interactions as plain-text context for the LLM.
Separate from ChromaDB long-term memory: this is a simple, ordered log.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

_FILE   = Path("data/task_memory.json")
_LOCK   = threading.Lock()
_MAX    = 200   # cap stored entries to keep file small


class TaskMemory:
    """Thread-safe append-only task log with bounded size."""

    # ── Read / write ──────────────────────────────────────────────────────────
    @staticmethod
    def _load() -> list[dict]:
        try:
            if _FILE.exists():
                return json.loads(_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    @staticmethod
    def _save(entries: list[dict]) -> None:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Public API ─────────────────────────────────────────────────────────────
    def save(self, query: str, result: str) -> None:
        """Append a task entry. Trims to _MAX entries automatically."""
        entry = {
            "ts":     datetime.now().isoformat(timespec="seconds"),
            "query":  query.strip()[:500],          # cap length
            "result": result.strip()[:2000],
        }
        with _LOCK:
            entries = self._load()
            entries.append(entry)
            if len(entries) > _MAX:
                entries = entries[-_MAX:]
            self._save(entries)

    def get_context(self, n: int = 10) -> str:
        """Return last n tasks formatted as plain-text context."""
        entries = self._load()
        recent = entries[-n:] if len(entries) >= n else entries
        if not recent:
            return ""
        lines = ["[Recent task history]"]
        for e in recent:
            lines.append(f"[{e['ts']}] User: {e['query']}")
            lines.append(f"           Jarvis: {e['result'][:200]}...")
        return "\n".join(lines)

    def show(self, n: int = 20) -> str:
        """Return last n tasks as a display string."""
        entries = self._load()
        if not entries:
            return "No tasks saved yet."
        recent = entries[-n:]
        lines = [f"  Last {len(recent)} task(s):"]
        for i, e in enumerate(reversed(recent), 1):
            lines.append(f"\n  {i}. [{e['ts']}]")
            lines.append(f"     Q: {e['query'][:80]}")
            lines.append(f"     A: {e['result'][:120]}...")
        return "\n".join(lines)

    def clear(self) -> int:
        """Delete all task history. Returns number of entries removed."""
        with _LOCK:
            entries = self._load()
            n = len(entries)
            self._save([])
        return n

    def count(self) -> int:
        return len(self._load())


# ── Module-level singleton ────────────────────────────────────────────────────
task_memory = TaskMemory()
