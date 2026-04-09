import subprocess
import shutil
import os
from pathlib import Path


def run_command(command: str, background: bool = False) -> str:
    """Run any shell command. Returns output or confirms background launch."""
    try:
        if background:
            subprocess.Popen(command, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            return f"Running in background: {command}"
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        return output[:2000]
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Command failed: {e}"


def move_file(source: str, destination: str) -> str:
    """Move or rename a file or folder."""
    try:
        src = Path(source).expanduser()
        dst = Path(destination).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Moved {src} to {dst}"
    except Exception as e:
        return f"Move failed: {e}"


def copy_file(source: str, destination: str) -> str:
    """Copy a file or folder."""
    try:
        src = Path(source).expanduser()
        dst = Path(destination).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return f"Copied {src} to {dst}"
    except Exception as e:
        return f"Copy failed: {e}"


def delete_file(path: str) -> str:
    """Delete a file or folder. Asks for confirmation via return value."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Not found: {path}"
        if p.is_dir():
            shutil.rmtree(str(p))
        else:
            p.unlink()
        return f"Deleted: {p}"
    except Exception as e:
        return f"Delete failed: {e}"


def system_power(action: str) -> str:
    """Control system power: shutdown, restart, hibernate, lock, sleep."""
    action = action.lower().strip()
    commands = {
        "shutdown":  "shutdown /s /t 10 /c \"Shutting down as requested, sir.\"",
        "restart":   "shutdown /r /t 10 /c \"Restarting as requested, sir.\"",
        "hibernate": "shutdown /h",
        "sleep":     "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "lock":      "rundll32.exe user32.dll,LockWorkStation",
        "cancel":    "shutdown /a",
    }
    if action not in commands:
        return f"Unknown action '{action}'. Choose from: {', '.join(commands)}"
    try:
        subprocess.run(commands[action], shell=True)
        return f"System {action} initiated, sir."
    except Exception as e:
        return f"Power action failed: {e}"


def install_software(package: str, manager: str = "winget") -> str:
    """Install software using winget or pip."""
    if manager == "winget":
        cmd = f"winget install --accept-source-agreements --accept-package-agreements \"{package}\""
    elif manager == "pip":
        cmd = f"pip install {package}"
    elif manager == "choco":
        cmd = f"choco install {package} -y"
    else:
        return f"Unknown package manager: {manager}"
    return run_command(cmd)


def search_files(name_pattern: str, search_dir: str = "C:\\Users") -> str:
    """Search for files matching a pattern."""
    try:
        result = subprocess.run(
            f"dir /s /b \"{search_dir}\\{name_pattern}\"",
            shell=True, capture_output=True, text=True,
            timeout=15, encoding="utf-8", errors="replace"
        )
        lines = result.stdout.strip().splitlines()
        if not lines:
            return f"No files found matching '{name_pattern}'"
        return "\n".join(lines[:20]) + (f"\n...and {len(lines)-20} more" if len(lines) > 20 else "")
    except Exception as e:
        return f"Search failed: {e}"
