"""
Jarvis AI - Main Entry Point
Default: text mode.  Voice input: /voice.  Help: /help
"""
import os, sys, threading, time, io, json, httpx

# ── Silence persistent library warnings (like HF Hub) ────────────────────────
_original_stderr = sys.stderr
sys.stderr = open(os.devnull, 'w')

# ── UTF-8 + silence warnings ─────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

import warnings; warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

import colorama
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
from tools.video_gen import text_to_video as _vid_text, image_to_video as _vid_image
from tools.ai_detection import detect_image as _det_image, detect_text as _det_text, fmt_detection_result as _det_fmt
from tools.n8n_bridge import (
    trigger_workflow as _n8n_trigger, add_shortcut as _n8n_add,
    remove_shortcut as _n8n_remove, list_shortcuts as _n8n_list,
    n8n_ping as _n8n_ping, n8n_api_list_workflows as _n8n_workflows,
    parse_kv_args as _n8n_parse_kv,
)
from core.self_evolution import (
    get_gaps as _evo_gaps, research_tool_idea as _evo_research,
    build_tool as _evo_build, list_evolved_tools as _evo_list,
    undo_evolved_tool as _evo_undo, record_gap as _evo_record_gap,
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
AMBER    = "\033[93m"
GOLD     = "\033[33m"
CYAN     = "\033[96m"
BLUE     = "\033[94m"
VIOLET   = "\033[95m"
GREEN    = "\033[92m"
CORAL    = "\033[91m"
RED      = "\033[91m"
PINK     = "\033[35m"
TEAL     = "\033[36m"
WHITE    = "\033[97m"
DIM      = "\033[2m"
BOLD     = "\033[1m"
RESET    = "\033[0m"

BAR  = f"{GOLD}{'─' * 58}{RESET}"

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

_clip_start()

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
_abort_event  = threading.Event()
_worker_busy  = threading.Event()

# ── Blessed UI state ──────────────────────────────────────────────────────────
import blessed as _blessed_mod
import re     as _re_mod
_term      = _blessed_mod.Terminal()
_out_buf  : list  = []
_out_acc  : list  = [""]
_stream   : list  = [""]
_scroll   : list  = [0]
_inp_buf  : list  = []
_inp_pos  : list  = [0]
_spin_lbl : list  = [""]
_ui_active: list  = [False]
_out_lock  = threading.Lock()
_rndr_lock = threading.Lock()
_ANSI_ESC  = _re_mod.compile(r'\x1b\[[0-9;]*[mABCDEFGHJKLMSTfnsuhlr]')
_last_render_t: list = [0.0]
_RENDER_INTERVAL = 0.033

def sanitize(t: str) -> str:
    return t.encode("utf-8", errors="replace").decode("utf-8")

def _set_cursor_visible(visible: bool) -> None:
    if sys.platform != "win32": return
    try:
        import ctypes, ctypes.wintypes
        class _CURSOR_INFO(ctypes.Structure):
            _fields_ = [("dwSize", ctypes.c_int), ("bVisible", ctypes.c_int)]
        k32 = ctypes.windll.kernel32
        h   = k32.GetStdHandle(-11)
        ci  = _CURSOR_INFO()
        if k32.GetConsoleCursorInfo(h, ctypes.byref(ci)):
            ci.bVisible = 1 if visible else 0
            k32.SetConsoleCursorInfo(h, ctypes.byref(ci))
    except Exception: pass

def cls(): os.system("cls" if os.name == "nt" else "clear")

def _raw(text: str, end: str = "") -> None:
    full = text + end
    chunks = full.split('\n')
    with _out_lock:
        _out_acc[0] += chunks[0]
        for chunk in chunks[1:]:
            _out_buf.append(_out_acc[0])
            _out_acc[0] = chunk
    _render()

def _do_render() -> None:
    try:
        w = max(_term.width  or 80, 40)
        h = max(_term.height or 24, 8)
    except Exception: return
    output_h = h - 4
    with _out_lock:
        lines = list(_out_buf)
        if _out_acc[0]: lines.append(_out_acc[0])
    stream = _stream[0]
    if stream:
        for ln in stream.split('\n'): lines.append(ln)
    total   = len(lines)
    offset  = _scroll[0]
    end_i   = total - offset
    start_i = max(0, end_i - output_h)
    visible = lines[start_i:end_i]
    _set_cursor_visible(False)
    buf: list = []
    for i in range(output_h):
        buf.append(f"\033[{i+1};1H\033[K")
        if i < len(visible):
            ln   = visible[i]
            vlen = len(_ANSI_ESC.sub('', ln))
            buf.append(ln if vlen <= w else _ANSI_ESC.sub('', ln)[:w])
    if offset > 0:
        hint = f" ↑ {offset} lines above — End: jump to bottom "[:w]
        buf.append(f"\033[1;1H\033[7m{hint}\033[m")
    buf.append(f"\033[{h-3};1H\033[K\033[33m{'─' * w}\033[m")
    inp_str  = ''.join(_inp_buf)
    inp_disp = f" \033[1mYou\033[m\033[2m › \033[m\033[97m{inp_str}\033[m"
    buf.append(f"\033[{h-2};1H\033[K{inp_disp}")
    buf.append(f"\033[{h-1};1H\033[K\033[33m{'─' * w}\033[m")
    mode_str = _get_mode() or "normal"
    try: qsize = msg_queue.size()
    except Exception: qsize = 0
    spin = _spin_lbl[0]
    try: mdl = orchestrator._api.current_model.split('/')[-1]
    except Exception: mdl = ""
    sb = (
        f" \033[1;33m⚡ Jarvis\033[m  \033[96m[{mode_str}]\033[m  \033[97m[Q:{qsize}]\033[m"
        + (f"  \033[2m{spin}\033[m" if spin else "")
        + (f"  \033[2m{mdl}\033[m" if mdl else "")
        + f"  \033[2mCtrl+Q: cancel\033[m"
    )
    buf.append(f"\033[{h};1H\033[K{sb}")
    cur_col = min(7 + _inp_pos[0] + 1, w)
    buf.append(f"\033[{h-2};{cur_col}H")
    sys.stdout.write(''.join(buf))
    sys.stdout.flush()
    _set_cursor_visible(True)

def _render(force: bool = False) -> None:
    if not _ui_active[0]: return
    now = time.monotonic()
    if not force and (now - _last_render_t[0]) < _RENDER_INTERVAL: return
    if _rndr_lock.acquire(blocking=False):
        try:
            _last_render_t[0] = time.monotonic()
            _do_render()
        finally: _rndr_lock.release()

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

def _section(title, color):
    _raw(f"\n  {color}{BOLD}{title}{RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")

def _cmd_row(cmd, desc, color):
    _raw(f"  {color}{cmd:<32}{RESET}  {DIM}{desc}{RESET}\n")

def cmd_help():
    _raw(f"\n  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    _raw(f"  {AMBER}{BOLD}   J A R V I S  —  COMMAND REFERENCE{RESET}\n")
    _raw(f"  {AMBER}{BOLD}{'═' * 58}{RESET}\n")
    # ... commands omitted ...
    _raw(f"\n  {DIM}Just talk naturally — Jarvis understands plain English.{RESET}\n\n")

def cmd_commands():
    # ... commands omitted ...
    _raw("\n")

def cmd_memory(args: list[str] = []):
    from memory.long_term import store, get_all, delete_by_index, clear_manual
    sub = args[0].lower() if args else "list"
    if sub == "add" and len(args) > 1:
        fact = " ".join(args[1:])
        store(fact, source="manual")
        _raw(f"\n  {VIOLET}● MEMORY{RESET}  {DIM}Saved:{RESET}  {WHITE}{sanitize(fact)}{RESET}\n\n")
        return
    # ... rest ...
    entries = get_all()
    if not entries:
        _raw(f"\n  {DIM}  No memories yet.{RESET}\n\n")
        return
    _raw(f"\n  {VIOLET}{BOLD}  Memories  ({len(entries)}){RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    for i, e in enumerate(entries[:40], 1):
        lock = f"  {CORAL}🔒{RESET}" if e["source"] == "auto" else f"  {GREEN}✎{RESET}"
        _raw(f"  {VIOLET}{i:>2}.{RESET}  {WHITE}{sanitize(e['doc'])}{RESET}{lock}\n")
    _raw(f"\n  {DIM}🔒 auto-learned (protected)  ✎ manual{RESET}\n\n")

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

def cmd_skill(args: list[str] = []):
    sub = args[0].lower() if args else "list"
    # ... rest ...
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

def cmd_profile(args: list[str] = []):
    sub = args[0].lower() if args else "show"
    # ... rest ...
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

def cmd_custom(args: list[str] = []):
    sub = args[0].lower() if args else "list"
    # ... rest ...
    cmds = list_commands()
    _raw(f"\n  {TEAL}{BOLD}  Custom Commands  ({len(cmds)}){RESET}\n")
    _raw(f"  {GOLD}{'─' * 50}{RESET}\n")
    for c in cmds:
        _raw(f"  {TEAL}/{c['name']:<18}{RESET}  {DIM}{sanitize(c['desc'])}{RESET}\n")
    _raw(f"\n  {DIM}/cmd add <name> <prompt>  ·  /cmd remove <name>{RESET}\n\n")

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
    lower = text.lower()
    if len(text) > 120 or any(kw in lower for kw in _HEAVY_KEYWORDS):
        return "heavy"
    return "light"

def _spinner_thread(stop_event: threading.Event, status_ref: list) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        _spin_lbl[0] = f"{frames[i % len(frames)]}  {status_ref[0]}"
        _render()
        i += 1
        time.sleep(0.08)
    _spin_lbl[0] = ""
    _render()

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
    if header_printed and full:
        with _out_lock:
            for ln in full.split('\n'): _out_buf.append(ln)
            _out_buf.append("")
        _stream[0] = ""
    else:
        _stream[0] = ""
    _render(force=True)
    return full

def _worker():
    while _running:
        item = msg_queue.get(timeout=0.3)
        if item is None: continue
        if item == "__STOP__": break
        _worker_busy.set()
        _abort_event.clear()
        prompt_str = item[0] if isinstance(item, tuple) else str(item)
        if isinstance(item, tuple):
            _raw(f"  {TEAL}◆ {item[1].split()[0]}{RESET}  {DIM}→ {sanitize(prompt_str)}{RESET}\n")
        try:
            tier = _classify_task(prompt_str)
            full_response = ask_streaming(prompt_str, abort_check=lambda: _abort_event.is_set(), model_tier=tier)
            extract_and_store_async(prompt_str, full_response)
            task_memory.save(prompt_str, full_response)
        except Exception as e:
            log_error("worker", f"Worker error: {e}")
        finally:
            _worker_busy.clear()
            _abort_event.clear()
        if full_response:
            threading.Thread(target=speak, args=(full_response,), daemon=True).start()
        threading.Thread(target=_queue_suggestions_after_delay, daemon=True).start()
        _flush_suggestions()
        next_items = msg_queue.peek()
        if next_items:
            nxt = next_items[0]
            preview = (nxt[1] if isinstance(nxt, tuple) else str(nxt))[:60]
            _raw(f"  {DIM}→ Running next queued task: \"{sanitize(preview)}\"{RESET}\n")
    
def _submit():
    # ... rest ...
    pass
    
def _test_openrouter_connection() -> None:
    # ...
    pass
    
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
