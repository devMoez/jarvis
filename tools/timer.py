"""Timer and reminder system."""
import threading, time, re


def _parse_duration(text: str) -> int | None:
    """Parse '5m', '30s', '2h', '1h30m' etc. → seconds. Returns None on failure."""
    text = text.strip().lower()
    total = 0
    for val, unit in re.findall(r'(\d+)\s*([smh])', text):
        v = int(val)
        if unit == 's': total += v
        elif unit == 'm': total += v * 60
        elif unit == 'h': total += v * 3600
    return total if total else None


def start_timer(duration_str: str, label: str, on_done) -> tuple[bool, str]:
    """
    Start a countdown timer. Calls on_done(label) when done.
    Returns (ok, message).
    """
    secs = _parse_duration(duration_str)
    if secs is None:
        return False, f"Can't parse duration: '{duration_str}'. Use formats like 5m, 30s, 1h, 1h30m."

    def _run():
        time.sleep(secs)
        on_done(label)

    t = threading.Thread(target=_run, daemon=True, name=f"Timer:{label[:20]}")
    t.start()

    # Human-readable duration
    parts = []
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return True, " ".join(parts)
