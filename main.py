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
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

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
from tools.wiki import wiki_search
from tools.youtube import get_transcript as yt_transcript
from tools.scholar import search_papers
from tools.clipboard_mgr import start_tracking as _clip_start, get_history as _clip_history, paste_item as _clip_paste, clear_history as _clip_clear
from tools.todo import add_todo, list_todos, done_todo, remove_todo, clear_done as clear_done_todos
from tools.timer import start_timer as _start_timer
from core.stats import get_today as _stats_today, get_all as _stats_all
from core.error_log import log_error
from audio.tts_elevenlabs import tts_speak as _tts_speak, tts_speak_async as _tts_async, list_voices as _tts_voices, get_usage_summary as _tts_usage
from audio.stt_advanced import transcribe_file as _transcribe_file, listen_once as _listen_once
from tools.scheduler import (
    add_schedule as _sched_add, list_schedules as _sched_list,
    remove_schedule as _sched_remove, clear_schedules as _sched_clear,
    toggle_schedule as _sched_toggle, fmt_schedule_list as _sched_fmt,
    start_scheduler as _start_scheduler,
)
from tools.file_organizer import (
    organize_directory as _organize_dir, fmt_organize_result as _organize_fmt,
    undo_organize as _organize_undo, list_manifests as _organize_manifests,
)
from tools.image_tools import (
    analyze_image as _img_analyze,
    remove_bg as _img_removebg,
    upscale_image as _img_upscale,
    generate_image as _img_generate,
    color_grade as _img_grade,
    list_grade_styles as _grade_styles,
)
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
    "/first", "/cancel",
    "/search", "/research", "/book",
    "/wiki", "/stats", "/clips", "/clip",
    "/todo", "/timer", "/remind",
    "/yt", "/transcript", "/papers",
    "/speak", "/voices", "/tts",
    "/transcribe", "/listen",
    "/schedule", "/organize",
    "/imagine", "/imggen", "/removebg", "/upscale", "/imganalyze", "/grade",
}


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
    "wiki_search":         ("WIKI",     "cyan"),
    "yt_transcript":       ("YOUTUBE",  "red"),
    "search_papers":       ("SCHOLAR",  "blue"),
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
    "wiki_search":         CYAN,
    "yt_transcript":       CORAL,
    "search_papers":       BLUE,
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
    "wiki_search":         "searching Wikipedia...",
    "yt_transcript":       "fetching transcript...",
    "search_papers":       "searching papers...",
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
registry.register("wiki_search",          wiki_search)
registry.register("yt_transcript",        yt_transcript)
registry.register("search_papers",        search_papers)

# Start clipboard background tracker
_clip_start()

# Start scheduler — fires scheduled tasks by injecting them into msg_queue
# (msg_queue is defined later in the module; use a lambda to defer the reference)
def _sched_on_trigger(label: str, action: str) -> None:
    try:
        _raw(f"\n  {GOLD}◆ Scheduled task fired:{RESET}  {DIM}[{label}]{RESET}  {WHITE}{sanitize(action)}{RESET}\n")
        msg_queue.put(action)
    except Exception:
        pass

orchestrator = Orchestrator(tool_registry=registry)


# ── State ─────────────────────────────────────────────────────────────────────
_running      = True
_activated    = threading.Event()
_mode         = "text"
_abort_event  = threading.Event()   # set to cancel the current AI task (Ctrl+Q)
_worker_busy  = threading.Event()   # set while worker thread is processing

# ── Blessed UI state ──────────────────────────────────────────────────────────
import blessed as _blessed_mod
import re     as _re_mod
_term      = _blessed_mod.Terminal()
_out_buf  : list  = []          # permanent output lines (strings with ANSI)
_out_acc  : list  = [""]        # partial-line accumulator for _raw()
_stream   : list  = [""]        # live streaming text (shown while AI is typing)
_scroll   : list  = [0]         # scroll offset — 0 = pinned to bottom
_inp_buf  : list  = []          # current input characters
_inp_pos  : list  = [0]         # cursor position inside _inp_buf
_spin_lbl : list  = [""]        # spinner text shown in the status bar
_ui_active: list  = [False]     # True only after t.fullscreen() is entered
_out_lock  = threading.Lock()   # guards _out_buf / _out_acc
_rndr_lock = threading.Lock()   # serialises terminal writes
_ANSI_ESC  = _re_mod.compile(r'\x1b\[[0-9;]*[mABCDEFGHJKLMSTfnsuhlr]')
_last_render_t: list = [0.0]    # throttle: last render timestamp
_RENDER_INTERVAL = 0.033        # ~30 fps cap

# ── Raw stdout helpers ────────────────────────────────────────────────────────
def sanitize(t: str) -> str:
    return t.encode("utf-8", errors="replace").decode("utf-8")

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def _raw(text: str, end: str = "") -> None:
    """Buffer output into the blessed output area (never writes stdout directly)."""
    full = text + end
    chunks = full.split('\n')
    with _out_lock:
        _out_acc[0] += chunks[0]
        for chunk in chunks[1:]:
            _out_buf.append(_out_acc[0])
            _out_acc[0] = chunk
    _render()

def _clear_line() -> None:
    pass  # spinner clearing is handled by _render()

def _do_render() -> None:
    """Full terminal redraw: output area + gold divider + status bar + input bar."""
    try:
        w = max(_term.width  or 80, 40)
        h = max(_term.height or 24, 8)
    except Exception:
        return
    output_h = h - 4          # rows 1 .. h-4 for scrollable output

    # Collect all content lines
    with _out_lock:
        lines = list(_out_buf)
        if _out_acc[0]:
            lines.append(_out_acc[0])

    stream = _stream[0]
    if stream:
        for ln in stream.split('\n'):
            lines.append(ln)

    total   = len(lines)
    offset  = _scroll[0]
    end_i   = total - offset
    start_i = max(0, end_i - output_h)
    visible = lines[start_i:end_i]

    buf: list = ["\033[?25l"]   # hide cursor during redraw (VT100 enabled inside fullscreen)

    # ── Output zone ───────────────────────────────────────────────────────
    for i in range(output_h):
        buf.append(f"\033[{i+1};1H\033[K")
        if i < len(visible):
            ln   = visible[i]
            vlen = len(_ANSI_ESC.sub('', ln))
            buf.append(ln if vlen <= w else _ANSI_ESC.sub('', ln)[:w])

    # Scroll hint (top row, reverse video)
    if offset > 0:
        hint = f" ↑ {offset} lines above — End: jump to bottom "[:w]
        buf.append(f"\033[1;1H\033[7m{hint}\033[m")

    # ── Gold divider ──────────────────────────────────────────────────────
    buf.append(f"\033[{h-3};1H\033[K\033[33m{'─' * w}\033[m")

    # ── Input bar ─────────────────────────────────────────────────────────
    inp_str  = ''.join(_inp_buf)
    inp_disp = f" \033[1mYou\033[m\033[2m › \033[m\033[97m{inp_str}\033[m"
    buf.append(f"\033[{h-2};1H\033[K{inp_disp}")

    # ── Bottom gold border ────────────────────────────────────────────────
    buf.append(f"\033[{h-1};1H\033[K\033[33m{'─' * w}\033[m")

    # ── Status bar (below input border) ───────────────────────────────────
    mode_str = _get_mode() or "normal"
    try:
        qsize = msg_queue.size()
    except Exception:
        qsize = 0
    spin = _spin_lbl[0]
    try:
        mdl = orchestrator._api.current_model.split('/')[-1]
    except Exception:
        mdl = ""
    sb = (
        f" \033[1;33m⚡ Jarvis\033[m  "
        f"\033[96m[{mode_str}]\033[m  "
        f"\033[97m[Q:{qsize}]\033[m"
        + (f"  \033[2m{spin}\033[m" if spin else "")
        + (f"  \033[2m{mdl}\033[m" if mdl else "")
        + f"  \033[2mCtrl+Q: cancel\033[m"
    )
    buf.append(f"\033[{h};1H\033[K{sb}")

    # ── Reposition cursor inside the input bar, then restore visibility ──
    cur_col = min(7 + _inp_pos[0] + 1, w)  # " You › " = 7 visible chars; 1-based
    buf.append(f"\033[{h-2};{cur_col}H\033[?25h")

    sys.stdout.write(''.join(buf))
    sys.stdout.flush()

def _render(force: bool = False) -> None:
    """Thread-safe render — throttled to _RENDER_INTERVAL; no-op before fullscreen."""
    if not _ui_active[0]:
        return
    now = time.monotonic()
    if not force and (now - _last_render_t[0]) < _RENDER_INTERVAL:
        return
    if _rndr_lock.acquire(blocking=False):
        try:
            _last_render_t[0] = time.monotonic()
            _do_render()
        finally:
            _rndr_lock.release()

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
    _cmd_row("/wiki <topic>",         "Wikipedia lookup",                             GREEN)
    _cmd_row("/papers <query>",       "Search academic papers (Semantic Scholar)",    GREEN)
    _cmd_row("/yt <url>",             "Fetch YouTube transcript",                     GREEN)

    _section("TTS — Text to Speech", AMBER)
    _cmd_row("/speak <text>",          "Speak text aloud (ElevenLabs → OpenAI → edge-tts)", AMBER)
    _cmd_row("/speak --voice <name> <text>", "Use a specific voice",                 AMBER)
    _cmd_row("/speak --save <text>",   "Generate audio without playing",             AMBER)
    _cmd_row("/speak --file <path>",   "Read entire file aloud",                     AMBER)
    _cmd_row("/voices",                "List all available TTS voices",              AMBER)

    _section("STT — Transcription", CYAN)
    _cmd_row("/transcribe <file>",     "Transcribe an audio file",                   CYAN)
    _cmd_row("/transcribe <f> --translate",  "Translate to English while transcribing", CYAN)
    _cmd_row("/transcribe <f> --summary",    "Add bullet-point summary",            CYAN)
    _cmd_row("/transcribe <f> --speakers",   "Label speakers in transcript",        CYAN)
    _cmd_row("/transcribe <f> --lang <code>","Force language (e.g. fr, es, de)",   CYAN)
    _cmd_row("/listen",                "Record from mic and transcribe",             CYAN)
    _cmd_row("/listen --save",         "Record, transcribe, and save file",         CYAN)

    _section("Image Tools", VIOLET)
    _cmd_row("/imagine <prompt>",           "Generate image (Stability AI or Replicate SDXL)", VIOLET)
    _cmd_row("/imagine <p> --size WxH",     "Set output dimensions",                           VIOLET)
    _cmd_row("/imagine <p> --negative <n>", "Add negative prompt",                             VIOLET)
    _cmd_row("/imganalyze <file> [question]","Analyze/describe an image via AI vision",        VIOLET)
    _cmd_row("/removebg <file>",            "Remove image background (remove.bg)",             VIOLET)
    _cmd_row("/upscale <file> [2|4]",       "Upscale image 2x or 4x (Replicate Real-ESRGAN)", VIOLET)
    _cmd_row("/grade <file> <style>",       "Apply color grade (vintage, vivid, noir, …)",     VIOLET)
    _cmd_row("/grade styles",               "List available color grade styles",               VIOLET)

    _section("Scheduler", AMBER)
    _cmd_row("/schedule list",                   "Show all scheduled tasks",        AMBER)
    _cmd_row("/schedule add <lbl> <when> -- <action>", "Add a scheduled task",     AMBER)
    _cmd_row("/schedule remove <id>",            "Remove a schedule",               AMBER)
    _cmd_row("/schedule pause/resume <id>",      "Pause or resume a schedule",      AMBER)
    _cmd_row("/schedule clear",                  "Remove all schedules",            AMBER)

    _section("File Organizer", TEAL)
    _cmd_row("/organize <dir>",            "Sort files into subfolders by type",    TEAL)
    _cmd_row("/organize <dir> --dry-run",  "Preview — nothing is moved",            TEAL)
    _cmd_row("/organize <dir> --recursive","Include subdirectory files",            TEAL)
    _cmd_row("/organize undo",             "Reverse the last organize operation",   TEAL)

    _section("Utilities", GOLD)
    _cmd_row("/stats",                 "Token usage today + all-time",              GOLD)
    _cmd_row("/clips",                 "Clipboard history (last 20)",               GOLD)
    _cmd_row("/clip <n>",              "Paste clipboard item n back to clipboard",  GOLD)
    _cmd_row("/todo add <task>",       "Add a TODO item",                           GOLD)
    _cmd_row("/todo list",             "Show all todos",                            GOLD)
    _cmd_row("/todo done <n>",         "Mark todo as done",                         GOLD)
    _cmd_row("/timer <duration> [lbl]","Countdown timer (5m, 1h30m, etc.)",        GOLD)

    _section("Task History", VIOLET)
    _cmd_row("/memory tasks",         "Show last 20 task queries",                    VIOLET)
    _cmd_row("/memory tasks clear",   "Clear task history",                           VIOLET)

    _section("Priority Queue", CORAL)
    _cmd_row("/first <message>",     "Insert message at front of queue (runs next)", CORAL)

    _section("Keyboard Shortcuts", CYAN)
    _cmd_row("Ctrl+Q",               "Cancel running task  /  quit (if idle)",    CYAN)
    _cmd_row("/cancel",              "Cancel current task (keeps queue)",          CYAN)
    _cmd_row("/cancel --all",        "Cancel task + clear entire queue",           CYAN)

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
    """Animate the status bar spinner — never writes to stdout directly."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        _spin_lbl[0] = f"{frames[i % len(frames)]}  {status_ref[0]}"
        _render()
        i += 1
        time.sleep(0.08)
    _spin_lbl[0] = ""
    _render()

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
            _stream[0] = ""
            header_printed = True

        full += token
        _stream[0] = full
        _render()

    if not stop_spin.is_set():
        stop_spin.set()
        spin_thread.join()

    # Move streaming text to permanent output, clear the live buffer
    if header_printed and full:
        with _out_lock:
            for ln in full.split('\n'):
                _out_buf.append(ln)
            _out_buf.append("")          # blank spacer after response
        _stream[0] = ""
    else:
        _stream[0] = ""

    _render(force=True)
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


# ── /stats ───────────────────────────────────────────────────────────────────
def cmd_stats():
    s = _stats_today()
    all_data = _stats_all()
    all_tokens = sum(
        v.get("prompt", 0) + v.get("completion", 0)
        for v in all_data.get("tokens", {}).values()
    )
    _raw(f"\n  {AMBER}{BOLD}Usage Stats{RESET}\n")
    _raw(f"  {GOLD}{'─' * 40}{RESET}\n")
    _raw(f"  {WHITE}Today ({s['date']}){RESET}\n")
    _raw(f"    Requests   {CYAN}{s['requests']}{RESET}\n")
    _raw(f"    Prompt     {CYAN}{s['prompt']:,}{RESET} tokens\n")
    _raw(f"    Completion {CYAN}{s['completion']:,}{RESET} tokens\n")
    _raw(f"    Total      {AMBER}{s['total']:,}{RESET} tokens\n")
    _raw(f"\n  {DIM}All-time: {all_tokens:,} tokens{RESET}\n\n")


# ── /clips ────────────────────────────────────────────────────────────────────
def cmd_clips(args: list):
    if args and args[0] == "clear":
        n = _clip_clear()
        _raw(f"  {DIM}Cleared {n} clipboard entries.{RESET}\n\n")
        return
    history = _clip_history()
    if not history:
        _raw(f"  {DIM}Clipboard history empty.{RESET}\n\n")
        return
    _raw(f"\n  {CYAN}{BOLD}Clipboard History  ({len(history)}){RESET}\n")
    _raw(f"  {GOLD}{'─' * 40}{RESET}\n")
    for i, item in enumerate(reversed(history), 1):
        preview = item.replace('\n', ' ')[:70]
        _raw(f"  {CYAN}{i:>2}.{RESET}  {WHITE}{sanitize(preview)}{RESET}\n")
    _raw(f"\n  {DIM}/clip <n> to paste item{RESET}\n\n")


# ── /todo ─────────────────────────────────────────────────────────────────────
def cmd_todo(args: list):
    sub = args[0].lower() if args else "list"

    if sub == "add" and len(args) > 1:
        task = " ".join(args[1:])
        priority = "med"
        if task.lower().endswith((" high", " med", " low")):
            *parts, priority = task.split()
            task = " ".join(parts)
        item = add_todo(task, priority)
        _p = {"high": CORAL, "med": AMBER, "low": DIM}.get(item["priority"], DIM)
        _raw(f"  {GREEN}✓{RESET}  Added #{item['id']}  {_p}[{item['priority'].upper()}]{RESET}  {WHITE}{sanitize(task)}{RESET}\n\n")
        return

    if sub == "done" and len(args) > 1:
        try:
            ok, task = done_todo(int(args[1]))
            if ok:
                _raw(f"  {GREEN}✓  Done:{RESET}  {DIM}{sanitize(task)}{RESET}\n\n")
            else:
                _raw(f"  {CORAL}{task}{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /todo done <number>{RESET}\n")
        return

    if sub == "remove" and len(args) > 1:
        try:
            ok, task = remove_todo(int(args[1]))
            _raw(f"  {ok and GREEN or CORAL}{'Removed' if ok else task}:{RESET}  {DIM}{sanitize(task) if ok else ''}{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /todo remove <number>{RESET}\n")
        return

    if sub == "clear":
        n = clear_done_todos()
        _raw(f"  {DIM}Cleared {n} completed tasks.{RESET}\n\n")
        return

    # Default: list
    items = list_todos()
    if not items:
        _raw(f"  {DIM}No pending tasks. Add one: /todo add <task>{RESET}\n\n")
        return
    _raw(f"\n  {VIOLET}{BOLD}TODO  ({len(items)} pending){RESET}\n")
    _raw(f"  {GOLD}{'─' * 40}{RESET}\n")
    _PCOL = {"high": CORAL, "med": AMBER, "low": DIM}
    for i, item in enumerate(items, 1):
        pc = _PCOL.get(item.get("priority", "med"), DIM)
        _raw(f"  {VIOLET}{i:>2}.{RESET}  {pc}[{item['priority'].upper()}]{RESET}  {WHITE}{sanitize(item['task'])}{RESET}\n")
    _raw(f"\n  {DIM}/todo done <n>  /todo remove <n>  /todo clear{RESET}\n\n")


# ── /timer ────────────────────────────────────────────────────────────────────
def cmd_timer(args: list):
    if not args:
        _raw(f"  {DIM}Usage: /timer <duration> [label]  e.g. /timer 5m coffee{RESET}\n\n")
        return
    duration_str = args[0]
    label = " ".join(args[1:]) if len(args) > 1 else "Timer"

    def _on_done(lbl):
        try:
            send_notification(f"⏰ {lbl}", "Time's up!")
        except Exception:
            pass
        _raw(f"\n  {AMBER}⏰  Timer done:{RESET}  {WHITE}{sanitize(lbl)}{RESET}\n")
        _render(force=True)

    ok, human = _start_timer(duration_str, label, _on_done)
    if ok:
        _raw(f"  {CYAN}⏱  Timer set:{RESET}  {WHITE}{sanitize(label)}{RESET}  {DIM}({human}){RESET}\n\n")
    else:
        _raw(f"  {CORAL}{human}{RESET}\n\n")


# ── /speak ────────────────────────────────────────────────────────────────────
def cmd_speak(args: list, raw_text: str = ""):
    """
    /speak <text>
    /speak --voice <name> <text>
    /speak --save <text>
    /speak --file <path>
    """
    if not args:
        _raw(f"  {DIM}Usage: /speak <text>  or  /speak --voice <name> <text>{RESET}\n\n")
        return

    voice = ""
    save  = False
    text  = ""

    i = 0
    while i < len(args):
        if args[i] == "--voice" and i + 1 < len(args):
            voice = args[i + 1]; i += 2
        elif args[i] == "--save":
            save = True; i += 1
        elif args[i] == "--file" and i + 1 < len(args):
            try:
                text = open(args[i + 1], encoding="utf-8").read()
            except Exception as e:
                _raw(f"  {CORAL}Could not read file: {e}{RESET}\n\n")
                return
            i += 2
        else:
            text = " ".join(args[i:]); break

    if not text.strip():
        _raw(f"  {DIM}No text to speak.{RESET}\n\n")
        return

    char_count = len(text)
    _raw(f"  {DIM}Speaking {char_count:,} chars via TTS...{RESET}\n")

    def _do():
        ok, result = _tts_speak(text, voice=voice, save=save)
        if ok:
            if save:
                _raw(f"  {GREEN}✓  Saved:{RESET}  {DIM}{result}{RESET}\n\n")
            else:
                _raw(f"  {GREEN}✓  Done{RESET}\n\n")
        else:
            _raw(f"  {CORAL}TTS failed: {result}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /transcribe ───────────────────────────────────────────────────────────────
def cmd_transcribe(args: list):
    """
    /transcribe <file>
    /transcribe <file> --translate
    /transcribe <file> --summary
    /transcribe <file> --speakers
    /transcribe <file> --lang <code>
    Flags can be combined.
    """
    if not args:
        _raw(
            f"\n  {BOLD}Usage:{RESET}  /transcribe <audio-file> [flags]\n"
            f"  {DIM}--translate    translate to English\n"
            f"  --summary      add bullet-point summary (AssemblyAI)\n"
            f"  --speakers     label speakers (AssemblyAI)\n"
            f"  --lang <code>  e.g. fr, es, de (auto-detect if omitted)\n"
            f"  --no-save      don't save to data/transcripts/{RESET}\n\n"
        )
        return

    translate = False
    summarize = False
    speakers  = False
    save      = True
    language  = None
    file_path = None

    i = 0
    while i < len(args):
        if args[i] == "--translate":
            translate = True; i += 1
        elif args[i] == "--summary":
            summarize = True; i += 1
        elif args[i] == "--speakers":
            speakers = True; i += 1
        elif args[i] == "--no-save":
            save = False; i += 1
        elif args[i] == "--lang" and i + 1 < len(args):
            language = args[i + 1]; i += 2
        elif file_path is None:
            file_path = args[i]; i += 1
        else:
            i += 1

    if not file_path:
        _raw(f"  {CORAL}No file specified.{RESET}\n"); return

    if not os.path.exists(file_path):
        _raw(f"  {CORAL}File not found: {file_path}{RESET}\n"); return

    flags_str = " ".join(
        f for f, v in [
            ("translate", translate), ("summary", summarize),
            ("speakers", speakers), (f"lang={language}", bool(language)),
        ] if v
    )
    _raw(f"  {DIM}Transcribing {os.path.basename(file_path)}"
         f"{' [' + flags_str + ']' if flags_str else ''}...{RESET}\n")

    def _do():
        ok, text, saved = _transcribe_file(
            file_path, translate=translate, summarize=summarize,
            speakers=speakers, language=language, save=save,
        )
        if ok:
            _raw(f"\n{sanitize(text)}\n\n")
            if saved:
                _raw(f"  {GREEN}✓  Saved:{RESET}  {DIM}{saved}{RESET}\n\n")
        else:
            _raw(f"  {CORAL}Transcription failed: {sanitize(text)}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /listen ────────────────────────────────────────────────────────────────────
def cmd_listen(args: list):
    """
    /listen           — record from mic and transcribe
    /listen --save    — record, transcribe, save to data/transcripts/
    /listen --lang <code>
    """
    save_file = "--save" in args
    language  = None
    if "--lang" in args:
        idx = args.index("--lang")
        if idx + 1 < len(args):
            language = args[idx + 1]

    _raw(f"  {DIM}Listening... (speak, then pause to stop){RESET}\n")

    def _do():
        ok, text, saved = _listen_once(save=save_file, language=language)
        if ok:
            _raw(f"\n  {CYAN}◈  Heard:{RESET}  {WHITE}{sanitize(text)}{RESET}\n")
            if saved:
                _raw(f"  {GREEN}✓  Saved:{RESET}  {DIM}{saved}{RESET}\n\n")
            else:
                _raw("\n")
        else:
            _raw(f"  {CORAL}Listen failed: {sanitize(text)}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /schedule ─────────────────────────────────────────────────────────────────
def cmd_schedule(args: list):
    """
    /schedule list
    /schedule add <label> <when> -- <action>
        when:   "every 30m" | "every 2h" | "daily 09:00" | "hourly" | "2025-12-31 08:00"
        action: message to send to Jarvis when triggered
    /schedule remove <id>
    /schedule pause <id>
    /schedule resume <id>
    /schedule clear
    """
    if not args or args[0] in ("list", "ls", ""):
        entries = _sched_list()
        _raw(f"\n  {BOLD}{CYAN}Scheduled Tasks{RESET}\n")
        _raw(f"  {DIM}{_sched_fmt(entries)}{RESET}\n\n")
        return

    sub = args[0].lower()

    if sub == "remove" and len(args) > 1:
        try:
            ok = _sched_remove(int(args[1]))
            if ok:
                _raw(f"  {GREEN}✓  Removed schedule #{args[1]}.{RESET}\n\n")
            else:
                _raw(f"  {CORAL}No schedule with id {args[1]}.{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /schedule remove <id>{RESET}\n")
        return

    if sub in ("pause", "disable") and len(args) > 1:
        try:
            _sched_toggle(int(args[1]), False)
            _raw(f"  {AMBER}◆  Schedule #{args[1]} paused.{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /schedule pause <id>{RESET}\n")
        return

    if sub in ("resume", "enable") and len(args) > 1:
        try:
            _sched_toggle(int(args[1]), True)
            _raw(f"  {GREEN}✓  Schedule #{args[1]} resumed.{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /schedule resume <id>{RESET}\n")
        return

    if sub == "clear":
        n = _sched_clear()
        _raw(f"  {AMBER}◆  Cleared {n} scheduled task(s).{RESET}\n\n")
        return

    if sub == "add":
        # /schedule add <label> <when...> -- <action...>
        rest = args[1:]
        rest_str = " ".join(rest)
        if "--" not in rest_str:
            _raw(
                f"  {DIM}Usage: /schedule add <label> <when> -- <action>\n"
                f"  Examples:\n"
                f"    /schedule add morning daily 09:00 -- What's on my agenda today?\n"
                f"    /schedule add ping every 30m -- search web for AI news\n"
                f"    /schedule add once 2025-12-31 23:59 -- Happy new year reminder{RESET}\n\n"
            )
            return
        sep_idx = rest_str.index(" -- ")
        before  = rest_str[:sep_idx].strip()
        action  = rest_str[sep_idx + 4:].strip()
        tokens  = before.split()
        if not tokens:
            _raw(f"  {CORAL}No label/when given.{RESET}\n"); return
        label   = tokens[0]
        when    = " ".join(tokens[1:]) if len(tokens) > 1 else tokens[0]
        once    = not any(when.lower().startswith(p) for p in ("every ", "daily ", "hourly"))
        try:
            entry = _sched_add(label, when, action, once=once)
            nr = entry.get("next_run", "?")
            if nr and nr != "?":
                import datetime as _dt
                try:
                    nr = _dt.datetime.fromisoformat(nr).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            _raw(f"  {GREEN}✓  Schedule #{entry['id']} '{label}' — next: {nr}{RESET}\n\n")
        except Exception as e:
            _raw(f"  {CORAL}Failed to add schedule: {e}{RESET}\n\n")
        return

    _raw(f"  {DIM}Usage: /schedule [list|add|remove|pause|resume|clear]{RESET}\n")


# ── /organize ─────────────────────────────────────────────────────────────────
def cmd_organize(args: list):
    """
    /organize <directory>            — sort files into subfolders by type
    /organize <directory> --dry-run  — preview without moving anything
    /organize <directory> --recursive— include subdirectory files
    /organize undo                   — reverse the last organize operation
    /organize undo <manifest_path>   — reverse a specific manifest
    """
    if not args:
        _raw(
            f"\n  {BOLD}Usage:{RESET}  /organize <directory> [flags]\n"
            f"  {DIM}--dry-run    Preview only — nothing is moved\n"
            f"  --recursive  Include files in subdirectories\n"
            f"  undo         Reverse last organize operation{RESET}\n\n"
        )
        return

    if args[0].lower() == "undo":
        manifest = args[1] if len(args) > 1 else None
        _raw(f"  {DIM}Undoing last organize...{RESET}\n")
        result = _organize_undo(manifest)
        if "error" in result:
            _raw(f"  {CORAL}Error: {result['error']}{RESET}\n\n")
        else:
            _raw(f"  {GREEN}✓  Restored {result['restored']} file(s)"
                 f"{', ' + str(result['failed']) + ' failed' if result['failed'] else ''}{RESET}\n\n")
        return

    directory   = args[0]
    dry_run     = "--dry-run" in args or "--preview" in args
    recursive   = "--recursive" in args or "-r" in args

    if not os.path.isdir(directory):
        _raw(f"  {CORAL}Not a valid directory: {directory}{RESET}\n"); return

    mode_str = "[DRY RUN] " if dry_run else ""
    _raw(f"  {DIM}{mode_str}Organizing {directory}...{RESET}\n")

    def _do():
        try:
            result = _organize_dir(directory, dry_run=dry_run, recursive=recursive)
            _raw(f"\n{_organize_fmt(result)}\n\n")
        except Exception as e:
            _raw(f"  {CORAL}Organize failed: {e}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /imagine (image generation) ───────────────────────────────────────────────
def cmd_imagine(args: list, raw_text: str = ""):
    """
    /imagine <prompt>
    /imagine <prompt> --negative <negative_prompt>
    /imagine <prompt> --size 512x512
    /imagine <prompt> --steps 50
    /imagine <prompt> --provider stability|replicate
    """
    if not args:
        _raw(f"  {DIM}Usage: /imagine <prompt> [--negative <neg>] [--size WxH] [--steps N] [--provider stability|replicate]{RESET}\n\n")
        return

    negative = ""
    width    = 1024
    height   = 1024
    steps    = 30
    provider = "auto"
    prompt_parts: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--negative" and i + 1 < len(args):
            negative = args[i + 1]; i += 2
        elif args[i] == "--size" and i + 1 < len(args):
            try:
                w, h = args[i + 1].lower().split("x")
                width, height = int(w), int(h)
            except Exception:
                pass
            i += 2
        elif args[i] == "--steps" and i + 1 < len(args):
            try:
                steps = int(args[i + 1])
            except Exception:
                pass
            i += 2
        elif args[i] == "--provider" and i + 1 < len(args):
            provider = args[i + 1].lower(); i += 2
        else:
            prompt_parts.append(args[i]); i += 1

    prompt = " ".join(prompt_parts) or raw_text
    if not prompt.strip():
        _raw(f"  {CORAL}No prompt given.{RESET}\n"); return

    _raw(f"  {DIM}Generating image: \"{prompt[:60]}{'…' if len(prompt) > 60 else ''}\"...{RESET}\n")

    def _do():
        ok, result = _img_generate(prompt, negative_prompt=negative,
                                   width=width, height=height,
                                   steps=steps, provider=provider)
        if ok:
            _raw(f"  {GREEN}✓  Image saved:{RESET}  {DIM}{result}{RESET}\n\n")
        else:
            _raw(f"  {CORAL}Generation failed: {sanitize(result)}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /removebg ────────────────────────────────────────────────────────────────
def cmd_removebg(args: list):
    if not args:
        _raw(f"  {DIM}Usage: /removebg <image-path>{RESET}\n"); return
    path = " ".join(args)
    _raw(f"  {DIM}Removing background from {os.path.basename(path)}...{RESET}\n")

    def _do():
        ok, result = _img_removebg(path)
        if ok:
            _raw(f"  {GREEN}✓  Saved:{RESET}  {DIM}{result}{RESET}\n\n")
        else:
            _raw(f"  {CORAL}Failed: {sanitize(result)}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /upscale ─────────────────────────────────────────────────────────────────
def cmd_upscale(args: list):
    """
    /upscale <image-path> [2|4]   (default 4x)
    """
    if not args:
        _raw(f"  {DIM}Usage: /upscale <image-path> [2|4]{RESET}\n"); return
    scale = 4
    if len(args) >= 2:
        try:
            scale = int(args[-1])
            path  = " ".join(args[:-1])
        except ValueError:
            path = " ".join(args)
    else:
        path = args[0]

    _raw(f"  {DIM}Upscaling {os.path.basename(path)} {scale}x...{RESET}\n")

    def _do():
        ok, result = _img_upscale(path, scale=scale)
        if ok:
            _raw(f"  {GREEN}✓  Saved:{RESET}  {DIM}{result}{RESET}\n\n")
        else:
            _raw(f"  {CORAL}Upscale failed: {sanitize(result)}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /imganalyze ───────────────────────────────────────────────────────────────
def cmd_imganalyze(args: list):
    """
    /imganalyze <image-path> [question...]
    """
    if not args:
        _raw(f"  {DIM}Usage: /imganalyze <image-path> [question]{RESET}\n"); return

    path     = args[0]
    question = " ".join(args[1:]) if len(args) > 1 else ""
    _raw(f"  {DIM}Analyzing image...{RESET}\n")

    def _do():
        result = _img_analyze(path, question=question)
        _raw(f"\n{sanitize(result)}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


# ── /grade ────────────────────────────────────────────────────────────────────
def cmd_grade(args: list):
    """
    /grade <image-path> <style>
    /grade styles — list available styles
    """
    if not args or (len(args) == 1 and args[0].lower() in ("styles", "list")):
        styles = ", ".join(_grade_styles())
        _raw(f"  {CYAN}Available styles:{RESET}  {WHITE}{styles}{RESET}\n\n")
        return

    if len(args) < 2:
        _raw(f"  {DIM}Usage: /grade <image-path> <style>  e.g. /grade photo.jpg vintage{RESET}\n"); return

    path  = args[0]
    style = args[1]
    _raw(f"  {DIM}Applying '{style}' grade to {os.path.basename(path)}...{RESET}\n")

    def _do():
        ok, result = _img_grade(path, style)
        if ok:
            _raw(f"  {GREEN}✓  Saved:{RESET}  {DIM}{result}{RESET}\n\n")
        else:
            _raw(f"  {CORAL}Failed: {sanitize(result)}{RESET}\n\n")
        _render(force=True)

    threading.Thread(target=_do, daemon=True).start()


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
    if cmd == "/cancel":
        cleared = 0
        if args and args[0] == "--all":
            cleared = msg_queue.clear()
        if _worker_busy.is_set():
            _abort_event.set()
            if cleared:
                _raw(f"  {CORAL}⊘  Task cancelled. {cleared} queued task(s) cleared.{RESET}\n")
            else:
                _raw(f"  {CORAL}⊘  Cancelling current task...{RESET}\n")
        elif cleared:
            _raw(f"  {AMBER}◆  Queue cleared ({cleared} task(s) removed).{RESET}\n")
        else:
            _raw(f"  {DIM}Nothing running. Use /cancel --all to also clear the queue.{RESET}\n")
        return True
    if cmd == "/stats":
        cmd_stats(); return True
    if cmd == "/clips":
        cmd_clips(args); return True
    if cmd == "/clip":
        if not args:
            _raw(f"  {DIM}Usage: /clip <n>{RESET}\n"); return True
        try:
            text = _clip_paste(int(args[0]))
            _raw(f"  {CYAN}Copied to clipboard:{RESET}  {WHITE}{sanitize(text[:80])}{RESET}\n\n")
        except ValueError:
            _raw(f"  {DIM}Usage: /clip <number>{RESET}\n")
        return True
    if cmd == "/todo":
        cmd_todo(args); return True
    if cmd in ("/timer", "/remind"):
        cmd_timer(args); return True
    if cmd in ("/speak", "/tts"):
        cmd_speak(args, " ".join(args)); return True
    if cmd == "/voices":
        _raw(f"\n{sanitize(_tts_voices())}\n\n"); return True
    if cmd == "/wiki":
        if not args:
            _raw(f"  {DIM}Usage: /wiki <topic>{RESET}\n"); return True
        msg_queue.put(f"Look up on Wikipedia: {' '.join(args)}")
        return True
    if cmd in ("/yt", "/transcript"):
        if not args:
            _raw(f"  {DIM}Usage: /yt <youtube-url-or-id>{RESET}\n"); return True
        msg_queue.put(f"Get the YouTube transcript for: {args[0]}")
        return True
    if cmd == "/papers":
        if not args:
            _raw(f"  {DIM}Usage: /papers <query>{RESET}\n"); return True
        msg_queue.put(f"Search academic papers on Semantic Scholar for: {' '.join(args)}")
        return True
    if cmd == "/transcribe":
        cmd_transcribe(args); return True
    if cmd == "/listen":
        cmd_listen(args); return True
    if cmd == "/schedule":
        cmd_schedule(args); return True
    if cmd == "/organize":
        cmd_organize(args); return True
    if cmd in ("/imagine", "/imggen"):
        cmd_imagine(args, raw_text=" ".join(args)); return True
    if cmd == "/removebg":
        cmd_removebg(args); return True
    if cmd == "/upscale":
        cmd_upscale(args); return True
    if cmd == "/imganalyze":
        cmd_imganalyze(args); return True
    if cmd == "/grade":
        cmd_grade(args); return True
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

    def clear(self) -> int:
        with self._lock:
            n = len(self._d)
            self._d.clear()
            self._ev.clear()
            return n

msg_queue = _PriorityDeque()   # module-level so _do_render() can read queue size

# ── Main loop ─────────────────────────────────────────────────────────────────
def main_loop():
    global _running, _mode

    # Enable native VT100 on Windows via CONOUT$ (more reliable than STD_OUTPUT_HANDLE)
    if sys.platform == "win32":
        try:
            import ctypes, ctypes.wintypes
            k32 = ctypes.windll.kernel32
            # Open the real console output handle — works even when stdout is redirected/wrapped
            h = k32.CreateFileW(
                "CONOUT$", 0x40000000, 3, None, 3, 0, None
            )  # GENERIC_WRITE | FILE_SHARE_READ|WRITE | OPEN_EXISTING
            if h != ctypes.wintypes.HANDLE(-1).value:
                m = ctypes.c_ulong()
                k32.GetConsoleMode(h, ctypes.byref(m))
                k32.SetConsoleMode(h, m.value | 4)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                k32.CloseHandle(h)
        except Exception:
            pass
        # Now that VT100 is enabled natively, stop colorama from converting sequences —
        # let ANSI codes pass through directly to the console.
        try:
            colorama.deinit()
        except Exception:
            pass

    import queue as _queue
    tg_queue: _queue.Queue = _queue.Queue()

    # ── Telegram ──────────────────────────────────────────────────────────────
    if _telegram.enabled:
        _telegram.start(tg_queue)
    else:
        _raw(f"  {DIM}Telegram not configured.{RESET}\n")

    _pending_suggestions: list = []
    _suggestions_lock = threading.Lock()

    def _queue_suggestions_after_delay(delay: float = 2.5):
        import time as _t; _t.sleep(delay)
        suggs = pop_suggestions()
        if suggs:
            with _suggestions_lock:
                _pending_suggestions.extend(suggs)

    def _flush_suggestions():
        with _suggestions_lock:
            suggs = list(_pending_suggestions); _pending_suggestions.clear()
        for s in suggs:
            _raw(f"  {VIOLET}✦ LEARN{RESET}  {WHITE}{sanitize(s)}{RESET}\n")
            _raw(f"  {DIM}/learn save <n>  — promote to a permanent skill{RESET}\n")

    # ── Telegram processor ────────────────────────────────────────────────────
    def _tg_processor():
        while _running:
            try:
                item = tg_queue.get(timeout=0.3)
            except _queue.Empty:
                continue
            if item is None:
                break
            user_text, tg_chat_id = item
            _raw(f"  {GOLD}[TG]{RESET}  {WHITE}{sanitize(user_text)}{RESET}\n")
            response = ask_streaming(user_text)
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            extract_and_store_async(user_text, response)
            threading.Thread(target=_queue_suggestions_after_delay, daemon=True).start()
            if _telegram.enabled:
                _telegram.send(tg_chat_id, response)

    if _telegram.enabled:
        threading.Thread(target=_tg_processor, daemon=True, name="TGProcessor").start()

    # ── Message worker ─────────────────────────────────────────────────────────
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
            # Show next-task hint if queue is non-empty
            next_items = msg_queue.peek()
            if next_items:
                nxt = next_items[0]
                preview = (nxt[1] if isinstance(nxt, tuple) else str(nxt))[:60]
                _raw(f"  {DIM}→ Running next queued task: \"{sanitize(preview)}\"{RESET}\n")

    threading.Thread(target=_worker, daemon=True, name="MsgWorker").start()

    # ── Submit helper — called when user presses Enter ─────────────────────────
    def _submit():
        raw = ''.join(_inp_buf).strip()
        _inp_buf.clear()
        _inp_pos[0] = 0
        if not raw:
            _render()
            return

        # Pin to bottom so echoed input + response appear just above the input bar
        _scroll[0] = 0
        # Echo the input into the output area
        _raw(f" {CYAN}○{RESET} {WHITE}{sanitize(raw)}{RESET}\n")

        if raw.lower().startswith("/first "):
            payload = raw[7:].strip()
            if not payload:
                _raw(f"  {DIM}Usage: /first <message or command>{RESET}\n"); return
            _raw(f"  {GOLD}◆{RESET}  {WHITE}{sanitize(payload)}{RESET}  {AMBER}[FIRST]{RESET}\n")
            qsize = msg_queue.size()
            if qsize:
                _raw(f"  {AMBER}↑ pushed to front  [was Q:{qsize}]{RESET}\n")
            msg_queue.put_first(payload)
            return

        if raw.startswith("/"):
            _parts = raw.strip().split()
            _cmd0  = _parts[0].lower()
            _args0 = " ".join(_parts[1:])

            if _cmd0 == "/search":
                if not _args0:
                    _raw(f"  {DIM}Usage: /search <query>{RESET}\n"); return
                qsize = msg_queue.size()
                if qsize: _raw(f"  {DIM}↓ queued [{qsize+1}]{RESET}\n")
                msg_queue.put(f"Search the web for: {_args0}"); return

            if _cmd0 == "/research":
                if not _args0:
                    _raw(f"  {DIM}Usage: /research <topic>{RESET}\n"); return
                qsize = msg_queue.size()
                if qsize: _raw(f"  {DIM}↓ queued [{qsize+1}]{RESET}\n")
                msg_queue.put(f"Research this topic in depth and write a complete, well-structured report: {_args0}"); return

            if _cmd0 == "/book":
                if not _args0:
                    _raw(f"  {DIM}Usage: /book <title or author>{RESET}\n"); return
                qsize = msg_queue.size()
                if qsize: _raw(f"  {DIM}↓ queued [{qsize+1}]{RESET}\n")
                msg_queue.put(f"Find and download this book: {_args0}"); return

            custom = get_command(raw[1:].split()[0])
            if custom:
                qsize = msg_queue.size()
                if qsize: _raw(f"  {DIM}↓ queued [{qsize+1}]{RESET}\n")
                msg_queue.put((custom["prompt"], raw)); return

            if not handle_slash(raw):
                _raw(f"  {CORAL}Unknown command{RESET}  {DIM}{raw}{RESET}  {CYAN}/help{RESET} {DIM}for help{RESET}\n")
            return

        if raw.lower() in ("exit", "quit", "bye"):
            handle_slash("/quit"); return

        qsize = msg_queue.size()
        if qsize:
            _raw(f"  {DIM}↓ queued [{qsize+1}]{RESET}\n")
        msg_queue.put(raw)

    # ── Blessed two-zone input loop ────────────────────────────────────────────
    t = _term
    _last_sz = [t.width, t.height]

    # Redirect stderr to devnull for the TUI session — any stray library
    # print()/warn() to stderr would corrupt the blessed layout.
    _real_stderr = sys.stderr
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

    with t.fullscreen(), t.cbreak():
        _ui_active[0] = True
        _render()

        while _running:
            key = t.inkey(timeout=0.05)

            # Resize detection (no SIGWINCH on Windows — poll instead)
            nw, nh = t.width, t.height
            if nw != _last_sz[0] or nh != _last_sz[1]:
                _last_sz[0] = nw; _last_sz[1] = nh
                _render()

            if not key:
                continue

            kc = key.code
            ks = str(key)

            if kc == t.KEY_ENTER or ks in ('\r', '\n'):
                _submit()

            elif kc == t.KEY_BACKSPACE or ks in ('\x7f', '\x08'):
                if _inp_pos[0] > 0:
                    _inp_buf.pop(_inp_pos[0] - 1)
                    _inp_pos[0] -= 1
                    _render()

            elif kc == t.KEY_DELETE:
                if _inp_pos[0] < len(_inp_buf):
                    _inp_buf.pop(_inp_pos[0]); _render()

            elif kc == t.KEY_LEFT:
                if _inp_pos[0] > 0:
                    _inp_pos[0] -= 1; _render()

            elif kc == t.KEY_RIGHT:
                if _inp_pos[0] < len(_inp_buf):
                    _inp_pos[0] += 1; _render()

            elif kc == t.KEY_HOME:
                _inp_pos[0] = 0; _render()

            elif kc == t.KEY_PGUP:
                out_h = max(t.height - 4, 1)
                with _out_lock: max_s = max(0, len(_out_buf) - out_h)
                _scroll[0] = min(_scroll[0] + out_h, max_s); _render()

            elif kc == t.KEY_PGDN:
                out_h = max(t.height - 4, 1)
                _scroll[0] = max(0, _scroll[0] - out_h); _render()

            elif kc == t.KEY_UP:
                with _out_lock: max_s = max(0, len(_out_buf) - 1)
                _scroll[0] = min(_scroll[0] + 3, max_s); _render()

            elif kc == t.KEY_DOWN:
                _scroll[0] = max(0, _scroll[0] - 3); _render()

            elif kc == t.KEY_END:
                _scroll[0] = 0
                _inp_pos[0] = len(_inp_buf); _render()

            elif ks == '\x11':   # Ctrl+Q
                if _worker_busy.is_set():
                    _abort_event.set()
                    _raw(f"  {CORAL}⊘  Cancelling task...{RESET}\n")
                else:
                    _running = False; break

            elif ks == '\x03':   # Ctrl+C
                _running = False; break

            elif not key.is_sequence and ks.isprintable():
                _inp_buf.insert(_inp_pos[0], ks)
                _inp_pos[0] += 1; _render()

    msg_queue.put("__STOP__")
    if _telegram.enabled:
        tg_queue.put(None)

    sys.stderr.close()
    sys.stderr = _real_stderr

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
    _start_scheduler(_sched_on_trigger)

    if "--voice" in sys.argv:
        wake_word_mode()
    else:
        main_loop()

if __name__ == "__main__":
    main()
