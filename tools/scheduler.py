"""
Scheduler — Phase 5
Cron-style recurring tasks + one-shot future tasks.
Stored in data/schedule.json.
Commands: /schedule add, /schedule list, /schedule remove, /schedule clear
"""
from __future__ import annotations
import json, threading, datetime, time
from pathlib import Path
from typing import Callable

_SCHEDULE_FILE = Path(__file__).parent.parent / "data" / "schedule.json"
_LOCK = threading.Lock()

# ── Data model ────────────────────────────────────────────────────────────────
# Each entry:
# {
#   "id":       int,
#   "label":    str,        # human name
#   "type":     "once" | "cron",
#   "when":     ISO str (for once) | cron-expression str (for cron),
#   "action":   str,        # text message to inject into Jarvis queue
#   "enabled":  bool,
#   "last_run": ISO str | null,
#   "next_run": ISO str | null,
# }

# Supported cron-like patterns (simplified):
#   "every 5m"    every 5 minutes
#   "every 1h"    every 1 hour
#   "every 1d"    every 1 day
#   "daily HH:MM" every day at HH:MM
#   "hourly"      top of every hour


def _load() -> list[dict]:
    if _SCHEDULE_FILE.exists():
        try:
            return json.loads(_SCHEDULE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(entries: list[dict]) -> None:
    _SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SCHEDULE_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _next_id(entries: list[dict]) -> int:
    return max((e["id"] for e in entries), default=0) + 1


# ── Parse "when" string into next datetime ───────────────────────────────────
def _parse_interval_seconds(expr: str) -> int | None:
    """Parse 'every Xm', 'every Xh', 'every Xd'. Returns seconds or None."""
    expr = expr.strip().lower()
    if expr.startswith("every "):
        rest = expr[6:].strip()
        try:
            if rest.endswith("m"):
                return int(rest[:-1]) * 60
            if rest.endswith("h"):
                return int(rest[:-1]) * 3600
            if rest.endswith("d"):
                return int(rest[:-1]) * 86400
        except ValueError:
            pass
    if expr == "hourly":
        return 3600
    return None


def _compute_next(entry: dict) -> datetime.datetime | None:
    now = datetime.datetime.now()
    if entry["type"] == "once":
        try:
            dt = datetime.datetime.fromisoformat(entry["when"])
            return dt if dt > now else None
        except Exception:
            return None
    # cron-style
    when = entry["when"].lower().strip()
    secs = _parse_interval_seconds(when)
    if secs:
        last = entry.get("last_run")
        if last:
            try:
                base = datetime.datetime.fromisoformat(last)
                candidate = base + datetime.timedelta(seconds=secs)
                while candidate <= now:
                    candidate += datetime.timedelta(seconds=secs)
                return candidate
            except Exception:
                pass
        return now + datetime.timedelta(seconds=secs)
    # "daily HH:MM"
    if when.startswith("daily "):
        time_str = when[6:].strip()
        try:
            t = datetime.datetime.strptime(time_str, "%H:%M").time()
            candidate = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += datetime.timedelta(days=1)
            return candidate
        except Exception:
            pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────
def add_schedule(
    label:   str,
    when:    str,
    action:  str,
    once:    bool = False,
) -> dict:
    """
    Add a scheduled task.
    when:   ISO datetime string (for once=True) or cron expression (once=False)
            e.g. "2025-12-31 08:00", "every 30m", "daily 09:00", "hourly"
    action: text to inject into Jarvis queue when triggered
    """
    with _LOCK:
        entries = _load()
        task_type = "once" if once else "cron"
        entry: dict = {
            "id":       _next_id(entries),
            "label":    label,
            "type":     task_type,
            "when":     when,
            "action":   action,
            "enabled":  True,
            "last_run": None,
            "next_run": None,
        }
        nr = _compute_next(entry)
        entry["next_run"] = nr.isoformat() if nr else None
        entries.append(entry)
        _save(entries)
    return entry


def list_schedules() -> list[dict]:
    with _LOCK:
        return _load()


def remove_schedule(id_: int) -> bool:
    with _LOCK:
        entries = _load()
        before = len(entries)
        entries = [e for e in entries if e["id"] != id_]
        _save(entries)
        return len(entries) < before


def clear_schedules() -> int:
    with _LOCK:
        entries = _load()
        count = len(entries)
        _save([])
        return count


def toggle_schedule(id_: int, enabled: bool) -> bool:
    with _LOCK:
        entries = _load()
        for e in entries:
            if e["id"] == id_:
                e["enabled"] = enabled
                _save(entries)
                return True
        return False


# ── Background scheduler loop ─────────────────────────────────────────────────
_scheduler_started = False

def start_scheduler(on_trigger: Callable[[str, str], None]) -> None:
    """
    Start background scheduler thread.
    on_trigger(label, action) called when a task fires.
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def _loop():
        while True:
            now = datetime.datetime.now()
            with _LOCK:
                entries = _load()
                changed = False
                for entry in entries:
                    if not entry.get("enabled", True):
                        continue
                    nr = entry.get("next_run")
                    if not nr:
                        continue
                    try:
                        fire_at = datetime.datetime.fromisoformat(nr)
                    except Exception:
                        continue
                    if fire_at <= now:
                        # Fire!
                        try:
                            on_trigger(entry["label"], entry["action"])
                        except Exception:
                            pass
                        entry["last_run"] = now.isoformat()
                        if entry["type"] == "once":
                            entry["enabled"] = False
                            entry["next_run"] = None
                        else:
                            new_next = _compute_next(entry)
                            entry["next_run"] = new_next.isoformat() if new_next else None
                        changed = True
                if changed:
                    _save(entries)
            time.sleep(15)

    t = threading.Thread(target=_loop, daemon=True, name="jarvis-scheduler")
    t.start()


# ── Format helpers ────────────────────────────────────────────────────────────
def fmt_schedule_list(entries: list[dict]) -> str:
    if not entries:
        return "No scheduled tasks."
    lines = []
    for e in entries:
        status = "✓" if e.get("enabled") else "✗"
        nr = e.get("next_run", "—")
        if nr and nr != "—":
            try:
                dt = datetime.datetime.fromisoformat(nr)
                nr = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        lines.append(
            f"  [{e['id']}] {status}  {e['label']}"
            f"  |  {e['type'].upper()}  {e['when']}"
            f"  |  next: {nr or '—'}"
            f"\n      action: {e['action'][:60]}{'…' if len(e['action']) > 60 else ''}"
        )
    return "\n".join(lines)
