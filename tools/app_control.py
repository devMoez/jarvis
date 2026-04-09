import subprocess
import psutil

# Common app name → executable mapping on Windows
APP_MAP = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "vscode": "code.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "task manager": "taskmgr.exe",
}


def open_app(app_name: str) -> str:
    """Open an application by name."""
    name_lower = app_name.lower().strip()
    exe = APP_MAP.get(name_lower, None)

    try:
        if exe:
            subprocess.Popen(exe, shell=True)
        else:
            # Try the name directly as a shell command
            subprocess.Popen(app_name, shell=True)
        return f"Opening {app_name}."
    except Exception as e:
        return f"Couldn't open {app_name}: {e}"


def list_running_apps() -> str:
    """List currently running applications."""
    apps = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and name.endswith(".exe"):
                apps.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return ", ".join(sorted(apps))


def close_app(app_name: str) -> str:
    """Close a running application by name."""
    name_lower = app_name.lower()
    killed = []
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if name_lower in proc.info["name"].lower():
                proc.kill()
                killed.append(proc.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        return f"Closed: {', '.join(killed)}"
    return f"No process found matching '{app_name}'."
