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
from memory.patterns import pop_suggestions
from core.skills import list_skills, add_skill, remove_skill, clear_skills
from core.profile import get_profile, set_field, set_preference, clear_field
from core.conversation import set_persona, get_persona
from core.custom_commands import list_commands, add_command, remove_command, get_command
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
AMBER    = "\033[38;5;214m"   # Iron Man amber — Jarvis label & accents
GOLD     = "\033[38;5;178m"   # warm gold — borders & rules
CYAN     = "\033[38;5;87m"    # bright cyan — user prompt
BLUE     = "\033[38;5;75m"    # soft blue — section headers
VIOLET   = "\033[38;5;141m"   # violet — memory / learning
GREEN    = "\033[38;5;114m"   # soft green — success / skills
CORAL    = "\033[38;5;210m"   # coral/salmon — warnings & protected
RED      = "\033[38;5;196m"   # red — delete / danger
PINK     = "\033[38;5;218m"   # pink — personality modes
TEAL     = "\033[38;5;43m"    # teal — custom commands
WHITE    = "\033[97m"          # body text
DIM      = "\033[2m"
BOLD     = "\033[1m"
ITALIC   = "\033[3m"
YELLOW   = "\033[93m"
MAGENTA  = "\033[95m"
USER_CLR = CYAN                # user › symbol
RESET    = "\033[0m"

BAR  = f"{GOLD}{'─' * 58}{RESET}"
BAR2 = f"{GOLD}{'·' * 58}{RESET}"

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

# Plain-text status labels shown in spinner (no ANSI — spinner colors them)
TOOL_STATUS = {
    "search_web":        "searching...",
    "scrape_page":       "fetching page...",
    "open_url":          "opening url...",
    "open_app":          "launching app...",
    "run_command":       "running command...",
    "read_file":         "reading file...",
    "write_file":        "writing file...",
    "delete_file":       "deleting...",
    "move_file":         "moving file...",
    "copy_file":         "copying file...",
    "list_directory":    "listing directory...",
    "search_files":      "searching files...",
    "get_system_info":   "getting system info...",
    "remember":          "saving to memory...",
    "send_notification": "sending notification...",
    "install_software":  "installing...",
    "system_power":      "power action...",
}

# Colors cycled by the spinner for status labels
_STATUS_COLORS = [AMBER, GOLD, CYAN, VIOLET, GREEN, PINK, TEAL, CORAL]
_COLOR_CHANGE_TICKS = 15  # ~1.2 s at 0.08 s/frame

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
    for i, line in enumerate(JARVIS_LOGO):
        # Gradient: top lines amber, bottom lines gold
        color = AMBER if i < 3 else GOLD
        _raw(f"  {color}{BOLD}{line}{RESET}\n")
    _raw("\n")
    _raw(f"  {BAR}\n")
    _raw(f"  {AMBER}  v{VERSION}{RESET}  {DIM}·{RESET}  {BLUE}{API_PROVIDER}{RESET}  {DIM}·{RESET}  {DIM}Built by {RESET}{CYAN}{AUTHOR}{RESET}\n")
    _raw(f"  {DIM}  Iron Man AI · type {RESET}{CYAN}/help{RESET}{DIM} to get started{RESET}\n")
    _raw(f"  {BAR}\n\n")

# ── Styled input with borders ─────────────────────────────────────────────────
def _read_input() -> str:
    _raw(f"\n  {CYAN}{BOLD}You{RESET}  {WHITE}")
    result = input()
    _raw(RESET)
    return result

# ── Section header helper ─────────────────────────────────────────────────────
def _section(title: str, color: str) -> None:
    _raw(f"\n  {color}{BOLD}{title}{RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")

def _cmd_row(cmd: str, desc: str, color: str) -> None:
    _raw(f"  {color}{cmd:<32}{RESET}  {DIM}{desc}{RESET}\n")

# ── /help ─────────────────────────────────────────────────────────────────────
def cmd_help():
    _raw(f"\n  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    _raw(f"  {AMBER}{BOLD}   J A R V I S  —  COMMAND REFERENCE{RESET}\n")
    _raw(f"  {AMBER}{BOLD}{'═' * 58}{RESET}\n")

    _section("Navigation", BLUE)
    _cmd_row("/help",                "Show this screen",                          BLUE)
    _cmd_row("/commands",            "List all AI tool capabilities",             BLUE)
    _cmd_row("/clear",               "Redraw the banner",                         BLUE)
    _cmd_row("/mode",                "Show active mode & persona",                BLUE)
    _cmd_row("/quit",                "Graceful shutdown",                         BLUE)

    _section("Input Mode", CYAN)
    _cmd_row("/voice",               "Switch to voice input",                     CYAN)
    _cmd_row("/text",                "Switch to text input (default)",            CYAN)

    _section("Personality", PINK)
    _cmd_row("/funny",               "Witty & sarcastic mode",                    PINK)
    _cmd_row("/stealth",             "Ultra-minimal replies",                     PINK)
    _cmd_row("/think",               "Verbose step-by-step reasoning",            PINK)
    _cmd_row("/roast",               "Playful roast mode",                        PINK)
    _cmd_row("/normal",              "Back to default personality",               PINK)

    _section("Memory  (auto-learned memories are protected)", VIOLET)
    _cmd_row("/memory",              "List all memories",                         VIOLET)
    _cmd_row("/memory add <fact>",   "Manually add a memory",                    VIOLET)
    _cmd_row("/memory remove <n>",   "Remove a manual memory by number",         VIOLET)
    _cmd_row("/memory clear",        "Clear manual memories only",               VIOLET)

    _section("Learning", VIOLET)
    _cmd_row("/learn",               "Show detected behavior patterns",           VIOLET)
    _cmd_row("/learn save <n>",      "Promote a pattern to a permanent skill",   VIOLET)

    _section("Skills  (auto-learned skills are protected)", GREEN)
    _cmd_row("/skill",               "List all skills",                           GREEN)
    _cmd_row("/skill add <text>",    "Add a manual skill",                        GREEN)
    _cmd_row("/skill remove <id>",   "Remove a manual skill",                     GREEN)
    _cmd_row("/skill clear",         "Clear manual skills only",                  GREEN)

    _section("Custom Commands", TEAL)
    _cmd_row("/cmd",                 "List your custom commands",                 TEAL)
    _cmd_row("/cmd add <name> <prompt>", "Create a new /name shortcut",          TEAL)
    _cmd_row("/cmd remove <name>",   "Delete a custom command",                   TEAL)

    _section("Profile", AMBER)
    _cmd_row("/profile",             "Show your profile",                         AMBER)
    _cmd_row("/profile set name X",  "Set your name",                             AMBER)
    _cmd_row("/profile set timezone X", "Set timezone",                           AMBER)
    _cmd_row("/profile pref <k> <v>","Set a preference",                         AMBER)

    _raw(f"\n  {GOLD}{'─' * 50}{RESET}\n")
    _raw(f"  {DIM}Just talk naturally — Jarvis understands plain English.{RESET}\n\n")

# ── /commands ─────────────────────────────────────────────────────────────────
def cmd_commands():
    _raw(f"\n  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    _raw(f"  {AMBER}{BOLD}   J A R V I S  —  AI CAPABILITIES{RESET}\n")
    _raw(f"  {AMBER}{BOLD}{'═' * 58}{RESET}\n")

    cats = [
        ("Web & Search",   CYAN,   [("SEARCH","Search the web"),("FETCH","Scrape any webpage"),("OPEN","Open URL in browser")]),
        ("Apps & System",  BLUE,   [("LAUNCH","Open applications"),("RUN","Execute shell commands"),("SYSTEM","Time, battery, clipboard"),("POWER","Shutdown / restart / sleep")]),
        ("Files",          GREEN,  [("READ","Read file contents"),("WRITE","Create or edit files"),("MOVE","Move / rename files"),("COPY","Copy files"),("DELETE","Delete files"),("LIST","List directory"),("FIND","Search files by name")]),
        ("Software",       TEAL,   [("INSTALL","Install via winget / pip / choco")]),
        ("Memory",         VIOLET, [("REMEMBER","Store facts in long-term memory")]),
        ("Notifications",  AMBER,  [("NOTIFY","Windows desktop notifications")]),
    ]
    for cat, color, tools in cats:
        _raw(f"\n  {color}{BOLD}{cat}{RESET}\n")
        for label, desc in tools:
            _raw(f"    {color}[{label}]{RESET}  {DIM}{desc}{RESET}\n")
    _raw("\n")

# ── /memory ───────────────────────────────────────────────────────────────────
def cmd_memory(args: list[str] = []):
    from memory.long_term import store, get_all, delete_by_index, clear_manual

    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) > 1:
        fact = " ".join(args[1:])
        store(fact, source="manual")
        _raw(f"\n  {VIOLET}● MEMORY{RESET}  {DIM}Saved:{RESET}  {WHITE}{sanitize(fact)}{RESET}\n\n")
        return

    if sub == "remove" and len(args) > 1:
        try:
            idx = int(args[1]) - 1
            ok, reason = delete_by_index(idx)
            if ok:
                _raw(f"\n  {VIOLET}● MEMORY{RESET}  {DIM}Removed entry {idx + 1}.{RESET}\n\n")
            elif reason == "protected":
                _raw(f"\n  {CORAL}⚠  Protected{RESET}  {DIM}Auto-learned memories cannot be deleted.{RESET}\n\n")
            else:
                _raw(f"\n  {RED}✗{RESET}  {DIM}No memory at that number.{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /memory remove <number>{RESET}\n")
        return

    if sub == "clear":
        n = clear_manual()
        _raw(f"\n  {VIOLET}● MEMORY{RESET}  {DIM}Cleared {n} manual memor{'y' if n==1 else 'ies'}. Auto-learned memories preserved.{RESET}\n\n")
        return

    entries = get_all()
    if not entries:
        _raw(f"\n  {DIM}  No memories yet.{RESET}\n\n")
        return

    _raw(f"\n  {VIOLET}{BOLD}  Memories  ({len(entries)}){RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    for i, e in enumerate(entries[:40], 1):
        lock = f"  {CORAL}🔒{RESET}" if e["source"] == "auto" else f"  {GREEN}✎{RESET}"
        _raw(f"  {VIOLET}{i:>2}.{RESET}  {WHITE}{sanitize(e['doc'])}{RESET}{lock}\n")
    if len(entries) > 40:
        _raw(f"  {DIM}  … and {len(entries) - 40} more{RESET}\n")
    _raw(f"\n  {DIM}🔒 auto-learned (protected)  ✎ manual{RESET}\n\n")

# ── /learn ────────────────────────────────────────────────────────────────────
def cmd_learn():
    from memory.patterns import all_patterns
    data = all_patterns()
    if not data:
        _raw(f"\n  {DIM}  No patterns detected yet. Keep talking to Jarvis.{RESET}\n\n")
        return

    _raw(f"\n  {VIOLET}{BOLD}  Detected Patterns{RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    items = sorted(data.items(), key=lambda x: x[1]["count"], reverse=True)
    for i, (key, entry) in enumerate(items, 1):
        if _skill_exists(entry["description"]):
            badge = f"  {GREEN}✓ saved{RESET}"
        else:
            badge = f"  {DIM}seen {entry['count']}×{RESET}"
        _raw(f"  {VIOLET}{i:>2}.{RESET}  {WHITE}{sanitize(entry['description'])}{RESET}{badge}\n")
    _raw(f"\n  {DIM}/learn save <n>  — promote to permanent skill{RESET}\n\n")


def _skill_exists(description: str) -> bool:
    return any(s["instruction"] == description for s in list_skills())


# ── /skill ────────────────────────────────────────────────────────────────────
def cmd_skill(args: list[str] = []):
    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) > 1:
        instruction = " ".join(args[1:])
        skill = add_skill(instruction, source="manual")
        _raw(f"\n  {GREEN}● SKILL{RESET}  {DIM}Added #{skill['id']}:{RESET}  {WHITE}{sanitize(instruction)}{RESET}\n\n")
        return

    if sub == "remove" and len(args) > 1:
        try:
            sid = int(args[1])
            ok, reason = remove_skill(sid)
            if ok:
                _raw(f"\n  {GREEN}● SKILL{RESET}  {DIM}Removed #{sid}.{RESET}\n\n")
            elif reason == "protected":
                _raw(f"\n  {CORAL}⚠  Protected{RESET}  {DIM}Auto-learned skills cannot be deleted.{RESET}\n\n")
            else:
                _raw(f"\n  {RED}✗{RESET}  {DIM}Skill #{sid} not found.{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /skill remove <id>{RESET}\n")
        return

    if sub == "clear":
        n = clear_skills()
        _raw(f"\n  {GREEN}● SKILL{RESET}  {DIM}Cleared {n} manual skill(s). Auto-learned skills preserved.{RESET}\n\n")
        return

    skills = list_skills()
    _raw(f"\n  {GREEN}{BOLD}  Skills  ({len(skills)}){RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    if not skills:
        _raw(f"  {DIM}  No skills yet. Use /skill add <instruction>{RESET}\n")
    else:
        for s in skills:
            lock = f"  {CORAL}🔒{RESET}" if s.get("source") == "auto" else f"  {GREEN}✎{RESET}"
            _raw(f"  {GREEN}{s['id']:>2}.{RESET}  {WHITE}{sanitize(s['instruction'])}{RESET}{lock}\n")
    _raw(f"\n  {DIM}🔒 auto-learned (protected)  ✎ manual{RESET}\n\n")

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
            _raw(f"\n  {AMBER}● PROFILE{RESET}  {DIM}Cleared {key}.{RESET}\n\n")
        else:
            _raw(f"  {RED}✗{RESET}  {DIM}Field '{key}' not found.{RESET}\n")
        return

    p = get_profile()
    _raw(f"\n  {AMBER}{BOLD}  Profile{RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    _raw(f"  {AMBER}Name{RESET}      {WHITE}{p.get('name') or DIM + '(not set)' + RESET}{RESET}\n")
    _raw(f"  {AMBER}Timezone{RESET}  {WHITE}{p.get('timezone') or DIM + '(not set)' + RESET}{RESET}\n")
    _raw(f"  {AMBER}Language{RESET}  {WHITE}{p.get('language', 'English')}{RESET}\n")
    prefs = p.get("preferences", {})
    if prefs:
        _raw(f"  {AMBER}Prefs{RESET}\n")
        for k, v in prefs.items():
            _raw(f"    {DIM}{k}{RESET}  {WHITE}{v}{RESET}\n")
    _raw(f"\n  {DIM}/profile set name X  ·  /profile set timezone X  ·  /profile pref key val{RESET}\n\n")

# ── /cmd ──────────────────────────────────────────────────────────────────────
def cmd_custom(args: list[str] = []):
    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) >= 3:
        name   = args[1]
        prompt = " ".join(args[2:])
        ok, msg = add_command(name, prompt)
        if ok:
            _raw(f"\n  {TEAL}◆ CMD{RESET}  {DIM}Created:{RESET}  {TEAL}/{name}{RESET}  {DIM}→{RESET}  {WHITE}{sanitize(prompt)}{RESET}\n\n")
        else:
            _raw(f"\n  {RED}✗{RESET}  {DIM}{msg}{RESET}\n\n")
        return

    if sub == "remove" and len(args) >= 2:
        name = args[1]
        if remove_command(name):
            _raw(f"\n  {TEAL}◆ CMD{RESET}  {DIM}Removed /{name}.{RESET}\n\n")
        else:
            _raw(f"\n  {RED}✗{RESET}  {DIM}/{name} not found.{RESET}\n\n")
        return

    cmds = list_commands()
    _raw(f"\n  {TEAL}{BOLD}  Custom Commands  ({len(cmds)}){RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    if not cmds:
        _raw(f"  {DIM}  None yet.  Try: /cmd add morning What's today's weather?{RESET}\n")
    else:
        for c in cmds:
            _raw(f"  {TEAL}/{c['name']:<18}{RESET}  {DIM}{sanitize(c['desc'])}{RESET}\n")
    _raw(f"\n  {DIM}/cmd add <name> <prompt>  ·  /cmd remove <name>{RESET}\n\n")

# ── Spinner (cycling colors) ──────────────────────────────────────────────────
def _spinner_thread(stop_event: threading.Event, status_ref: list) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    color_i = 0
    tick = 0
    sys.stdout.write("\n")   # push below the You line so \r doesn't overwrite it
    sys.stdout.flush()
    while not stop_event.is_set():
        color = _STATUS_COLORS[color_i % len(_STATUS_COLORS)]
        label = status_ref[0]
        sys.stdout.write(f"\r  {color}{frames[i % len(frames)]}{RESET}  {color}{label}{RESET}   ")
        sys.stdout.flush()
        i += 1
        tick += 1
        if tick >= _COLOR_CHANGE_TICKS:
            color_i += 1
            tick = 0
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
            status_ref[0] = TOOL_STATUS.get(tool_name, "working...")
            continue

        if not header_printed:
            stop_spin.set()
            spin_thread.join()
            _clear_line()
            _raw(f"  {AMBER}{BOLD}Jarvis{RESET}  ")
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
    if cmd in ("/learn", "/patterns"):
        if args and args[0].lower() == "save" and len(args) > 1:
            from memory.patterns import all_patterns
            try:
                idx = int(args[1]) - 1
                items = sorted(all_patterns().items(), key=lambda x: x[1]["count"], reverse=True)
                if 0 <= idx < len(items):
                    desc = items[idx][1]["description"]
                    skill = add_skill(desc, source="auto")
                    _raw(f"\n  {GREEN}✓  Skill #{skill['id']} saved:{RESET}  {DIM}{sanitize(desc)}{RESET}\n\n")
                else:
                    _raw(f"  {DIM}No pattern at that number.{RESET}\n")
            except ValueError:
                _raw(f"  {DIM}Usage: /learn save <number>{RESET}\n")
        else:
            cmd_learn()
        return True
    if cmd in ("/skill", "/skills"):
        cmd_skill(args); return True
    if cmd in ("/cmd", "/commands_custom"):
        cmd_custom(args); return True
    if cmd == "/profile":
        cmd_profile(args); return True
    if cmd == "/mode":
        persona = get_persona() or "normal"
        _raw(f"\n  {BLUE}◈  Mode:{RESET} {WHITE}{_mode}{RESET}  {BLUE}Persona:{RESET} {PINK}{persona}{RESET}  {DIM}v{VERSION}{RESET}\n\n")
        return True
    if cmd == "/voice":
        _mode = "voice"
        _raw(f"\n  {CYAN}◈  Voice input mode.{RESET} {DIM}Press Enter to start recording.{RESET}\n\n")
        return True
    if cmd == "/text":
        _mode = "text"
        _raw(f"\n  {CYAN}◈  Text mode.{RESET}\n\n")
        return True
    if cmd in ("/funny", "/stealth", "/think", "/roast"):
        name = cmd[1:]
        set_persona(name)
        labels = {
            "funny":   f"{PINK}◈  Funny mode.{RESET}  {DIM}Wit engaged.{RESET}",
            "stealth": f"{PINK}◈  Stealth mode.{RESET}  {DIM}Minimal output from here.{RESET}",
            "think":   f"{PINK}◈  Think mode.{RESET}  {DIM}Reasoning out loud.{RESET}",
            "roast":   f"{PINK}◈  Roast mode.{RESET}  {DIM}You asked for it.{RESET}",
        }
        _raw(f"\n  {labels[name]}\n\n")
        return True
    if cmd == "/normal":
        set_persona(None)
        _raw(f"\n  {PINK}◈  Normal mode.{RESET}\n\n")
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

# ── Main loop ─────────────────────────────────────────────────────────────────
def main_loop():
    global _running, _mode

    import queue as _queue
    tg_queue: _queue.Queue = _queue.Queue()

    # Start Telegram — puts (text, chat_id) tuples into tg_queue
    if _telegram.enabled:
        _telegram.start(tg_queue)
    else:
        _raw(f"  {DIM}Telegram not configured — add TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_ID to .env to enable.{RESET}\n")

    _pending_suggestions: list[str] = []
    _suggestions_lock = threading.Lock()

    def _queue_suggestions_after_delay(delay: float = 2.5):
        import time as _time
        _time.sleep(delay)
        suggestions = pop_suggestions()
        if suggestions:
            with _suggestions_lock:
                _pending_suggestions.extend(suggestions)

    # ── Telegram processor thread (only for remote TG messages) ───────────────
    def _tg_processor():
        while _running:
            try:
                item = tg_queue.get(timeout=0.3)
            except _queue.Empty:
                continue
            if item is None:
                break
            user_text, tg_chat_id = item
            _raw(f"\n  {GOLD}[TG]{RESET}  {WHITE}{sanitize(user_text)}{RESET}\n")
            response = ask_streaming(user_text)
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            extract_and_store_async(user_text, response)
            threading.Thread(target=_queue_suggestions_after_delay, daemon=True).start()
            if _telegram.enabled:
                _telegram.send(tg_chat_id, response)

    if _telegram.enabled:
        threading.Thread(target=_tg_processor, daemon=True, name="TGProcessor").start()

    def _show_pending_suggestions():
        with _suggestions_lock:
            suggestions = list(_pending_suggestions)
            _pending_suggestions.clear()
        for suggestion in suggestions:
            _raw(f"\n  {VIOLET}✦ LEARN{RESET}  {WHITE}{sanitize(suggestion)}{RESET}\n")
            _raw(f"  {DIM}Save as a permanent skill? (y / n){RESET}\n")
            _raw(f"  {CYAN}›{RESET} {WHITE}")
            try:
                answer = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            _raw(RESET)
            if answer in ("y", "yes"):
                skill = add_skill(suggestion, source="auto")
                _raw(f"  {GREEN}✓  Skill #{skill['id']} saved.{RESET}\n\n")
            else:
                _raw(f"  {DIM}Skipped.{RESET}\n\n")

    # ── Input loop: synchronous — next prompt only after response is done ─────
    while _running:
        _show_pending_suggestions()

        try:
            raw = _read_input().strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        if raw.startswith("/"):
            custom = get_command(raw[1:].split()[0])
            if custom:
                _raw(f"  {TEAL}◆ {raw.split()[0]}{RESET}  {DIM}→ {sanitize(custom['prompt'])}{RESET}\n")
                response = ask_streaming(custom["prompt"])
                threading.Thread(target=speak, args=(response,), daemon=True).start()
                extract_and_store_async(custom["prompt"], response)
                threading.Thread(target=_queue_suggestions_after_delay, daemon=True).start()
                continue
            if not handle_slash(raw):
                _raw(f"  {CORAL}Unknown command{RESET}  {DIM}{raw}{RESET}  {CYAN}/help{RESET} {DIM}for help{RESET}\n")
            continue

        if raw.lower() in ("exit", "quit", "bye"):
            handle_slash("/quit")
            break

        # Synchronous — blocks here until response is fully printed
        response = ask_streaming(raw)
        threading.Thread(target=speak, args=(response,), daemon=True).start()
        extract_and_store_async(raw, response)
        threading.Thread(target=_queue_suggestions_after_delay, daemon=True).start()

    if _telegram.enabled:
        tg_queue.put(None)
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
