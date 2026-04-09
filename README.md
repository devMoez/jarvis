# Jarvis AI

A personal AI assistant that runs on your computer. Talks back, searches the web, opens apps, runs commands, manages files, and remembers things — all from plain English.

Built with free tools. No subscriptions needed beyond an OpenRouter API key.

---

## What it can do

| Label | Capability |
|---|---|
| `[SEARCH]` | Web search via DuckDuckGo |
| `[FETCH]` | Read content from any webpage |
| `[OPEN]` | Open URLs in browser |
| `[LAUNCH]` | Open applications by name |
| `[RUN]` | Execute any shell command |
| `[READ]` | Read file contents |
| `[WRITE]` | Create and edit files |
| `[MOVE]` | Move and rename files |
| `[COPY]` | Copy files and folders |
| `[DELETE]` | Delete files |
| `[FILES]` | Search files by name pattern |
| `[SYSTEM]` | Time, date, battery, clipboard |
| `[POWER]` | Shutdown / restart / hibernate / sleep / lock |
| `[INSTALL]` | Install software via winget / pip / choco |
| `[MEMORY]` | Persistent long-term memory |
| `[NOTIFY]` | Windows desktop notifications |

---

## Setup

**Requirements:** Python 3.10+, Windows 10/11

```bash
git clone https://github.com/yourusername/jarvis.git
cd jarvis

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file:
```
OPENROUTER_API_KEY=your_key_here
```

Get a free key at [openrouter.ai](https://openrouter.ai)

---

## Run

```bash
# Text mode (default)
python main.py

# Voice input mode
python main.py --voice
```

---

## Slash Commands

| Command | Description |
|---|---|
| `/help` | Usage guide |
| `/commands` | All capabilities |
| `/voice` | Switch to voice input |
| `/text` | Switch to text input |
| `/clear` | Clear terminal |
| `/memory` | Show stored memories |
| `/mode` | Show current mode |
| `/quit` | Exit |

---

## Stack

| Component | Tool |
|---|---|
| LLM | OpenRouter (free models — Llama, GPT-OSS) |
| Speech-to-text | faster-whisper (local) |
| Text-to-speech | edge-tts (Microsoft Neural, free) |
| Wake word | openwakeword |
| Web search | DuckDuckGo (no API key) |
| Memory | ChromaDB + sentence-transformers (local) |
| Browser | Playwright |

Everything except the OpenRouter API key is free and runs locally.

---

## Voice Mode

In voice mode, Jarvis listens for "Hey Jarvis" to activate. If wake word detection fails, it falls back to pressing Enter.

Switch between modes at runtime:
```
/voice    → speak your message
/text     → type your message
```

---

## Adding Features

See `FEATURES.md` for the full feature list. When adding a new tool:

1. Create the function in `tools/`
2. Register it in `main.py` via `registry.register()`
3. Add a tool definition in `core/tool_registry.py`
4. Add a label entry in `TOOL_LABELS` in `main.py`
5. Document it in `FEATURES.md`
