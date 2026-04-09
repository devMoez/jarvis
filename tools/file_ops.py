import os
from pathlib import Path

DEFAULT_DIR = str(Path.home() / "Desktop")


def read_file(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"File not found: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        return content[:4000] + ("..." if len(content) > 4000 else "")
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str, mode: str = "write") -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        file_mode = "a" if mode == "append" else "w"
        with open(p, file_mode, encoding="utf-8") as f:
            f.write(content)
        return f"{'Appended to' if mode == 'append' else 'Written to'} {p}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory(path: str = DEFAULT_DIR) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Directory not found: {path}"
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = []
        for entry in entries[:50]:
            kind = "DIR " if entry.is_dir() else "FILE"
            lines.append(f"[{kind}] {entry.name}")
        if len(list(p.iterdir())) > 50:
            lines.append("... (more files not shown)")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


def send_notification(title: str, message: str) -> str:
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="Jarvis", timeout=5)
        return f"Notification sent: {title}"
    except Exception as e:
        return f"Notification failed: {e}"
