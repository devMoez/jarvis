"""Token usage + request tracking — data/stats.json"""
import json, datetime
from pathlib import Path

_FILE = Path(__file__).parent.parent / "data" / "stats.json"


def _load() -> dict:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tokens": {}, "requests": {}}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record(prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    today = datetime.date.today().isoformat()
    data  = _load()
    t = data["tokens"].setdefault(today, {"prompt": 0, "completion": 0})
    t["prompt"]     += prompt_tokens
    t["completion"] += completion_tokens
    data["requests"][today] = data["requests"].get(today, 0) + 1
    _save(data)


def get_today() -> dict:
    today = datetime.date.today().isoformat()
    data  = _load()
    t = data["tokens"].get(today, {"prompt": 0, "completion": 0})
    return {
        "date":        today,
        "prompt":      t["prompt"],
        "completion":  t["completion"],
        "total":       t["prompt"] + t["completion"],
        "requests":    data["requests"].get(today, 0),
    }


def get_all() -> dict:
    return _load()
