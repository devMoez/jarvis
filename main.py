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

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.rule import Rule
from rich.table import Table

console = Console(force_terminal=True, highlight=False)

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
            ("  J A R V I S \n", "bold cyan"),
            ("  AI Personal Assistant", "dim white"),
        ),
        border_style="cyan",
        box=box.DOUBLE,
        expand=False,
        padding=(1, 6),
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
    rows = [
        ("/help",     "Show this screen"),
        ("/commands", "List all Jarvis capabilities"),
        ("/voice",    "Switch to voice input mode"),
        ("/text",     "Switch to text input mode"),
        ("/clear",    "Clear the terminal"),
        ("/memory",   "Show stored long-term memories"),
        ("/mode",     "Show current mode"),
        ("/quit",     "Exit Jarvis"),
    ]
    for cmd, desc in rows:
        console.print(f"  [bold cyan]{cmd:<12}[/] [white]{desc}[/]")
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
def cmd_memory():
    try:
        from memory.long_term import _get_collection
        col = _get_collection()
        count = col.count()
        if count == 0:
            console.print("  [dim]No memories stored yet.[/]")
            return
        results = col.get()
        docs = results.get("documents", [])
        console.print()
        console.print(f"  [bold bright_blue]Long-term memories ({count})[/]")
        console.print("  [dim]─────────────────────────────────────────[/]")
        for i, doc in enumerate(docs[:20], 1):
            console.print(f"  [bright_blue]{i:>2}.[/] [white]{sanitize(doc)}[/]")
        if count > 20:
            console.print(f"  [dim]  ... and {count - 20} more[/]")
        console.print()
    except Exception as e:
        console.print(f"  [red]Could not load memories: {e}[/]")

# ── Tool status display ───────────────────────────────────────────────────────
def print_tool_event(tool_name: str):
    label, color = TOOL_LABELS.get(tool_name, ("TOOL", "dim"))
    console.print(f"  [{color}][{label}][/{color}]", end="\r")

# ── Streaming response ────────────────────────────────────────────────────────
def ask_streaming(user_text: str) -> str:
    memory_context = retrieve(user_text)
    gen = orchestrator.process_stream(user_text, memory_context=memory_context)

    full = ""
    first_token = True
    spinner_stop = threading.Event()

    def spin():
        frames = [".  ", ".. ", "..."]
        i = 0
        while not spinner_stop.is_set():
            console.print(f"\r  [dim cyan]thinking{frames[i % 3]}[/]", end="")
            i += 1
            time.sleep(0.35)
        console.print("\r" + " " * 30 + "\r", end="")

    spin_thread = threading.Thread(target=spin, daemon=True)
    spin_thread.start()

    header_printed = False

    for token in gen:
        if token.startswith(TOOL_EVENT_PREFIX):
            tool_name = token[len(TOOL_EVENT_PREFIX):]
            spinner_stop.set()
            spin_thread.join()
            spinner_stop = threading.Event()
            print_tool_event(tool_name)
            # restart spinner for next round
            spin_thread = threading.Thread(target=spin, daemon=True)
            spin_thread.start()
            continue

        if first_token:
            spinner_stop.set()
            spin_thread.join()
            first_token = False
            console.print("\r" + " " * 30 + "\r", end="")

        if not header_printed:
            console.print(f"\n  [bold cyan]Jarvis[/] [dim cyan]>[/] ", end="")
            header_printed = True

        console.print(sanitize(token), end="")
        full += token

    console.print("\n")
    spinner_stop.set()
    return full

# ── Slash command router ──────────────────────────────────────────────────────
def handle_slash(cmd: str) -> bool:
    """Returns True if command was handled."""
    global _mode, _running
    cmd = cmd.strip().lower()

    if cmd == "/help":
        cmd_help(); return True
    if cmd == "/commands":
        cmd_commands(); return True
    if cmd == "/clear":
        print_banner(); return True
    if cmd == "/memory":
        cmd_memory(); return True
    if cmd == "/mode":
        console.print(f"\n  [dim]Current mode: [bold cyan]{_mode}[/]\n")
        return True
    if cmd == "/voice":
        _mode = "voice"
        console.print("\n  [cyan]  Switched to VOICE INPUT mode.[/]")
        console.print("  [dim]  Speak after the prompt. Press Enter to start recording.[/]\n")
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
