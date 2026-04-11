"""
File Organizer — Phase 5
/organize <directory> — auto-sort files into subfolders by type.
Supports dry-run preview, undo via a manifest, and custom rules.
"""
from __future__ import annotations
import os, json, shutil, datetime
from pathlib import Path

_MANIFEST_DIR = Path(__file__).parent.parent / "data" / "organizer_manifests"

# ── Extension → folder mapping ─────────────────────────────────────────────────
_RULES: dict[str, str] = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images",
    ".bmp": "Images", ".webp": "Images", ".svg": "Images", ".ico": "Images",
    ".tiff": "Images", ".tif": "Images", ".heic": "Images", ".raw": "Images",
    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".avi": "Videos", ".mov": "Videos",
    ".wmv": "Videos", ".flv": "Videos", ".webm": "Videos", ".m4v": "Videos",
    ".mpg": "Videos", ".mpeg": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".aac": "Audio",
    ".ogg": "Audio", ".m4a": "Audio", ".wma": "Audio",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".odt": "Documents", ".ods": "Documents",
    ".odp": "Documents", ".rtf": "Documents", ".pages": "Documents",
    ".numbers": "Documents", ".key": "Documents",
    # Text / Markdown / Config
    ".txt": "Text", ".md": "Text", ".rst": "Text", ".csv": "Text",
    ".json": "Text", ".xml": "Text", ".yaml": "Text", ".yml": "Text",
    ".toml": "Text", ".ini": "Text", ".cfg": "Text", ".conf": "Text",
    ".log": "Text", ".env": "Text",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".jsx": "Code",
    ".tsx": "Code", ".html": "Code", ".css": "Code", ".scss": "Code",
    ".java": "Code", ".c": "Code", ".cpp": "Code", ".h": "Code",
    ".cs": "Code", ".go": "Code", ".rs": "Code", ".rb": "Code",
    ".php": "Code", ".swift": "Code", ".kt": "Code", ".sh": "Code",
    ".bat": "Code", ".ps1": "Code", ".lua": "Code", ".r": "Code",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".tar": "Archives", ".gz": "Archives", ".bz2": "Archives",
    ".xz": "Archives", ".iso": "Archives",
    # Executables / Installers
    ".exe": "Programs", ".msi": "Programs", ".dmg": "Programs",
    ".deb": "Programs", ".rpm": "Programs", ".appimage": "Programs",
    # Fonts
    ".ttf": "Fonts", ".otf": "Fonts", ".woff": "Fonts", ".woff2": "Fonts",
    # 3D / Design
    ".psd": "Design", ".ai": "Design", ".xd": "Design", ".fig": "Design",
    ".sketch": "Design", ".blend": "Design", ".obj": "Design", ".fbx": "Design",
    # eBooks
    ".epub": "eBooks", ".mobi": "eBooks", ".azw": "eBooks", ".azw3": "eBooks",
    ".djvu": "eBooks",
    # Spreadsheets (extra)
    ".ods": "Documents",
    # Subtitles
    ".srt": "Subtitles", ".vtt": "Subtitles", ".ass": "Subtitles",
}

_MISC_FOLDER = "Misc"


def _get_folder(ext: str) -> str:
    return _RULES.get(ext.lower(), _MISC_FOLDER)


# ── Core organizer ────────────────────────────────────────────────────────────
def organize_directory(
    directory: str,
    dry_run:   bool = False,
    recursive: bool = False,
) -> dict:
    """
    Organize files in `directory` into subfolders by type.
    Returns {
        "moved": [(src, dst), ...],
        "skipped": [(path, reason), ...],
        "manifest_path": str | None,
        "dry_run": bool,
    }
    """
    root = Path(directory).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    moved:   list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    pattern = "**/*" if recursive else "*"
    for item in sorted(root.glob(pattern)):
        if not item.is_file():
            continue
        # Skip already-in-subfolder files (unless recursive)
        if not recursive and item.parent != root:
            continue
        # Skip hidden / system files
        if item.name.startswith("."):
            skipped.append((str(item), "hidden file"))
            continue
        # Skip manifest files we created
        if item.suffix == ".json" and item.stem.startswith("organize_manifest_"):
            skipped.append((str(item), "manifest file"))
            continue

        folder_name = _get_folder(item.suffix)
        target_dir  = root / folder_name
        target_path = target_dir / item.name

        # Handle name collision
        if target_path.exists():
            stem = item.stem
            suffix = item.suffix
            counter = 1
            while target_path.exists():
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        if dry_run:
            moved.append((str(item), str(target_path)))
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target_path))
            moved.append((str(item), str(target_path)))

    manifest_path: str | None = None
    if moved and not dry_run:
        manifest_path = _save_manifest(directory, moved)

    return {
        "moved":         moved,
        "skipped":       skipped,
        "manifest_path": manifest_path,
        "dry_run":       dry_run,
    }


# ── Undo ─────────────────────────────────────────────────────────────────────
def _save_manifest(directory: str, moves: list[tuple[str, str]]) -> str:
    _MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() else "_" for c in Path(directory).name)[:30]
    path = _MANIFEST_DIR / f"organize_manifest_{ts}_{safe}.json"
    data = {
        "directory": directory,
        "timestamp": ts,
        "moves": [{"src": s, "dst": d} for s, d in moves],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(path)


def list_manifests() -> list[Path]:
    if not _MANIFEST_DIR.exists():
        return []
    return sorted(_MANIFEST_DIR.glob("organize_manifest_*.json"), reverse=True)


def undo_organize(manifest_path: str | None = None) -> dict:
    """
    Undo the last (or specified) organize operation.
    Returns {"restored": int, "failed": int}.
    """
    if manifest_path:
        mpath = Path(manifest_path)
    else:
        manifests = list_manifests()
        if not manifests:
            return {"restored": 0, "failed": 0, "error": "No manifests found"}
        mpath = manifests[0]

    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception as e:
        return {"restored": 0, "failed": 0, "error": str(e)}

    restored = 0
    failed   = 0
    for move in reversed(data.get("moves", [])):
        src = move["src"]
        dst = move["dst"]
        try:
            dst_p = Path(dst)
            src_p = Path(src)
            if dst_p.exists():
                src_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst_p), str(src_p))
                restored += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    # Remove empty category folders
    try:
        base = Path(data.get("directory", ""))
        if base.is_dir():
            for d in base.iterdir():
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
    except Exception:
        pass

    mpath.unlink(missing_ok=True)
    return {"restored": restored, "failed": failed}


# ── Format helpers ────────────────────────────────────────────────────────────
def fmt_organize_result(result: dict) -> str:
    moved   = result["moved"]
    skipped = result["skipped"]
    dry     = result["dry_run"]
    mpath   = result.get("manifest_path")

    lines = []
    if dry:
        lines.append(f"  [DRY RUN] Would move {len(moved)} file(s):\n")
    else:
        lines.append(f"  Moved {len(moved)} file(s):\n")

    # Group by destination folder
    from collections import defaultdict
    by_folder: dict = defaultdict(list)
    for src, dst in moved:
        folder = Path(dst).parent.name
        by_folder[folder].append(Path(src).name)

    for folder, names in sorted(by_folder.items()):
        lines.append(f"    {folder}/  ({len(names)} file{'s' if len(names) != 1 else ''})")
        for name in names[:5]:
            lines.append(f"      • {name}")
        if len(names) > 5:
            lines.append(f"      … and {len(names) - 5} more")

    if skipped:
        lines.append(f"\n  Skipped {len(skipped)} item(s) (hidden/special files)")

    if mpath and not dry:
        lines.append(f"\n  Manifest saved — use /organize undo to reverse")

    return "\n".join(lines)
