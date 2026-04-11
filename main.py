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

import colorama
# convert=True  → colorama intercepts ANSI codes and calls Win32 console API (works in ALL terminals)
# strip=False   → don't strip sequences (convert is doing the job)
# This is more reliable than relying on VT100 terminal support.
colorama.init(autoreset=False, convert=True, strip=False)

from dotenv import load_dotenv
from pathlib import Path as _Path
load_dotenv(_Path(__file__).parent / ".env")

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.rule import Rule

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout as _patch_stdout
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.lexers import Lexer as _PTLexer
from prompt_toolkit.styles import Style as _PTStyle

from version import VERSION, API_PROVIDER, AUTHOR

console = Console(force_terminal=True, color_system="256", highlight=False)

if not os.getenv("OPENROUTER_API_KEY"):
    console.print("[red]  ERROR: No API key found. Set OPENROUTER_API_KEY in .env[/]")
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
from core.api_manager import add_key as _api_add_key, list_providers as _api_list_providers
from core.conversation import (
    save_custom_mode, delete_custom_mode, list_all_modes,
    set_mode as _set_mode, get_mode as _get_mode,
)
from tools.search import search_web
from tools.research import deep_research
from tools.books import find_book
from memory.task_memory import task_memory
from tools.browser import (
    open_url, scrape_page,
    browser_open_visible, browser_login, browser_with_session, browser_list_sessions,
)
from tools.app_control import open_app
from tools.system_info import get_system_info
from tools.file_ops import read_file, write_file, list_directory, send_notification
from tools.os_control import (run_command, move_file, copy_file, delete_file,
                               system_power, install_software, search_files)
from telegram_bridge import TelegramBridge

_telegram = TelegramBridge()

# ── ANSI color palette ────────────────────────────────────────────────────────
# Using standard 16-color codes — colorama's Win32 converter handles these reliably
AMBER    = "\033[93m"    # bright yellow — Iron Man amber
GOLD     = "\033[33m"    # yellow — warm gold
CYAN     = "\033[96m"    # bright cyan — user prompt
BLUE     = "\033[94m"    # bright blue — section headers
VIOLET   = "\033[95m"    # bright magenta — memory / learning
GREEN    = "\033[92m"    # bright green — success / skills
CORAL    = "\033[91m"    # bright red — warnings & protected
RED      = "\033[91m"    # bright red — delete / danger
PINK     = "\033[35m"    # magenta — personality modes
TEAL     = "\033[36m"    # cyan — custom commands
WHITE    = "\033[97m"    # body text
DIM      = "\033[2m"
BOLD     = "\033[1m"
ITALIC   = "\033[3m"
YELLOW   = "\033[93m"
MAGENTA  = "\033[95m"
USER_CLR = CYAN                # user › symbol
RESET    = "\033[0m"

BAR  = f"{GOLD}{'─' * 58}{RESET}"
BAR2 = f"{GOLD}{'·' * 58}{RESET}"

# ── Known built-in slash commands (for live input coloring) ───────────────────
_KNOWN_CMDS = {
    "/help", "/commands", "/clear", "/mode", "/quit", "/exit", "/bye",
    "/voice", "/text", "/funny", "/stealth", "/think", "/roast", "/normal",
    "/memory", "/mem", "/learn", "/patterns", "/skill", "/skills",
    "/cmd", "/commands_custom", "/profile",
    "/add-api", "/list-apis",
    "/first",
    "/search", "/research", "/book",
}

class _CmdLexer(_PTLexer):
    """Color /commands as you type: valid=cyan, partial=teal, unknown=gray."""
    def lex_document(self, document):
        text = document.text
        def get_line(lineno):
            if not text.startswith("/"):
                return [("", text)]
            parts = text.split()
            cmd  = parts[0].lower() if parts else text.lower()
            if cmd in _KNOWN_CMDS:
                return [("class:cmd-valid", text)]
            if any(k.startswith(cmd) for k in _KNOWN_CMDS):
                return [("class:cmd-partial", text)]
            return [("class:cmd-unknown", text)]
        return get_line

_PROMPT_STYLE = _PTStyle.from_dict({
    "pt-label":   "bold #57d7ff",   # You  — bright cyan bold
    "pt-arrow":   "#57d7ff",        # ›
    "pt-mode":    "bold #5fd787",   # [mode] tag
    "pt-queue":   "bold #ff8c69",   # [Q:n] tag
    "cmd-valid":  "bold #5fd7ff",   # known command — cyan bold
    "cmd-partial":"#5faf87",        # still typing — teal
    "cmd-unknown":"#808080",        # unrecognised — dim gray
    # bottom toolbar
    "toolbar":         "bg:#0d0d1a #57d7ff",
    "toolbar.mode":    "bg:#0d0d1a bold #5fd787",
    "toolbar.busy":    "bg:#0d0d1a bold #ffd700",
    "toolbar.queue":   "bg:#0d0d1a bold #ff8c69",
    "toolbar.hint":    "bg:#0d0d1a #404040",
    "toolbar.model":   "bg:#0d0d1a #505088",
})

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
    "system_power":        ("POWER",   "bright_red"),
    "browser_open_visible":("BROWSER",  "cyan"),
    "browser_login":       ("LOGIN",    "cyan"),
    "browser_with_session":("SESSION",  "cyan"),
    "deep_research":       ("RESEARCH", "magenta"),
    "find_book":           ("BOOKS",    "green"),
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
    "system_power":        RED,
    "browser_open_visible":CYAN,
    "browser_login":       CYAN,
    "browser_with_session":CYAN,
    "deep_research":       VIOLET,
    "find_book":           GREEN,
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
    "system_power":        "power action...",
    "browser_open_visible":"opening browser...",
    "browser_login":       "opening login window...",
    "browser_with_session":"opening with session...",
    "deep_research":       "researching topic...",
    "find_book":           "searching LibGen...",
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
registry.register("search_files",         search_files)
registry.register("browser_open_visible", browser_open_visible)
registry.register("browser_login",        browser_login)
registry.register("browser_with_session", browser_with_session)
registry.register("deep_research",        deep_research)
registry.register("find_book",            find_book)

orchestrator = Orchestrator(tool_registry=registry)


# ── State ─────────────────────────────────────────────────────────────────────
_running      = True
_activated    = threading.Event()
_mode         = "text"
_abort_event  = threading.Event()   # set to cancel the current AI task (Ctrl+Q)
_worker_busy  = threading.Event()   # set while worker thread is processing

# ── Raw stdout helpers ────────────────────────────────────────────────────────
def sanitize(t: str) -> str:
    return t.encode("utf-8", errors="replace").decode("utf-8")

def cls():
    os.system("cls" if os.name == "nt" else "clear")

if sys.platform == "win32":
    from colorama.ansitowin32 import AnsiToWin32 as _AnsiToWin32
    def _raw(text: str, end: str = "") -> None:
        _AnsiToWin32(sys.stdout, convert=True, strip=False).write(text + end)
        sys.stdout.flush()
else:
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
        color = AMBER if i < 3 else GOLD
        _raw(f"  {color}{BOLD}{line}{RESET}\n")
    _raw("\n")
    _raw(f"  {GOLD}{BOLD}v{CYAN}{VERSION}{RESET}\n")
    _raw(f"  {GOLD}{BOLD}Powered By {CYAN}OpenRouter{GOLD}  |  Built by {CYAN}Moez{RESET}\n")
    _raw(f"\n  {BAR}\n\n")

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

    _section("API Keys & Providers", GOLD)
    _cmd_row("/add-api openrouter <key>","Update OpenRouter API key",                  GOLD)
    _cmd_row("/list-apis",           "Show all providers & active model",         GOLD)

    _section("Behavior Modes", PINK)
    _cmd_row("/mode",                "Show active mode",                           PINK)
    _cmd_row("/mode <name>",         "Switch mode: expert/coder/jarvis/humanize/…",PINK)
    _cmd_row("/mode list",           "List all available modes",                  PINK)
    _cmd_row("/mode save <n> \"…\"", "Create a custom mode with your own prompt", PINK)
    _cmd_row("/mode delete <name>",  "Delete a custom mode",                      PINK)
    _cmd_row("/mode off",            "Clear active mode (back to default)",       PINK)

    _section("Research & Books", GREEN)
    _cmd_row("/search <query>",       "Web search (Tavily or DuckDuckGo)",            GREEN)
    _cmd_row("/research <topic>",     "Deep research: scrape sources, full report",   GREEN)
    _cmd_row("/book <title/author>",  "Find & download book from LibGen",             GREEN)

    _section("Task History", VIOLET)
    _cmd_row("/memory tasks",         "Show last 20 task queries",                    VIOLET)
    _cmd_row("/memory tasks clear",   "Clear task history",                           VIOLET)

    _section("Priority Queue", CORAL)
    _cmd_row("/first <message>",     "Insert message at front of queue (runs next)", CORAL)

    _section("Keyboard Shortcuts", CYAN)
    _cmd_row("Ctrl+Q",               "Cancel running task  /  quit (if idle)",    CYAN)

    _raw(f"\n  {GOLD}{'─' * 50}{RESET}\n")
    _raw(f"  {DIM}Just talk naturally — Jarvis understands plain English.{RESET}\n\n")

# ── /commands ─────────────────────────────────────────────────────────────────
def cmd_commands():
    _raw(f"\n  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    _raw(f"  {AMBER}{BOLD}   J A R V I S  —  AI CAPABILITIES{RESET}\n")
    _raw(f"  {AMBER}{BOLD}{'═' * 58}{RESET}\n")

    cats = [
        ("Web & Search",   CYAN,   [("SEARCH","Search the web (Tavily/DuckDuckGo)"),("FETCH","Scrape any webpage"),("OPEN","Open URL in browser"),("BROWSER","Open visible Chrome window"),("LOGIN","Sign-in with persistent session"),("SESSION","Open URL with saved login")]),
        ("Research",       VIOLET, [("RESEARCH","Deep research: Tavily + scrape + full report"),]),
        ("Books & Files",  GREEN,  [("BOOKS","Find & download books from LibGen / Anna's Archive")]),
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

    if sub == "tasks":
        sub2 = args[1].lower() if len(args) > 1 else "show"
        if sub2 == "clear":
            n = task_memory.clear()
            _raw(f"\n  {VIOLET}● TASKS{RESET}  {DIM}Cleared {n} task entr{'y' if n==1 else 'ies'}.{RESET}\n\n")
        else:
            _raw(f"\n{task_memory.show(20)}\n\n")
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

# ── Task classifier (light vs heavy model) ───────────────────────────────────
_HEAVY_KEYWORDS = (
    "research", "analyze", "analyse", "write", "create", "generate", "plan",
    "design", "explain", "debug", "implement", "report", "essay", "letter",
    "document", "translate", "summarize", "compare", "review", "investigate",
    "study", "evaluate", "describe", "elaborate", "code", "script", "program",
    "algorithm", "refactor", "optimize", "difference between", "how does",
    "how do i", "help me understand", "walk me through", "what is the",
    "why does", "why is", "can you explain", "tell me about",
)

def _classify_task(text: str) -> str:
    """Return 'heavy' (smart model) or 'light' (fast model) for the given message."""
    lower = text.lower()
    if len(text) > 120:
        return "heavy"
    if any(kw in lower for kw in _HEAVY_KEYWORDS):
        return "heavy"
    return "light"


# ── Spinner (cycling colors) ──────────────────────────────────────────────────
def _spinner_thread(stop_event: threading.Event, status_ref: list) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    color_i = 0
    tick = 0
    _raw("\n")   # push below the You line so \r doesn't overwrite it
    while not stop_event.is_set():
        color = _STATUS_COLORS[color_i % len(_STATUS_COLORS)]
        label = status_ref[0]
        _raw(f"\r  {color}{frames[i % len(frames)]}{RESET}  {color}{label}{RESET}   ")
        i += 1
        tick += 1
        if tick >= _COLOR_CHANGE_TICKS:
            color_i += 1
            tick = 0
        time.sleep(0.08)
    _clear_line()

# ── Streaming response ────────────────────────────────────────────────────────
def ask_streaming(user_text: str, abort_check=None, model_tier: str = "auto") -> str:
    mem_result: list[str] = [""]
    mem_done = threading.Event()
    def _fetch_mem():
        mem_result[0] = retrieve(user_text)
        mem_done.set()
    threading.Thread(target=_fetch_mem, daemon=True).start()

    full = ""
    header_printed = False
    status_ref = ["thinking..."]
    stop_spin  = threading.Event()

    spin_thread = threading.Thread(
        target=_spinner_thread, args=(stop_spin, status_ref), daemon=True
    )
    spin_thread.start()

    # ── Word-wrap state ───────────────────────────────────────────────────────
    _WRAP       = 78
    _CONT       = "  "           # 2-space indent, matches standard UI left edge
    _col        = [2]
    _wbuf       = [""]

    def _out(ch: str) -> None:
        if ch == "\n":
            if _wbuf[0]:
                _raw(_wbuf[0])
                _col[0] += len(_wbuf[0])
                _wbuf[0] = ""
            _raw("\n" + _CONT)
            _col[0] = len(_CONT)
        elif ch == " ":
            candidate = _wbuf[0] + " "
            if _col[0] + len(candidate) > _WRAP:
                _raw("\n" + _CONT)
                _col[0] = len(_CONT)
                _raw(_wbuf[0])
                _col[0] += len(_wbuf[0])
                _wbuf[0] = ""
                # drop the space that triggered the wrap
            else:
                _raw(candidate)
                _col[0] += len(candidate)
                _wbuf[0] = ""
        else:
            _wbuf[0] += ch

    def _flush_wbuf() -> None:
        if _wbuf[0]:
            if _col[0] + len(_wbuf[0]) > _WRAP:
                _raw("\n" + _CONT)
            _raw(_wbuf[0])
            _wbuf[0] = ""

    mem_done.wait(timeout=3)
    gen = orchestrator.process_stream(
        user_text,
        memory_context=mem_result[0],
        abort_check=abort_check,
        model_tier=model_tier,
    )

    for token in gen:
        if abort_check and abort_check():
            break

        if token.startswith(TOOL_EVENT_PREFIX):
            tool_name = token[len(TOOL_EVENT_PREFIX):]
            status_ref[0] = TOOL_STATUS.get(tool_name, "working...")
            continue

        if not header_printed:
            stop_spin.set()
            spin_thread.join()
            _clear_line()
            _raw("  ")
            header_printed = True

        for ch in sanitize(token):
            _out(ch)
        full += token

    if not stop_spin.is_set():
        stop_spin.set()
        spin_thread.join()
        _clear_line()

    if header_printed:
        _flush_wbuf()
        _raw("\n\n")

    return full

# ── /add-api ──────────────────────────────────────────────────────────────────
def cmd_add_api(args: list[str]) -> None:
    if len(args) < 2:
        _raw(f"\n  {DIM}Usage: /add-api <provider> <key>{RESET}\n")
        _raw(f"  {DIM}Provider: openrouter{RESET}\n\n")
        return
    provider, key = args[0], args[1]
    ok, msg = _api_add_key(provider, key)
    if ok:
        # Rebuild the orchestrator's provider chain
        orchestrator._api.rebuild()
        chain_len = orchestrator._api.chain_length
        _raw(f"\n  {GREEN}◉  {msg}{RESET}  {DIM}Chain rebuilt — {chain_len} model(s) available.{RESET}\n\n")
    else:
        _raw(f"\n  {RED}✗{RESET}  {DIM}{msg}{RESET}\n\n")


# ── /list-apis ────────────────────────────────────────────────────────────────
def cmd_list_apis() -> None:
    providers = _api_list_providers()
    _raw(f"\n  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    _raw(f"  {AMBER}{BOLD}   API PROVIDERS{RESET}\n")
    _raw(f"  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    for p in providers:
        if p["configured"]:
            dot = f"{GREEN}◉{RESET}"
            key_str = f"  {DIM}{p['preview']}{RESET}"
            models_str = f"  {DIM}[{len(p['models'])} models]{RESET}"
        else:
            dot = f"{DIM}○{RESET}"
            key_str = f"  {DIM}(not configured){RESET}"
            models_str = ""
        _raw(f"  {dot}  {AMBER}{p['display']:<18}{RESET}{key_str}{models_str}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    cur_p = orchestrator._api.current_provider
    cur_m = orchestrator._api.current_model
    _raw(f"  {DIM}Active:{RESET}  {GREEN}{cur_p}{RESET} / {WHITE}{cur_m}{RESET}\n")
    _raw(f"\n  {DIM}/add-api <provider> <key>  — add a new key{RESET}\n\n")


# ── /mode ─────────────────────────────────────────────────────────────────────
def cmd_mode(args: list[str]) -> None:
    if not args:
        current = _get_mode()
        if current:
            _raw(f"\n  {PINK}◈  Active mode:{RESET}  {WHITE}{current}{RESET}\n\n")
        else:
            _raw(f"\n  {PINK}◈  No mode active (default).{RESET}  {DIM}Try /mode jarvis{RESET}\n\n")
        return

    sub = args[0].lower()

    if sub == "list":
        all_modes = list_all_modes()
        _raw(f"\n  {PINK}{BOLD}  Modes  ({len(all_modes)}){RESET}\n")
        _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
        for name, prompt in all_modes.items():
            active_tag = f"  {GREEN}← active{RESET}" if name == _get_mode() else ""
            _raw(f"  {PINK}{name:<18}{RESET}  {DIM}{prompt[:55]}...{RESET}{active_tag}\n")
        _raw(f"\n  {DIM}/mode <name>  |  /mode save <name> \"<prompt>\"  |  /mode delete <name>{RESET}\n\n")
        return

    if sub == "save" and len(args) >= 3:
        name   = args[1].lower()
        prompt = " ".join(args[2:]).strip('"').strip("'")
        save_custom_mode(name, prompt)
        _set_mode(name)
        _raw(f"\n  {PINK}◈  Mode '{name}' saved and activated.{RESET}\n\n")
        return

    if sub == "delete" and len(args) >= 2:
        name = args[1].lower()
        if delete_custom_mode(name):
            if _get_mode() == name:
                _set_mode(None)
            _raw(f"\n  {PINK}◈  Mode '{name}' deleted.{RESET}\n\n")
        else:
            _raw(f"\n  {RED}✗{RESET}  {DIM}Mode '{name}' not found.{RESET}\n\n")
        return

    if sub == "off" or sub == "none":
        _set_mode(None)
        _raw(f"\n  {PINK}◈  Mode cleared — back to default.{RESET}\n\n")
        return

    # Set mode by name
    all_modes = list_all_modes()
    if sub in all_modes:
        _set_mode(sub)
        preview = all_modes[sub][:70]
        _raw(f"\n  {PINK}◈  Mode:{RESET}  {WHITE}{sub}{RESET}\n")
        _raw(f"  {DIM}{preview}...{RESET}\n\n")
    else:
        avail = "  ".join(sorted(all_modes.keys()))
        _raw(f"\n  {CORAL}Unknown mode '{sub}'.{RESET}\n")
        _raw(f"  {DIM}Available: {avail}{RESET}\n")
        _raw(f"  {DIM}Create one: /mode save {sub} \"your system prompt\"{RESET}\n\n")


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
        cmd_mode(args); return True
    if cmd == "/add-api":
        cmd_add_api(args); return True
    if cmd == "/list-apis":
        cmd_list_apis(); return True
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

# ── Priority message deque ────────────────────────────────────────────────────
class _PriorityDeque:
    """Thread-safe deque with put_first() for /first priority injection."""
    def __init__(self):
        import collections
        self._d    = collections.deque()
        self._lock = threading.Lock()
        self._ev   = threading.Event()

    def put(self, item) -> None:
        with self._lock: self._d.append(item)
        self._ev.set()

    def put_first(self, item) -> None:
        with self._lock: self._d.appendleft(item)
        self._ev.set()

    def get(self, timeout: float = 0.3):
        if self._ev.wait(timeout):
            with self._lock:
                if self._d:
                    item = self._d.popleft()
                    if not self._d:
                        self._ev.clear()
                    return item
        return None

    def size(self) -> int:
        with self._lock: return len(self._d)

    def peek(self) -> list:
        with self._lock: return list(self._d)


# ── Main loop ─────────────────────────────────────────────────────────────────
def main_loop():
    global _running, _mode

    import queue as _queue
    tg_queue: _queue.Queue = _queue.Queue()
    msg_queue = _PriorityDeque()

    # Start Telegram
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

    def _flush_suggestions():
        with _suggestions_lock:
            suggestions = list(_pending_suggestions)
            _pending_suggestions.clear()
        for suggestion in suggestions:
            _raw(f"\n  {VIOLET}✦ LEARN{RESET}  {WHITE}{sanitize(suggestion)}{RESET}\n")
            _raw(f"  {DIM}/learn save <n>  — promote to a permanent skill{RESET}\n\n")

    # ── Telegram processor ─────────────────────────────────────────────────────
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

    # ── Message worker (AI calls, non-blocking input) ──────────────────────────
    def _worker():
        while _running:
            item = msg_queue.get(timeout=0.3)
            if item is None:
                continue
            if item == "__STOP__":
                break

            _worker_busy.set()
            _abort_event.clear()
            try:
                abort_check = lambda: _abort_event.is_set()

                if isinstance(item, tuple):
                    prompt_str, raw_cmd = item
                    _raw(f"  {TEAL}◆ {raw_cmd.split()[0]}{RESET}  {DIM}→ {sanitize(prompt_str)}{RESET}\n")
                    tier = _classify_task(prompt_str)
                    response = ask_streaming(prompt_str, abort_check=abort_check, model_tier=tier)
                    extract_and_store_async(prompt_str, response)
                    task_memory.save(prompt_str, response)
                else:
                    tier = _classify_task(item)
                    response = ask_streaming(item, abort_check=abort_check, model_tier=tier)
                    extract_and_store_async(item, response)
                    task_memory.save(item, response)
            finally:
                _worker_busy.clear()
                _abort_event.clear()

            threading.Thread(target=speak, args=(response,), daemon=True).start()
            threading.Thread(target=_queue_suggestions_after_delay, daemon=True).start()
            _flush_suggestions()

    threading.Thread(target=_worker, daemon=True, name="MsgWorker").start()

    # ── Dynamic lexer (includes user /cmd names) ───────────────────────────────
    class _DynCmdLexer(_CmdLexer):
        def lex_document(self, document):
            text  = document.text
            known = set(_KNOWN_CMDS)
            for c in list_commands():
                known.add(f"/{c['name']}")
            def get_line(lineno):
                if not text.startswith("/"):
                    return [("", text)]
                parts = text.split()
                cmd   = parts[0].lower() if parts else text.lower()
                if cmd in known:
                    return [("class:cmd-valid", text)]
                if any(k.startswith(cmd) for k in known):
                    return [("class:cmd-partial", text)]
                return [("class:cmd-unknown", text)]
            return get_line

    # ── Bottom toolbar — shows mode, busy state, queue depth ──────────────────
    def _toolbar():
        mode  = _get_mode()
        busy  = _worker_busy.is_set()
        qsize = msg_queue.size()
        parts = [("class:toolbar", f"  ⚡ Jarvis")]
        if mode:
            parts.append(("class:toolbar.mode",  f"  [{mode.upper()}]"))
        if busy:
            parts.append(("class:toolbar.busy",  "  processing…"))
        if qsize > 0:
            parts.append(("class:toolbar.queue", f"  [{qsize} queued]"))
        parts.append(("class:toolbar.hint",  "  Ctrl+Q: cancel/quit"))
        cur_m = orchestrator._api.current_model
        # Show tier indicator: ⚡ light  ◈ heavy
        parts.append(("class:toolbar.model", f"  {cur_m}"))
        return parts

    # ── Ctrl+Q key binding ─────────────────────────────────────────────────────
    from prompt_toolkit.key_binding import KeyBindings
    kb = KeyBindings()

    @kb.add("c-q")
    def _ctrlq(event):
        global _running
        if _worker_busy.is_set():
            _abort_event.set()
            _raw(f"\n  {CORAL}⊘  Cancelling task...{RESET}\n")
        else:
            _running = False
            event.app.exit(exception=KeyboardInterrupt)

    session = PromptSession(
        lexer=_DynCmdLexer(),
        style=_PROMPT_STYLE,
        key_bindings=kb,
        bottom_toolbar=_toolbar,
        refresh_interval=0.5,
    )

    # Cycling bullet colors for prompt ○ and /first ◆
    _BULLET_HEX   = ["#57d7ff", "#d7af00", "#af87d7", "#5fd787", "#00af87", "#875f87", "#ff5f5f", "#d7d700"]
    _BULLET_COLORS = [CYAN, AMBER, VIOLET, GREEN, TEAL, PINK, CORAL, GOLD]
    _bi = [0]
    _cur_bullet = ["#57d7ff"]

    def _bullet():
        c = _BULLET_COLORS[_bi[0] % len(_BULLET_COLORS)]
        _bi[0] += 1
        return c

    def _pt_prompt():
        """Dynamic prompt label showing active mode."""
        mode = _get_mode()
        parts = [("fg:" + _cur_bullet[0] + " bold", "\n  ○")]
        if mode:
            parts.append(("class:pt-mode", f" [{mode}]"))
        parts.append(("class:pt-arrow", "  › "))
        return FormattedText(parts)

    # ── Input loop — input always available, AI runs in worker ────────────────
    with _patch_stdout():
        while _running:
            try:
                _cur_bullet[0] = _BULLET_HEX[_bi[0] % len(_BULLET_HEX)]
                _bi[0] += 1
                raw = session.prompt(_pt_prompt).strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue

            # ── /first <payload> — priority insert at queue front ──────────────
            if raw.lower().startswith("/first "):
                payload = raw[7:].strip()
                if not payload:
                    _raw(f"  {DIM}Usage: /first <message or command>{RESET}\n")
                    continue
                bc = _bullet()
                _raw(f"  {bc}◆{RESET}  {WHITE}{sanitize(payload)}{RESET}  {AMBER}[FIRST]{RESET}\n")
                qsize = msg_queue.size()
                if qsize:
                    _raw(f"  {AMBER}↑ pushed to front  [was Q:{qsize}]{RESET}\n")
                msg_queue.put_first(payload)
                continue

            if raw.startswith("/"):
                _parts = raw.strip().split()
                _cmd0  = _parts[0].lower()
                _args0 = " ".join(_parts[1:])

                # Translate shortcut commands to natural language for the worker
                if _cmd0 == "/search":
                    if not _args0:
                        _raw(f"  {DIM}Usage: /search <query>{RESET}\n")
                        continue
                    qsize = msg_queue.size()
                    if qsize:
                        _raw(f"  {DIM}↓ queued [{qsize + 1}]{RESET}\n")
                    msg_queue.put(f"Search the web for: {_args0}")
                    continue

                if _cmd0 == "/research":
                    if not _args0:
                        _raw(f"  {DIM}Usage: /research <topic>{RESET}\n")
                        continue
                    qsize = msg_queue.size()
                    if qsize:
                        _raw(f"  {DIM}↓ queued [{qsize + 1}]{RESET}\n")
                    msg_queue.put(f"Research this topic in depth and write a complete, well-structured report: {_args0}")
                    continue

                if _cmd0 == "/book":
                    if not _args0:
                        _raw(f"  {DIM}Usage: /book <title or author>{RESET}\n")
                        continue
                    qsize = msg_queue.size()
                    if qsize:
                        _raw(f"  {DIM}↓ queued [{qsize + 1}]{RESET}\n")
                    msg_queue.put(f"Find and download this book: {_args0}")
                    continue

                custom = get_command(raw[1:].split()[0])
                if custom:
                    qsize = msg_queue.size()
                    if qsize:
                        _raw(f"  {DIM}↓ queued [{qsize + 1}]{RESET}\n")
                    msg_queue.put((custom["prompt"], raw))
                    continue
                if not handle_slash(raw):
                    _raw(f"  {CORAL}Unknown command{RESET}  {DIM}{raw}{RESET}  {CYAN}/help{RESET} {DIM}for help{RESET}\n")
                if not _running:
                    break
                continue

            if raw.lower() in ("exit", "quit", "bye"):
                handle_slash("/quit")
                break

            qsize = msg_queue.size()
            if qsize:
                _raw(f"  {DIM}↓ queued [{qsize + 1}]{RESET}\n")
            msg_queue.put(raw)

    msg_queue.put("__STOP__")
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
def _test_openrouter_connection() -> None:
    """Quick connectivity check on startup — prints result, never blocks."""
    try:
        import openai as _oai
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            _raw(f"  {RED}OpenRouter connection failed{RESET}\n\n")
            return
        client = _oai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://github.com/jarvis-ai", "X-Title": "Jarvis"},
        )
        client.chat.completions.create(
            model="meta-llama/llama-4-maverick",
            messages=[{"role": "user", "content": "say ok"}],
            max_tokens=5,
        )
        _raw(f"  {GREEN}OpenRouter connection ok{RESET}\n\n")
    except Exception:
        _raw(f"  {RED}OpenRouter connection failed{RESET}\n\n")


def main():
    print_banner()
    _test_openrouter_connection()

    if "--voice" in sys.argv:
        wake_word_mode()
    else:
        main_loop()

if __name__ == "__main__":
    main()
