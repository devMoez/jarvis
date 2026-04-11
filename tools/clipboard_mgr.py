"""Clipboard manager — tracks last 20 entries, /clips and /clip <n>."""
import threading

_history: list[str] = []
_lock = threading.Lock()
_MAX = 20


def _snapshot() -> None:
    """Grab current clipboard content and add to history if new."""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text or not text.strip():
            return
        with _lock:
            if not _history or _history[-1] != text:
                _history.append(text)
                if len(_history) > _MAX:
                    _history.pop(0)
    except Exception:
        pass


def start_tracking(interval: float = 1.5) -> None:
    """Start background thread that polls clipboard every `interval` seconds."""
    import time, threading

    def _loop():
        while True:
            _snapshot()
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True, name="ClipboardTracker")
    t.start()


def get_history() -> list[str]:
    with _lock:
        return list(_history)


def paste_item(n: int) -> str:
    """Copy item n (1-based) back to clipboard. Returns the text or error."""
    with _lock:
        items = list(_history)
    if not items:
        return "Clipboard history is empty."
    if n < 1 or n > len(items):
        return f"No item {n}. History has {len(items)} entries."
    try:
        import pyperclip
        pyperclip.copy(items[n - 1])
        return items[n - 1]
    except Exception as e:
        return f"Clipboard error: {e}"


def clear_history() -> int:
    with _lock:
        n = len(_history)
        _history.clear()
    return n
