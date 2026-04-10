"""
Jarvis AI — Main Entry Point
Default: text mode.  Voice input: /voice.  Help: /help
"""
import os, sys, threading, time, io

# ── UTF-8 + silence warnings ─────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

import warnings; warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

sys.stderr = io.TextIOWrapper(open(os.devnull, "wb"), encoding="utf-8")

# ── Enable ANSI colors on Windows terminal ────────────────────────────────────
import colorama
colorama.init(autoreset=False)

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.rule import Rule

from version import VERSION, API_PROVIDER, AUTHOR

console = Console(force_terminal=True, color_system="256", highlight=False)

if not os.getenv("OPENROUTER_API_KEY"):
    console.print("[red]  ERROR: OPENROUTER_API_KEY not set in .env[/]")
    sys.exit(1)

# ── Imports ───────────────────────────────────────────────────────────────────
from core.orchestrator import Orchestrator, TOOL_EVENT_PREFIX
from core.tool_registry import ToolRegistry
from audio.recorder import record_until_silence
from audio.stt import transcribe
from audio.tts import speak
from audio.wake_word import start_listening, stop_listening
from memory.long_term import retrieve, remember
from memory.extractor import extract_and_store_async
from core.skills import list_skills, add_skill, remove_skill, clear_skills
from core.profile import get_profile, set_field, set_preference, clear_field
from tools.search import search_web
from tools.browser import open_url, scrape_page
from tools.app_control import open_app
from tools.system_info import get_system_info
from tools.file_ops import read_file, write_file, list_directory, send_notification
from tools.os_control import (run_command, move_file, copy_file, delete_file,
                               system_power, install_software, search_files)
from telegram_bridge import TelegramBridge

_telegram = TelegramBridge()

# ── ANSI color palette ────────────────────────────────────────────────────────
AMBER    = "\033[38;5;214m"   # Iron Man gold — Jarvis responses & label
GOLD     = "\033[33m"         # dimmer gold — accents, borders, hints
USER_CLR = "\033[92m"         # bright green — user › symbol
WHITE    = "\033[97m"         # body text
DIM      = "\033[2m"
BOLD     = "\033[1m"
RED      = "\033[91m"
GREEN    = "\033[92m"
YELLOW   = "\033[93m"
MAGENTA  = "\033[95m"
RESET    = "\033[0m"

BAR = f"{GOLD}{'─' * 56}{RESET}"   # horizontal rule

# ── Tool label map ────────────────────────────────────────────────────────────
TOOL_LABELS = {
    "search_web":        ("SEARCH",  "yellow"),
    "scrape_page":       ("FETCH",   "dark_orange"),
    "open_url":          ("OPEN",    "yellow"),
    "open_app":          ("LAUNCH",  "yellow"),
    "run_command":       ("RUN",     "bright_yellow"),
    "read_file":         ("READ",    "white"),
    "write_file":        ("WRITE",   "green"),
    "delete_file":       ("DELETE",  "red"),
    "move_file":         ("MOVE",    "magenta"),
    "copy_file":         ("COPY",    "magenta"),
    "list_directory":    ("LIST",    "white"),
    "search_files":      ("FILES",   "yellow"),
    "get_system_info":   ("SYSTEM",  "yellow"),
    "remember":          ("MEMORY",  "dark_orange"),
    "send_notification": ("NOTIFY",  "bright_yellow"),
    "install_software":  ("INSTALL", "green"),
    "system_power":      ("POWER",   "bright_red"),
}

TOOL_ANSI = {
    "search_web":        AMBER,
    "scrape_page":       GOLD,
    "open_url":          GOLD,
    "open_app":          GOLD,
    "run_command":       YELLOW,
    "read_file":         WHITE,
    "write_file":        GREEN,
    "delete_file":       RED,
    "move_file":         MAGENTA,
    "copy_file":         MAGENTA,
    "list_directory":    WHITE,
    "search_files":      AMBER,
    "get_system_info":   GOLD,
    "remember":          AMBER,
    "send_notification": YELLOW,
    "install_software":  GREEN,
    "system_power":      RED,
}

# ── Register tools ────────────────────────────────────────────────────────────
registry = ToolRegistry()
registry.register("search_web",        search_web)
registry.register("open_url",          open_url)
registry.register("scrape_page",       scrape_page)
registry.register("open_app",          open_app)
registry.register("get_system_info",   get_system_info)
registry.register("read_file",         read_file)
registry.register("write_file",        write_file)
registry.register("list_directory",    list_directory)
registry.register("remember",          remember)
registry.register("send_notification", send_notification)
registry.register("run_command",       run_command)
registry.register("move_file",         move_file)
registry.register("copy_file",         copy_file)
registry.register("delete_file",       delete_file)
registry.register("system_power",      system_power)
registry.register("install_software",  install_software)
registry.register("search_files",      search_files)

orchestrator = Orchestrator(tool_registry=registry)

# Pre-warm ChromaDB in background
threading.Thread(target=lambda: retrieve("warmup"), daemon=True).start()

# ── State ─────────────────────────────────────────────────────────────────────
_running   = True
_activated = threading.Event()
_mode      = "text"

# ── Raw stdout helpers ────────────────────────────────────────────────────────
def sanitize(t: str) -> str:
    return t.encode("utf-8", errors="replace").decode("utf-8")

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def _raw(text: str, end: str = "") -> None:
    sys.stdout.write(text + end)
    sys.stdout.flush()

def _clear_line() -> None:
    sys.stdout.write("\r" + " " * 70 + "\r")
    sys.stdout.flush()

# ── ASCII art logo ────────────────────────────────────────────────────────────
JARVIS_LOGO = [
    r"     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗",
    r"     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝",
    r"     ██║███████║██████╔╝██║   ██║██║███████╗",
    r"██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║",
    r"╚████╔╝ ██║  ██║██║  ██║ ╚████╔╝ ██║███████║",
    r" ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝",
]

def print_banner():
    cls()
    _raw("\n")
    for line in JARVIS_LOGO:
        _raw(f"  {AMBER}{BOLD}{line}{RESET}\n")
    _raw("\n")
    _raw(f"  {BAR}\n")
    _raw(f"  {DIM}  v{VERSION}  ·  {API_PROVIDER}  ·  Built by {AUTHOR}{RESET}\n")
    _raw(f"  {DIM}  AI Personal Assistant — Iron Man Edition{RESET}\n")
    _raw(f"  {BAR}\n\n")

# ── Styled input with borders ─────────────────────────────────────────────────
try:
    from prompt_toolkit import prompt as _pt_prompt
    from prompt_toolkit.styles import Style as _PtStyle

    _PT_STYLE = _PtStyle.from_dict({
        "prompt": "#ffaf00 bold",   # amber › and border
        "":       "#ffffff",        # white input text (highlighted)
    })
    _USE_PT = True
except ImportError:
    _USE_PT = False

def _read_input() -> str:
    """Show top border, styled › prompt, bottom border after enter."""
    border = f"  {GOLD}{'─' * 56}{RESET}"
    _raw(f"\n{border}\n")
    if _USE_PT:
        try:
            result = _pt_prompt(
                [("class:prompt", "  › ")],
                style=_PT_STYLE,
            )
            _raw(f"{border}\n")
            return result
        except (EOFError, KeyboardInterrupt):
            raise
    else:
        _raw(f"  {AMBER}›{RESET} ")
        result = input()
        _raw(f"{border}\n")
        return result

# ── /help ─────────────────────────────────────────────────────────────────────
def cmd_help():
    console.print()
    console.print(Panel(
        Text.assemble(("  JARVIS — HELP", "bold yellow")),
        border_style="yellow", box=box.SIMPLE, expand=False
    ))
    console.print()
    console.print("  [bold white]Getting Started[/]")
    console.print(f"  {GOLD}{'─' * 45}{RESET}")
    console.print("  [white]Run[/]  [yellow]python main.py[/]        [dim]→ text mode (default)[/]")
    console.print("  [white]Run[/]  [yellow]python main.py --voice[/] [dim]→ wake word voice mode[/]")
    console.print()
    console.print("  [bold white]Slash Commands[/]")
    console.print(f"  {GOLD}{'─' * 45}{RESET}")
    groups = {
        "Navigation": [
            ("/help",                "Show this screen"),
            ("/commands",            "List all capabilities"),
            ("/clear",               "Clear the terminal"),
            ("/mode",                "Show current mode + version"),
            ("/quit",                "Exit Jarvis"),
        ],
        "Input Mode": [
            ("/voice",               "Switch to voice input"),
            ("/text",                "Switch to text input (default)"),
        ],
        "Memory": [
            ("/memory",              "List all long-term memories"),
            ("/memory add <fact>",   "Add a memory manually"),
            ("/memory remove <n>",   "Remove memory by number"),
            ("/memory clear",        "Wipe all memories"),
        ],
        "Skills": [
            ("/skill",               "List persistent behaviors"),
            ("/skill add <text>",    "Add a permanent behavior Jarvis always follows"),
            ("/skill remove <id>",   "Remove a skill"),
            ("/skill clear",         "Remove all skills"),
        ],
        "Profile": [
            ("/profile",             "Show your profile"),
            ("/profile set name X",  "Set your name"),
            ("/profile set timezone X", "Set your timezone"),
            ("/profile pref <k> <v>","Set a preference"),
        ],
    }
    for group, rows in groups.items():
        console.print(f"\n  [bold white]{group}[/]")
        for cmd, desc in rows:
            console.print(f"  [bold yellow]  {cmd:<28}[/] [dim]{desc}[/]")
    console.print()
    console.print("  [bold white]Usage Tips[/]")
    console.print(f"  {GOLD}{'─' * 45}{RESET}")
    console.print("  [dim]Just type naturally — Jarvis understands plain English.[/]")
    console.print("  [dim]Examples:[/]")
    console.print("  [dim]  › search for latest AI news[/]")
    console.print("  [dim]  › open Spotify[/]")
    console.print("  [dim]  › install vlc[/]")
    console.print("  [dim]  › what time is it[/]")
    console.print("  [dim]  › remember my name is Alex[/]")
    console.print("  [dim]  › run ipconfig[/]")
    console.print("  [dim]  › shutdown the computer[/]")
    console.print()

# ── /commands ─────────────────────────────────────────────────────────────────
def cmd_commands():
    console.print()
    console.print(Panel(
        Text.assemble(("  JARVIS — CAPABILITIES", "bold yellow")),
        border_style="yellow", box=box.SIMPLE, expand=False
    ))
    console.print()
    categories = {
        "Web & Search": [
            ("SEARCH",  "yellow",       "Search the web (DuckDuckGo)"),
            ("FETCH",   "dark_orange",  "Read content from any webpage"),
            ("OPEN",    "yellow",       "Open any URL in browser"),
        ],
        "Apps & System": [
            ("LAUNCH",  "yellow",       "Open applications by name"),
            ("RUN",     "bright_yellow","Execute any shell / terminal command"),
            ("SYSTEM",  "yellow",       "Get time, date, battery, clipboard"),
            ("POWER",   "bright_red",   "Shutdown / restart / hibernate / sleep / lock"),
        ],
        "Files": [
            ("READ",    "white",        "Read file contents"),
            ("WRITE",   "green",        "Create or edit files"),
            ("MOVE",    "magenta",      "Move or rename files and folders"),
            ("COPY",    "magenta",      "Copy files and folders"),
            ("DELETE",  "red",          "Delete files and folders"),
            ("LIST",    "white",        "List directory contents"),
            ("FILES",   "yellow",       "Search files by name pattern"),
        ],
        "Software": [
            ("INSTALL", "green",        "Install software via winget / pip / choco"),
        ],
        "Memory": [
            ("MEMORY",  "dark_orange",  "Store facts in long-term memory"),
        ],
        "Notifications": [
            ("NOTIFY",  "bright_yellow","Send Windows desktop notifications"),
        ],
    }
    for cat, tools in categories.items():
        console.print(f"  [bold white]{cat}[/]")
        for label, color, desc in tools:
            console.print(f"   [{color}][{label}][/{color}]  [dim]{desc}[/]")
        console.print()

# ── /memory ───────────────────────────────────────────────────────────────────
def cmd_memory(args: list[str] = []):
    from memory.long_term import _get_collection, store

    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) > 1:
        fact = " ".join(args[1:])
        store(fact)
        console.print(f"\n  [dark_orange][MEMORY][/] Saved: [white]{sanitize(fact)}[/]\n")
        return

    if sub == "remove" and len(args) > 1:
        try:
            idx = int(args[1]) - 1
            col = _get_collection()
            results = col.get()
            ids = results.get("ids", [])
            if 0 <= idx < len(ids):
                col.delete(ids=[ids[idx]])
                console.print(f"\n  [dark_orange][MEMORY][/] Removed entry {idx + 1}.\n")
            else:
                console.print(f"  [red]  No memory at index {idx + 1}[/]")
        except ValueError:
            console.print("  [red]  Usage: /memory remove <number>[/]")
        return

    if sub == "clear":
        col = _get_collection()
        col.delete(where={"$exists": True}) if col.count() > 0 else None
        console.print("\n  [dark_orange][MEMORY][/] All memories cleared.\n")
        return

    try:
        col = _get_collection()
        count = col.count()
        if count == 0:
            console.print("\n  [dim]  No memories stored yet.[/]\n")
            return
        results = col.get()
        docs = results.get("documents", [])
        console.print()
        console.print(f"  [bold dark_orange]  Memories  ({count})[/]")
        console.print(f"  {GOLD}{'─' * 45}{RESET}")
        for i, doc in enumerate(docs[:30], 1):
            console.print(f"  [dark_orange]{i:>2}.[/] [white]{sanitize(doc)}[/]")
        if count > 30:
            console.print(f"  [dim]  ... and {count - 30} more[/]")
        console.print()
        console.print("  [dim]  /memory add <fact>  |  /memory remove <n>  |  /memory clear[/]\n")
    except Exception as e:
        console.print(f"  [red]  Could not load memories: {e}[/]")

# ── /skill ────────────────────────────────────────────────────────────────────
def cmd_skill(args: list[str] = []):
    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) > 1:
        instruction = " ".join(args[1:])
        skill = add_skill(instruction)
        console.print(f"\n  [green][SKILL][/] Added #{skill['id']}: [white]{sanitize(instruction)}[/]\n")
        return

    if sub == "remove" and len(args) > 1:
        try:
            sid = int(args[1])
            if remove_skill(sid):
                console.print(f"\n  [green][SKILL][/] Removed skill #{sid}.\n")
            else:
                console.print(f"  [red]  Skill #{sid} not found.[/]")
        except ValueError:
            console.print("  [red]  Usage: /skill remove <id>[/]")
        return

    if sub == "clear":
        n = clear_skills()
        console.print(f"\n  [green][SKILL][/] Cleared {n} skill(s).\n")
        return

    skills = list_skills()
    console.print()
    console.print(f"  [bold green]  Skills  ({len(skills)})[/]")
    console.print(f"  {GOLD}{'─' * 45}{RESET}")
    if not skills:
        console.print("  [dim]  No skills set yet.[/]")
        console.print("  [dim]  Example: /skill add always reply in bullet points[/]")
    else:
        for s in skills:
            console.print(f"  [green]{s['id']:>2}.[/] [white]{sanitize(s['instruction'])}[/]")
    console.print()
    console.print("  [dim]  /skill add <instruction>  |  /skill remove <id>  |  /skill clear[/]\n")

# ── /profile ──────────────────────────────────────────────────────────────────
def cmd_profile(args: list[str] = []):
    sub = args[0].lower() if args else "show"

    if sub == "set" and len(args) >= 3:
        key = args[1].lower()
        value = " ".join(args[2:])
        set_field(key, value)
        console.print(f"\n  [yellow][PROFILE][/] Set {key} = [white]{sanitize(value)}[/]\n")
        return

    if sub == "pref" and len(args) >= 3:
        key = args[1]
        value = " ".join(args[2:])
        set_preference(key, value)
        console.print(f"\n  [yellow][PROFILE][/] Preference set: {key} = [white]{sanitize(value)}[/]\n")
        return

    if sub == "clear" and len(args) >= 2:
        key = args[1].lower()
        if clear_field(key):
            console.print(f"\n  [yellow][PROFILE][/] Cleared {key}.\n")
        else:
            console.print(f"  [red]  Field '{key}' not found.[/]")
        return

    p = get_profile()
    console.print()
    console.print("  [bold yellow]  Profile[/]")
    console.print(f"  {GOLD}{'─' * 45}{RESET}")
    console.print(f"  [yellow]Name[/]      [white]{p.get('name') or '(not set)'}[/]")
    console.print(f"  [yellow]Timezone[/]  [white]{p.get('timezone') or '(not set)'}[/]")
    console.print(f"  [yellow]Language[/]  [white]{p.get('language', 'English')}[/]")
    prefs = p.get("preferences", {})
    if prefs:
        console.print(f"  [yellow]Prefs[/]")
        for k, v in prefs.items():
            console.print(f"    [dim yellow]{k}[/]  [white]{v}[/]")
    console.print()
    console.print("  [dim]  /profile set name <name>  |  /profile set timezone <tz>  |  /profile pref <key> <val>[/]\n")

# ── Spinner ───────────────────────────────────────────────────────────────────
def _spinner_thread(stop_event: threading.Event, status_ref: list) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        label = status_ref[0]
        sys.stdout.write(f"\r  {AMBER}{frames[i % len(frames)]}{RESET} {DIM}{label}{RESET}   ")
        sys.stdout.flush()
        i += 1
        time.sleep(0.08)
    _clear_line()

# ── Streaming response ────────────────────────────────────────────────────────
def ask_streaming(user_text: str) -> str:
    mem_result: list[str] = [""]
    mem_done = threading.Event()
    def _fetch_mem():
        mem_result[0] = retrieve(user_text)
        mem_done.set()
    threading.Thread(target=_fetch_mem, daemon=True).start()

    full = ""
    header_printed = False
    status_ref = ["thinking..."]
    stop_spin = threading.Event()

    spin_thread = threading.Thread(
        target=_spinner_thread, args=(stop_spin, status_ref), daemon=True
    )
    spin_thread.start()

    mem_done.wait(timeout=3)
    gen = orchestrator.process_stream(user_text, memory_context=mem_result[0])

    for token in gen:
        if token.startswith(TOOL_EVENT_PREFIX):
            tool_name = token[len(TOOL_EVENT_PREFIX):]
            label, _ = TOOL_LABELS.get(tool_name, ("TOOL", "dim"))
            color = TOOL_ANSI.get(tool_name, DIM)
            status_ref[0] = f"{color}[{label}]{RESET}"
            continue

        if not header_printed:
            stop_spin.set()
            spin_thread.join()
            _clear_line()
            _raw(f"\n  {AMBER}{BOLD}Jarvis{RESET} {GOLD}›{RESET} ")
            header_printed = True

        clean = sanitize(token)
        _raw(clean)
        full += token

    if not stop_spin.is_set():
        stop_spin.set()
        spin_thread.join()
        _clear_line()

    if header_printed:
        _raw("\n\n")

    return full

# ── Slash command router ──────────────────────────────────────────────────────
def handle_slash(raw: str) -> bool:
    global _mode, _running
    parts = raw.strip().split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "/help":
        cmd_help(); return True
    if cmd == "/commands":
        cmd_commands(); return True
    if cmd == "/clear":
        print_banner(); return True
    if cmd in ("/memory", "/mem"):
        cmd_memory(args); return True
    if cmd in ("/skill", "/skills"):
        cmd_skill(args); return True
    if cmd == "/profile":
        cmd_profile(args); return True
    if cmd == "/mode":
        _raw(f"\n  {DIM}Mode: {BOLD}{_mode}{RESET}{DIM} | Version: v{VERSION}{RESET}\n\n")
        return True
    if cmd == "/voice":
        _mode = "voice"
        _raw(f"\n  {AMBER}Switched to VOICE INPUT mode.{RESET}\n")
        _raw(f"  {DIM}Press Enter to start recording.{RESET}\n\n")
        return True
    if cmd == "/text":
        _mode = "text"
        _raw(f"\n  {AMBER}Switched to TEXT mode.{RESET}\n\n")
        return True
    if cmd in ("/quit", "/exit", "/bye"):
        speak("Goodbye, sir.")
        _running = False
        return True
    return False

# ── Voice input cycle ─────────────────────────────────────────────────────────
def voice_input_cycle() -> str | None:
    _raw(f"  {DIM}[ Recording — speak now, pause to stop ]{RESET}\n")
    audio = record_until_silence()
    if audio is None or len(audio) < 1600:
        _raw(f"  {DIM}Nothing captured.{RESET}\n")
        return None
    _raw(f"  {DIM}Transcribing...{RESET}\r")
    text = transcribe(audio)
    _raw(" " * 40 + "\r")
    if not text.strip():
        _raw(f"  {DIM}Could not understand audio.{RESET}\n")
        return None
    _raw(f"\n  {USER_CLR}›{RESET} {WHITE}{sanitize(text)}{RESET}\n")
    return text

# ── Main loop — queue-based, input thread always live ─────────────────────────
def main_loop():
    global _running, _mode

    import queue as _queue
    msg_queue: _queue.Queue[str] = _queue.Queue()
    jarvis_busy = threading.Event()

    def _input_reader():
        while _running:
            try:
                raw = _read_input().strip()
                if not raw:
                    continue

                if raw.startswith("/"):
                    if not handle_slash(raw):
                        _raw(f"  {DIM}Unknown command — /help for help{RESET}\n")
                    continue

                if raw.lower() in ("exit", "quit", "bye"):
                    handle_slash("/quit")
                    return

                if jarvis_busy.is_set():
                    _raw(f"  {DIM}[queued]{RESET}\n")

                msg_queue.put(raw)

            except (EOFError, KeyboardInterrupt):
                _running = False
                msg_queue.put(None)
                break

    # Start Telegram bridge (no-op if TELEGRAM_BOT_TOKEN not set)
    _telegram.start(msg_queue, reply_callback=None)   # reply_callback set below

    input_thread = threading.Thread(target=_input_reader, daemon=True, name="InputReader")
    input_thread.start()

    if _telegram.enabled:
        _raw(f"  {AMBER}Telegram bot active.{RESET} {DIM}Messages from your bot will be processed here.{RESET}\n\n")

    while _running:
        try:
            item = msg_queue.get(timeout=0.3)
        except _queue.Empty:
            continue

        if item is None:
            break

        # Unpack: terminal sends str, Telegram sends (str, chat_id)
        if isinstance(item, tuple):
            user_text, tg_chat_id = item
        else:
            user_text, tg_chat_id = item, None

        jarvis_busy.set()
        try:
            response = ask_streaming(user_text)
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            extract_and_store_async(user_text, response)
            # Send reply back to Telegram if this came from there
            if tg_chat_id is not None and _telegram.enabled:
                _telegram.send(tg_chat_id, response)
        finally:
            jarvis_busy.clear()

    _raw(f"\n  {DIM}Jarvis offline.{RESET}\n\n")

# ── Wake-word voice mode ──────────────────────────────────────────────────────
def wake_word_mode():
    global _running

    _raw(f"  {DIM}Say {AMBER}'Hey Jarvis'{RESET}{DIM} to activate  |  Ctrl+C to quit{RESET}\n")
    _raw(f"  {BAR}\n\n")
    start_listening(_activated.set)
    speak("Jarvis online. Ready when you are, sir.")
    _raw(f"  {AMBER}Jarvis online.{RESET}\n\n")

    try:
        while _running:
            if _activated.wait(timeout=0.5):
                _activated.clear()
                speak("Yes sir?")
                _raw(f"  {AMBER}Listening...{RESET}\n")
                user_text = voice_input_cycle()
                if user_text:
                    response = ask_streaming(user_text)
                    speak(response)
                    extract_and_store_async(user_text, response)
    except KeyboardInterrupt:
        pass
    finally:
        stop_listening()
        _raw(f"\n  {DIM}Jarvis offline.{RESET}\n\n")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print_banner()
    _raw(f"  {DIM}Type a message  |  /help for help  |  /commands for capabilities{RESET}\n")
    _raw(f"  {BAR}\n\n")

    if "--voice" in sys.argv:
        wake_word_mode()
    else:
        main_loop()

if __name__ == "__main__":
    main()
