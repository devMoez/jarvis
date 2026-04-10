import sys
steps = [
    ("colorama",        "import colorama; colorama.init()"),
    ("dotenv",          "from dotenv import load_dotenv; load_dotenv()"),
    ("rich",            "from rich.console import Console"),
    ("version",         "from version import VERSION"),
    ("orchestrator",    "from core.orchestrator import Orchestrator"),
    ("tool_registry",   "from core.tool_registry import ToolRegistry"),
    ("audio.recorder",  "from audio.recorder import record_until_silence"),
    ("audio.stt",       "from audio.stt import transcribe"),
    ("audio.tts",       "from audio.tts import speak"),
    ("audio.wake_word", "from audio.wake_word import start_listening"),
    ("memory.long_term","from memory.long_term import retrieve, remember"),
    ("memory.extractor","from memory.extractor import extract_and_store_async"),
    ("core.skills",     "from core.skills import list_skills"),
    ("core.profile",    "from core.profile import get_profile"),
    ("tools.search",    "from tools.search import search_web"),
    ("tools.browser",   "from tools.browser import open_url, scrape_page"),
    ("tools.app_control","from tools.app_control import open_app"),
    ("tools.system_info","from tools.system_info import get_system_info"),
    ("tools.file_ops",  "from tools.file_ops import read_file, write_file"),
    ("tools.os_control","from tools.os_control import run_command"),
    ("telegram_bridge", "from telegram_bridge import TelegramBridge"),
    ("prompt_toolkit",  "from prompt_toolkit import prompt"),
]

for name, code in steps:
    try:
        exec(code)
        print(f"  OK  {name}")
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        sys.exit(1)

print("\nAll imports OK.")
