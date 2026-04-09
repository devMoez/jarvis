import datetime
import pyperclip
import psutil


def get_system_info(info_type: str = "all") -> str:
    """Return requested system info."""
    results = {}

    if info_type in ("time", "all"):
        results["time"] = datetime.datetime.now().strftime("%I:%M %p")

    if info_type in ("date", "all"):
        results["date"] = datetime.datetime.now().strftime("%A, %B %d, %Y")

    if info_type in ("battery", "all"):
        battery = psutil.sensors_battery()
        if battery:
            status = "charging" if battery.power_plugged else "discharging"
            results["battery"] = f"{battery.percent:.0f}% ({status})"
        else:
            results["battery"] = "No battery detected (desktop?)"

    if info_type in ("clipboard", "all"):
        try:
            clip = pyperclip.paste()
            results["clipboard"] = clip[:500] if clip else "(empty)"
        except Exception:
            results["clipboard"] = "Clipboard unavailable"

    if len(results) == 1:
        return list(results.values())[0]

    return "\n".join(f"{k}: {v}" for k, v in results.items())
