"""Append-only error log — data/logs/errors.log"""
import datetime
from pathlib import Path

_LOG = Path(__file__).parent.parent / "data" / "logs" / "errors.log"


def log_error(source: str, error: str) -> None:
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{source}] {error}\n")
