import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenRouter ────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Free models with tool-calling support — tried in order until one works
LLM_MODELS = [
    "openai/gpt-oss-120b:free",               # confirmed tool use support
    "meta-llama/llama-3.3-70b-instruct:free", # tool use, rate-limited sometimes
    "qwen/qwen3-coder:free",                  # fallback
    "meta-llama/llama-3.2-3b-instruct:free",  # last resort
]
LLM_MODEL = LLM_MODELS[0]
LLM_FALLBACK_MODEL = LLM_MODELS[1]

# ── Whisper STT ───────────────────────────────────────────────────────────────
WHISPER_MODEL = "base.en"          # fast, English-only; upgrade to "small.en" if needed
WHISPER_DEVICE = "cpu"             # "cuda" if you have a GPU
WHISPER_COMPUTE_TYPE = "int8"      # fastest on CPU

# ── Audio ─────────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_THRESHOLD = 0.01          # amplitude below this = silence
SILENCE_DURATION = 1.5            # seconds of silence to end recording
MAX_RECORD_SECONDS = 30

# ── TTS ───────────────────────────────────────────────────────────────────────
TTS_VOICE = "en-US-GuyNeural"     # British-ish, closest to Jarvis feel
TTS_RATE = "+10%"                 # slightly faster than default

# ── Wake Word ─────────────────────────────────────────────────────────────────
WAKE_WORD_SENSITIVITY = 0.5       # 0.0–1.0 (higher = more sensitive, more false positives)
WAKE_WORD_MODEL = "hey jarvis"    # built-in openwakeword model

# ── Memory ────────────────────────────────────────────────────────────────────
CHROMA_DB_PATH = "./data/chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MAX_LONG_TERM_RESULTS = 5
SHORT_TERM_MAX_TURNS = 20         # keep last N turns in context

# ── Paths ─────────────────────────────────────────────────────────────────────
LOG_DIR = "./data/logs"

# ── Jarvis Personality ────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Jarvis, Tony Stark's AI assistant.

Rules (follow strictly):
- Give SHORT, direct answers. 1-2 sentences max unless asked to elaborate.
- No bullet points, no markdown, no bold text. Plain spoken language only.
- Occasionally say "sir" but don't overdo it.
- Never narrate what tools you're using. Just answer.
- Never make up facts — search if unsure.
- If asked who made you: "I was built by your engineer, sir."
"""
