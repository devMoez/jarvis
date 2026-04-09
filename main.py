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

# ── Tool label map: name → (label, color) ────────────────────────────────────
TOOL_LABELS = {
    "search_web":       ("SEARCH",  "bright_cyan"),
    "scrape_page":      ("FETCH",   "cyan"),
    "open_url":         ("OPEN",    "blue"),
    "open_app":         ("LAUNCH",  "blue"),
    "run_command":      ("RUN",     "yellow"),
    "read_file":        ("READ",    "white"),
    "write_file":       ("WRITE",   "green"),
    "delete_file":      ("DELETE",  "red"),
    "move_file":        ("MOVE",    "magenta"),
    "copy_file":        ("COPY",    "magenta"),
    "list_directory":   ("LIST",    "white"),
    "search_files":     ("FILES",   "cyan"),
    "get_system_info":  ("SYSTEM",  "blue"),
    "remember":         ("MEMORY",  "bright_blue"),
    "send_notification":("NOTIFY",  "yellow"),
    "install_software": ("INSTALL", "green"),
    "system_power":     ("POWER",   "bright_red"),
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
_mode      = "text"   # "text" | "voice"

# ── Helpers ───────────────────────────────────────────────────────────────────
def sanitize(t: str) -> str:
    return t.encode("utf-8", errors="replace").decode("utf-8")

def cls():
    os.system("cls" if os.name == "nt" else "clear")

# ── Banner ────────────────────────────────────────────────────────────────────
def print_banner():
    cls()
    console.print()
    console.print(Panel(
        Text.assemble(
            ("  J A R V I S \n",          "bold cyan"),
            (f"  v{VERSION}",              "cyan"),
            (f"  |  {API_PROVIDER}",       "dim cyan"),
            (f"  |  Powered by {AUTHOR}\n","dim white"),
            ("  AI Personal Assistant",    "dim white"),
        ),
        border_style="cyan",
        box=box.DOUBLE,
        expand=False,
        padding=(1, 4),
    ))
    console.print()

# ── /help ─────────────────────────────────────────────────────────────────────
def cmd_help():
    console.print()
    console.print(Panel(
        Text.assemble(("  JARVIS — HELP", "bold cyan")),
        border_style="cyan", box=box.SIMPLE, expand=False
    ))
    console.print()
    console.print("  [bold white]Getting Started[/]")
    console.print("  [dim]─────────────────────────────────────────[/]")
    console.print("  [white]Run[/]  [cyan]python main.py[/]        [dim]→ text mode (default)[/]")
    console.print("  [white]Run[/]  [cyan]python main.py --voice[/] [dim]→ wake word voice mode[/]")
    console.print()
    console.print("  [bold white]Slash Commands[/]")
    console.print("  [dim]─────────────────────────────────────────[/]")
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
            console.print(f"  [bold cyan]  {cmd:<28}[/] [dim]{desc}[/]")
    console.print()
    console.print("  [bold white]Usage Tips[/]")
    console.print("  [dim]─────────────────────────────────────────[/]")
    console.print("  [dim]Just type naturally — Jarvis understands plain English.[/]")
    console.print("  [dim]Examples:[/]")
    console.print("  [dim]  > search for latest AI news[/]")
    console.print("  [dim]  > open Spotify[/]")
    console.print("  [dim]  > install vlc[/]")
    console.print("  [dim]  > what time is it[/]")
    console.print("  [dim]  > remember my name is Alex[/]")
    console.print("  [dim]  > run ipconfig[/]")
    console.print("  [dim]  > shutdown the computer[/]")
    console.print()

# ── /commands ─────────────────────────────────────────────────────────────────
def cmd_commands():
    console.print()
    console.print(Panel(
        Text.assemble(("  JARVIS — CAPABILITIES", "bold cyan")),
        border_style="cyan", box=box.SIMPLE, expand=False
    ))
    console.print()
    categories = {
        "Web & Search": [
            ("SEARCH",  "bright_cyan",  "Search the web (DuckDuckGo)"),
            ("FETCH",   "cyan",         "Read content from any webpage"),
            ("OPEN",    "blue",         "Open any URL in browser"),
        ],
        "Apps & System": [
            ("LAUNCH",  "blue",         "Open applications by name"),
            ("RUN",     "yellow",       "Execute any shell / terminal command"),
            ("SYSTEM",  "blue",         "Get time, date, battery, clipboard"),
            ("POWER",   "bright_red",   "Shutdown / restart / hibernate / sleep / lock"),
        ],
        "Files": [
            ("READ",    "white",        "Read file contents"),
            ("WRITE",   "green",        "Create or edit files"),
            ("MOVE",    "magenta",      "Move or rename files and folders"),
            ("COPY",    "magenta",      "Copy files and folders"),
            ("DELETE",  "red",          "Delete files and folders"),
            ("LIST",    "white",        "List directory contents"),
            ("FILES",   "cyan",         "Search files by name pattern"),
        ],
        "Software": [
            ("INSTALL", "green",        "Install software via winget / pip / choco"),
        ],
        "Memory": [
            ("MEMORY",  "bright_blue",  "Store facts in long-term memory"),
        ],
        "Notifications": [
            ("NOTIFY",  "yellow",       "Send Windows desktop notifications"),
        ],
    }
    for cat, tools in categories.items():
        console.print(f"  [bold white]{cat}[/]")
        for label, color, desc in tools:
            console.print(f"   [{color}][{label}][/{color}]  [dim]{desc}[/]")
        console.print()

# ── /memory ───────────────────────────────────────────────────────────────────
def cmd_memory(args: list[str] = []):
    """
    /memory              — list all memories
    /memory add <fact>   — add a memory manually
    /memory remove <id>  — remove memory by ID
    /memory clear        — wipe all memories
    """
    from memory.long_term import _get_collection, store

    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) > 1:
        fact = " ".join(args[1:])
        store(fact)
        console.print(f"\n  [bright_blue][MEMORY][/] Saved: [white]{sanitize(fact)}[/]\n")
        return

    if sub == "remove" and len(args) > 1:
        try:
            idx = int(args[1]) - 1
            col = _get_collection()
            results = col.get()
            ids = results.get("ids", [])
            if 0 <= idx < len(ids):
                col.delete(ids=[ids[idx]])
                console.print(f"\n  [bright_blue][MEMORY][/] Removed entry {idx + 1}.\n")
            else:
                console.print(f"  [red]  No memory at index {idx + 1}[/]")
        except ValueError:
            console.print("  [red]  Usage: /memory remove <number>[/]")
        return

    if sub == "clear":
        col = _get_collection()
        col.delete(where={"$exists": True}) if col.count() > 0 else None
        console.print("\n  [bright_blue][MEMORY][/] All memories cleared.\n")
        return

    # Default: list
    try:
        col = _get_collection()
        count = col.count()
        if count == 0:
            console.print("\n  [dim]  No memories stored yet.[/]\n")
            return
        results = col.get()
        docs = results.get("documents", [])
        console.print()
        console.print(f"  [bold bright_blue]  Memories  ({count})[/]")
        console.print("  [dim]─────────────────────────────────────────[/]")
        for i, doc in enumerate(docs[:30], 1):
            console.print(f"  [bright_blue]{i:>2}.[/] [white]{sanitize(doc)}[/]")
        if count > 30:
            console.print(f"  [dim]  ... and {count - 30} more[/]")
        console.print()
        console.print("  [dim]  /memory add <fact>  |  /memory remove <n>  |  /memory clear[/]\n")
    except Exception as e:
        console.print(f"  [red]  Could not load memories: {e}[/]")


# ── /skill ────────────────────────────────────────────────────────────────────
def cmd_skill(args: list[str] = []):
    """
    /skill               — list skills
    /skill add <text>    — add a permanent skill/behavior
    /skill remove <id>   — remove a skill
    /skill clear         — remove all skills
    """
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

    # Default: list
    skills = list_skills()
    console.print()
    console.print(f"  [bold green]  Skills  ({len(skills)})[/]")
    console.print("  [dim]─────────────────────────────────────────[/]")
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
    """
    /profile                    — show profile
    /profile set name Alex      — set your name
    /profile set timezone PST   — set timezone
    /profile set <key> <value>  — set any field
    /profile pref <key> <value> — set a preference
    /profile clear <key>        — remove a field
    """
    sub = args[0].lower() if args else "show"

    if sub == "set" and len(args) >= 3:
        key = args[1].lower()
        value = " ".join(args[2:])
        set_field(key, value)
        console.print(f"\n  [cyan][PROFILE][/] Set {key} = [white]{sanitize(value)}[/]\n")
        return

    if sub == "pref" and len(args) >= 3:
        key = args[1]
        value = " ".join(args[2:])
        set_preference(key, value)
        console.print(f"\n  [cyan][PROFILE][/] Preference set: {key} = [white]{sanitize(value)}[/]\n")
        return

    if sub == "clear" and len(args) >= 2:
        key = args[1].lower()
        if clear_field(key):
            console.print(f"\n  [cyan][PROFILE][/] Cleared {key}.\n")
        else:
            console.print(f"  [red]  Field '{key}' not found.[/]")
        return

    # Default: show
    p = get_profile()
    console.print()
    console.print("  [bold cyan]  Profile[/]")
    console.print("  [dim]─────────────────────────────────────────[/]")
    console.print(f"  [cyan]Name[/]      [white]{p.get('name') or '(not set)'}[/]")
    console.print(f"  [cyan]Timezone[/]  [white]{p.get('timezone') or '(not set)'}[/]")
    console.print(f"  [cyan]Language[/]  [white]{p.get('language', 'English')}[/]")
    prefs = p.get("preferences", {})
    if prefs:
        console.print(f"  [cyan]Prefs[/]")
        for k, v in prefs.items():
            console.print(f"    [dim cyan]{k}[/]  [white]{v}[/]")
    console.print()
    console.print("  [dim]  /profile set name <name>  |  /profile set timezone <tz>  |  /profile pref <key> <val>[/]\n")

# ── Raw stdout write (bypasses Rich buffering, works on Windows) ──────────────
def _raw(text: str, end: str = "") -> None:
    sys.stdout.write(text + end)
    sys.stdout.flush()

def _clear_line() -> None:
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()

# ANSI color codes (work after colorama.init())
CYAN    = "\033[96m"
DIM     = "\033[2m"
BOLD    = "\033[1m"
RESET   = "\033[0m"

# Tool label → ANSI color
TOOL_ANSI = {
    "search_web":        "\033[96m",   # bright cyan
    "scrape_page":       "\033[36m",   # cyan
    "open_url":          "\033[94m",   # blue
    "open_app":          "\033[94m",   # blue
    "run_command":       "\033[93m",   # yellow
    "read_file":         "\033[37m",   # white
    "write_file":        "\033[92m",   # green
    "delete_file":       "\033[91m",   # red
    "move_file":         "\033[95m",   # magenta
    "copy_file":         "\033[95m",   # magenta
    "list_directory":    "\033[37m",   # white
    "search_files":      "\033[36m",   # cyan
    "get_system_info":   "\033[94m",   # blue
    "remember":          "\033[96m",   # bright cyan
    "send_notification": "\033[93m",   # yellow
    "install_software":  "\033[92m",   # green
    "system_power":      "\033[91m",   # red
}

def _spinner_thread(stop_event: threading.Event, status_ref: list) -> None:
    """Single spinner thread. Reads status_ref[0] for current status label."""
    frames = ["|", "/", "-", "\\"]
    i = 0
    while not stop_event.is_set():
        label = status_ref[0]
        sys.stdout.write(f"\r  {DIM}{frames[i % 4]} {label}{RESET}   ")
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    _clear_line()

# ── Streaming response ────────────────────────────────────────────────────────
def ask_streaming(user_text: str) -> str:
    # Fetch memory in background while spinner starts — no blocking wait
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

    spin_thread = threading.Thread(target=_spinner_thread, args=(stop_spin, status_ref), daemon=True)
    spin_thread.start()

    # Wait for memory (usually done in <1s, spinner already running)
    mem_done.wait(timeout=3)
    gen = orchestrator.process_stream(user_text, memory_context=mem_result[0])

    for token in gen:
        if token.startswith(TOOL_EVENT_PREFIX):
            tool_name = token[len(TOOL_EVENT_PREFIX):]
            label, _ = TOOL_LABELS.get(tool_name, ("TOOL", "dim"))
            color = TOOL_ANSI.get(tool_name, DIM)
            status_ref[0] = f"{color}[{label}]{RESET}"
            continue

        # First real token — kill spinner, print header
        if not header_printed:
            stop_spin.set()
            spin_thread.join()
            _clear_line()
            _raw(f"\n  {BOLD}{CYAN}Jarvis{RESET} {DIM}>{RESET} ")
            header_printed = True

        clean = sanitize(token)
        _raw(clean)
        full += token

    # Ensure spinner is stopped
    if not stop_spin.is_set():
        stop_spin.set()
        spin_thread.join()
        _clear_line()

    if header_printed:
        _raw("\n\n")

    return full

# ── Slash command router ──────────────────────────────────────────────────────
def handle_slash(raw: str) -> bool:
    """Returns True if command was handled."""
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
        console.print(f"\n  [dim]  Mode: [bold cyan]{_mode}[/] | Version: [cyan]v{VERSION}[/]\n")
        return True
    if cmd == "/voice":
        _mode = "voice"
        console.print("\n  [cyan]  Switched to VOICE INPUT mode.[/]")
        console.print("  [dim]  Press Enter to start recording.[/]\n")
        return True
    if cmd == "/text":
        _mode = "text"
        console.print("\n  [cyan]  Switched to TEXT mode.[/]\n")
        return True
    if cmd in ("/quit", "/exit", "/bye"):
        speak("Goodbye, sir.")
        _running = False
        return True
    return False

# ── Voice input cycle ─────────────────────────────────────────────────────────
def voice_input_cycle() -> str | None:
    """Record audio, transcribe, return text. None if nothing captured."""
    console.print("  [dim cyan]  [ Recording — speak now, pause to stop ][/]")
    audio = record_until_silence()
    if audio is None or len(audio) < 1600:
        console.print("  [dim]  Nothing captured.[/]")
        return None
    console.print("  [dim]  Transcribing...[/]", end="\r")
    text = transcribe(audio)
    console.print(" " * 40, end="\r")
    if not text.strip():
        console.print("  [dim]  Could not understand audio.[/]")
        return None
    console.print(f"  [bold white]You[/] [dim white]>[/] [white]{sanitize(text)}[/]")
    return text

# ── Main loop ─────────────────────────────────────────────────────────────────
def main_loop():
    global _running, _mode

    while _running:
        try:
            if _mode == "voice":
                input("  [dim]Press Enter to speak...[/] ")
                user_text = voice_input_cycle()
                if not user_text:
                    continue
            else:
                raw = input("  You > ").strip()
                if not raw:
                    continue
                if raw.startswith("/"):
                    if handle_slash(raw):
                        continue
                    else:
                        console.print(f"  [dim red]Unknown command. Type /help for help.[/]")
                        continue
                if raw.lower() in ("exit", "quit", "bye"):
                    handle_slash("/quit")
                    break
                user_text = raw

            response = ask_streaming(user_text)
            # TTS in background so prompt returns immediately
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            extract_and_store_async(user_text, response)

        except (KeyboardInterrupt, EOFError):
            break

    console.print("\n  [dim]Jarvis offline.[/]\n")

# ── Wake-word voice mode (full voice I/O) ─────────────────────────────────────
def wake_word_mode():
    global _running

    console.print(f"  [dim]Say [bold cyan]'Hey Jarvis'[/] to activate  |  Ctrl+C to quit[/]")
    console.print(Rule(style="dim cyan"))
    console.print()
    start_listening(_activated.set)
    speak("Jarvis online. Ready when you are, sir.")
    console.print("  [dim cyan]Jarvis online.[/]\n")

    try:
        while _running:
            if _activated.wait(timeout=0.5):
                _activated.clear()
                speak("Yes sir?")
                console.print("  [cyan]  Listening...[/]")
                user_text = voice_input_cycle()
                if user_text:
                    response = ask_streaming(user_text)
                    speak(response)
                    extract_and_store_async(user_text, response)
    except KeyboardInterrupt:
        pass
    finally:
        stop_listening()
        console.print("\n  [dim]Jarvis offline.[/]\n")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print_banner()
    console.print(f"  [dim]Type a message  |  /help for help  |  /commands for capabilities[/]")
    console.print(Rule(style="dim cyan"))
    console.print()

    if "--voice" in sys.argv:
        wake_word_mode()
    else:
        main_loop()

if __name__ == "__main__":
    main()
