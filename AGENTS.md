# AGENTS.md — Jarvis AI Project Reference

> **Read this file before every session. Do not re-explore the codebase.**
> This document is the authoritative map of every file, feature, rule, and known issue.
> All the information you need is here. Grep specific files only when you need to read exact implementation details.

---

## Project Overview

**Jarvis** is a personal AI assistant for Windows, built by Moez.
Iron Man–inspired CLI. Text + voice input. Streaming LLM responses via Gemini 2.5 Pro (primary) / OpenRouter (fallback). Tool-use for web search, deep research, book finding, file ops, browser automation, system control. Persistent memory (long-term + task history), adaptive learning, custom personas, Telegram remote control.

- **Entry point:** `main.py` — run with `venv/Scripts/python.exe main.py`
- **Voice mode:** `venv/Scripts/python.exe main.py --voice`
- **Current version:** 2.0.0 (defined in `version.py` and `pyproject.toml`)
- **Platform:** Windows 11 only (Windows-specific paths, subprocess calls, power commands)
- **Python:** 3.14 (venv at `./venv/`)

---

## Full Project Structure

```
jarvis/
│
├── main.py                      # Entry point, CLI loop, all UI rendering
├── config.py                    # All configuration constants + system prompt + persona/mode overlays
├── version.py                   # VERSION, API_PROVIDER, AUTHOR strings
├── telegram_bridge.py           # Telegram bot polling + message dispatch
├── test_imports.py              # Sanity-check import script (not used in prod)
├── pyproject.toml               # Package metadata, entry-point: jarvis = "main:main"
├── requirements.txt             # All Python dependencies (pinned with >=)
├── .env                         # API keys — never commit, never read by Codex
├── .env.example                 # Template: OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_ID
├── .gitignore                   # Standard ignores
├── README.md                    # User-facing docs
├── FEATURES.md                  # Feature list (may be outdated — AGENTS.md is authoritative)
│
├── core/
│   ├── __init__.py
│   ├── api_manager.py           # Multi-provider API key management + fallback chain (NEW)
│   ├── orchestrator.py          # LLM streaming, tool-call loop, abort support (uses APIManager)
│   ├── conversation.py          # ConversationHistory, session persistence, unified mode system
│   ├── tool_registry.py         # TOOL_DEFINITIONS (OpenAI function-calling schema) + ToolRegistry dispatcher
│   ├── skills.py                # Persistent skills (data/skills.json) — injected into every system prompt
│   ├── profile.py               # User profile (data/profile.json) — injected into every system prompt
│   └── custom_commands.py       # User-defined /commands (data/custom_commands.json)
│
├── tools/
│   ├── __init__.py
│   ├── search.py                # search_web() — Tavily (if key set) or DuckDuckGo fallback
│   │                            #   search_tavily_raw() — returns raw list[dict] for research pipeline
│   ├── research.py              # deep_research() — Tavily URLs → Crawl4AI scrape → LLM synthesizes
│   │                            #   _scrape_url() tries Crawl4AI first, falls back to httpx+BS4
│   ├── books.py                 # find_book() — LibGen search + MD5 download + Anna's Archive fallback
│   │                            #   auto-downloads first result to ./downloads/
│   ├── browser.py               # open_url, scrape_page, browser_open_visible, browser_login,
│   │                            #   browser_with_session, browser_list_sessions (Playwright)
│   ├── app_control.py           # open_app(), list_running_apps(), close_app() — subprocess/psutil
│   ├── file_ops.py              # read_file, write_file, list_directory, send_notification
│   ├── os_control.py            # run_command, move_file, copy_file, delete_file,
│   │                            #   system_power, install_software, search_files
│   └── system_info.py           # get_system_info() — time, date, battery, clipboard
│
├── audio/
│   ├── __init__.py
│   ├── recorder.py              # record_until_silence(), record_chunk() — sounddevice
│   ├── stt.py                   # transcribe() — faster-whisper (lazy-loaded, base.en model)
│   ├── tts.py                   # speak(), speak_async_nonblocking() — edge-tts + soundfile
│   └── wake_word.py             # start_listening(), stop_listening() — openwakeword "hey_jarvis"
│
├── memory/
│   ├── __init__.py
│   ├── long_term.py             # ChromaDB vector store — store(), retrieve(), get_all(),
│   │                            #   delete_by_index(), clear_manual(), remember()
│   ├── task_memory.py           # TaskMemory — append-only JSON log at data/task_memory.json
│   │                            #   save(query, result), get_context(n), show(n), clear(), count()
│   │                            #   Cap: 200 entries. Provides last N as LLM context (future).
│   ├── extractor.py             # extract_and_store_async() — background LLM extraction of
│   │                            #   facts/profile/patterns from each conversation turn
│   │                            #   Uses APIManager (benefits from full provider fallback)
│   ├── patterns.py              # Behavior pattern tracker — record(), pop_suggestions(),
│   │                            #   all_patterns() — data/patterns.json
│   └── short_term.py            # PLACEHOLDER — no-op, short-term is in ConversationHistory
│
└── data/                        # All runtime state (gitignored where sensitive)
    ├── profile.json             # User profile: {name, timezone, language, preferences}
    ├── session.json             # Conversation history (last 40 turns, user+assistant only)
    ├── skills.json              # Persistent skills: [{id, instruction, source}]
    ├── patterns.json            # Behavior pattern counts: {key: {count, suggested, description}}
    ├── custom_commands.json     # User /commands: [{name, prompt, desc}]   ← may not exist yet
    ├── custom_modes.json        # Custom behavior modes: {name: prompt}     ← created on first /mode save
    ├── task_memory.json         # Ordered log of every query+response (cap 200)
    ├── browser_sessions/        # Playwright persistent profiles per service ← created on first login
    │   └── <service_name>/      # Chromium profile dir (cookies, localStorage, etc.)
    ├── chroma_db/               # ChromaDB vector index (embedding store)
    └── logs/                    # Empty — reserved for future logging

downloads/                       # Auto-downloaded books/files from find_book() — created on first download
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| LLM API | **Gemini 2.5 Pro** (primary) | `gemini-2.5-pro-exp-03-25` via OpenAI-compat endpoint |
| LLM Fallback | OpenRouter → OpenAI → Anthropic → Gemini → Groq → Mistral | All via `core/api_manager.py` |
| Gemini endpoint | `https://generativelanguage.googleapis.com/v1beta/openai/` | OpenAI-compatible, requires `/openai/` suffix |
| Streaming | OpenAI SDK `stream=True`, `max_tokens=8192` | Token-by-token, tool calls accumulated across chunks |
| Function calling | OpenAI tool-use format | Defined in `core/tool_registry.py` TOOL_DEFINITIONS |
| Web search | Tavily (if `TAVILY_API_KEY` set) → DuckDuckGo fallback | `tools/search.py` auto-selects |
| Deep research | Tavily URLs → Crawl4AI scrape → LLM synthesis | `tools/research.py`; httpx+BS4 fallback per URL |
| Book search | LibGen HTML scrape → MD5 → `library.lol` download | `tools/books.py`; Anna's Archive fallback |
| Task memory | JSON append-log `data/task_memory.json` | Every query+response saved; cap 200 |
| STT | faster-whisper `base.en` | CPU, int8, lazy-loaded on first voice use |
| TTS | edge-tts `en-US-GuyNeural` | Microsoft Neural via asyncio, plays via soundfile+sounddevice |
| Wake word | openwakeword `hey_jarvis` | ONNX inference, 16kHz int16 audio |
| Vector memory | ChromaDB + SentenceTransformers `all-MiniLM-L6-v2` | Persistent at `data/chroma_db/` |
| Browser automation | Playwright (async API) | Called synchronously via `asyncio.new_event_loop()` |
| CLI UI | prompt_toolkit 3.x + colorama + ANSI | prompt_toolkit for live input coloring, bottom toolbar |
| Terminal rendering | `_raw()` / `sys.stdout.write()` | NOT Rich console for main output — only `console` for startup errors |
| HTTP | httpx | Used by Telegram bridge, scraper fallback, LibGen downloader |
| Telegram | httpx long-polling (custom) | Does NOT use `python-telegram-bot` async SDK — raw HTTP |
| Config | python-dotenv | `.env` loaded at startup in `config.py` |
| Package | setuptools / pyproject.toml | Entry point `jarvis = "main:main"` |

---

## All Finished Features

### Input & Modes
- **Text mode** (default) — prompt_toolkit input with persistent bottom toolbar
- **Voice mode** (`--voice` flag or `/voice`) — wake word "Hey Jarvis" → record → transcribe → respond
- **Non-blocking input** — messages queue up while Jarvis processes; input always available

### CLI / UI
- **Colorful `/` command coloring** — valid commands bright cyan, partial teal, unknown gray (live as you type)
- **Dynamic prompt label** — shows active mode: `You [coder] ›`
- **Bottom toolbar** — shows active mode, processing state, queue depth, current model, Ctrl+Q hint
- **Cycling bullet `◆`** — every user message gets a rotating colored bullet (cyan→amber→violet→…)
- **Spinner** — cycling-color spinner with tool status during AI processing

### AI & LLM
- **Primary model: Gemini 2.5 Pro** (`gemini-2.5-pro-exp-03-25`) — key in `GEMINI_API_KEY`, `max_tokens=8192`
- **Streaming responses** — token-by-token; tool calls accumulated across chunks
- **Tool-call loop** — up to 10 rounds of tool use per message
- **Multi-provider fallback** (`core/api_manager.py`) — Gemini → OpenRouter → OpenAI → Anthropic → Groq → Mistral
- **Abort support** — `_abort_event` checked at every token and tool boundary
- **Document generation rules** — system prompt enforces complete output: min 4 paragraphs for letters, full structure for reports, no truncation

### Web Research
- **`search_web(query)`** — auto-uses Tavily if `TAVILY_API_KEY` set, else DuckDuckGo
- **`deep_research(topic, max_sources=5)`** — multi-step pipeline:
  1. Tavily finds top N URLs with snippets
  2. Each URL scraped with Crawl4AI (httpx+BS4 fallback)
  3. Raw content returned labeled per source; LLM synthesizes full report
  4. Falls back to DuckDuckGo snippets if Tavily not configured
- **`/research <topic>`** slash command — translates to "Research this topic in depth…" prompt

### Books & File Download
- **`find_book(query, auto_download=True)`** — pipeline:
  1. Scrapes LibGen HTML table for MD5 hashes (tries `libgen.rs` mirror on failure)
  2. Fetches `https://library.lol/main/<md5>` to extract direct download URL
  3. Streams download to `./downloads/<title>.<ext>`
  4. Falls back to Anna's Archive scrape if LibGen unavailable
- **`/book <title or author>`** slash command
- Downloads saved to `./downloads/` (created automatically)

### Commands — Built-in
```
/help              Full command reference
/commands          AI tool capabilities list
/clear             Redraw banner
/mode              Manage behavior modes (see below)
/voice / /text     Switch input mode
/add-api           Add/update API key for any provider
/list-apis         Show all providers, key previews, active model
/first <msg>       Inject message at front of priority queue
/search <query>    Web search (Tavily/DuckDuckGo)
/research <topic>  Deep research: scrape top sources, full report
/book <title>      Find and download book from LibGen
/memory tasks      Show last 20 task queries
/memory tasks clear  Clear task history
/quit / /exit      Graceful shutdown
```

### Behavior Modes (`/mode`)
Built-in modes: `funny`, `stealth`, `think`, `roast` (legacy), `expert`, `professional`, `master`, `humanize`, `coder`, `jarvis`
- `/mode <name>` — activate mode
- `/mode list` — see all modes with previews
- `/mode save <name> "prompt"` — create custom mode (saved to `data/custom_modes.json`)
- `/mode delete <name>` — remove custom mode
- `/mode off` — clear active mode
- Mode overlay is appended to system prompt on every turn

### Memory System
- **Long-term memory** — ChromaDB vector store; facts auto-extracted after each turn; semantic retrieval injected into system prompt
- **Adaptive extraction** — background LLM call after each turn extracts facts, profile updates, behavior patterns
- **Pattern tracking** — patterns hitting threshold (3×) queue a `/learn save` suggestion
- **Skills** — persistent instructions always appended to system prompt; auto-learned skills are write-protected
- **Profile** — user name/timezone/language/preferences auto-updated and always injected

### Memory System
- **Long-term memory** — ChromaDB vector store; facts auto-extracted after each turn; semantic retrieval injected into system prompt
- **Task memory** — `data/task_memory.json` append-log (cap 200); every query+response saved after worker completes
- **Adaptive extraction** — background LLM call after each turn extracts facts, profile updates, behavior patterns
- **Pattern tracking** — patterns hitting threshold (3×) queue a `/learn save` suggestion
- **Skills** — persistent instructions always appended to system prompt; auto-learned skills are write-protected
- **Profile** — user name/timezone/language/preferences auto-updated and always injected

### Memory Commands
```
/memory            List all memories (🔒 auto = protected, ✎ manual = deletable)
/memory add <fact> Add manually
/memory remove <n> Remove manual entry
/memory clear      Clear manual only
/memory tasks      Show last 20 task queries from task_memory.json
/memory tasks clear  Wipe task history
/learn             Show detected behavior patterns
/learn save <n>    Promote pattern to permanent skill
/skill             Manage skills (add/remove/clear)
```

### Custom Commands
```
/cmd               List custom commands
/cmd add <name> <prompt>   Create /name shortcut
/cmd remove <name>         Delete
```
Custom command names are live-colored in the prompt alongside built-ins.

### Priority Queue (`/first`)
- Normal messages → appended to `_PriorityDeque`
- `/first <message>` → prepended with `[FIRST] ↑ pushed to front` indicator
- Queue depth shown inline and in toolbar

### Keyboard Shortcuts
- **Ctrl+Q (busy)** → sets `_abort_event`; orchestrator stops at next token/tool boundary; prints `⊘ Cancelling task...`
- **Ctrl+Q (idle)** → graceful shutdown

### Browser Automation (`tools/browser.py`)
- `open_url` — system default browser (webbrowser module)
- `browser_open_visible(url, wait_seconds)` — visible Chrome via Playwright; no session
- `browser_login(url, service, wait_seconds)` — visible Chrome with persistent profile at `data/browser_sessions/<service>/`; window stays open for manual login; session reused on next call
- `browser_with_session(url, service)` — opens with saved session; auto-falls-back to login if no session
- All Playwright functions fall back to `webbrowser.open()` if Playwright fails
- LLM is instructed via tool descriptions to use `browser_login` (never `open_url`) for any authentication task

### Tools Registered (22 total)
`search_web`, `open_url`, `scrape_page`, `open_app`, `get_system_info`, `read_file`, `write_file`, `list_directory`, `remember`, `send_notification`, `run_command`, `move_file`, `copy_file`, `delete_file`, `system_power`, `install_software`, `search_files`, `browser_open_visible`, `browser_login`, `browser_with_session`, `deep_research`, `find_book`

### Telegram Remote Control
- Optional; requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_ID` in `.env`
- Long-poll via httpx (not python-telegram-bot async); runs in `TGProcessor` daemon thread
- Validates sender ID; responds with `⏳ On it, sir...` then sends reply
- Comma-separated IDs supported for multi-user whitelist

### User Profile
```
/profile                     Show profile
/profile set name X
/profile set timezone X
/profile pref <key> <value>
/profile clear <field>
```

---

## Known Bugs & TODO

### Bugs

1. ~~**`memory/extractor.py` bypasses APIManager**~~ — **FIXED**: extractor now uses `APIManager` singleton; benefits from full provider fallback chain.

2. **`audio/recorder.py` line 9 raw `print()`** — `print("[recorder] Listening...")` writes directly to stdout, bypassing `_raw()` and `patch_stdout()`. In voice mode this may corrupt terminal display. Fix: replace with `_raw(...)` or suppress.

3. **`audio/stt.py` raw `print()` calls** — Same issue; `print("[stt] Loading Whisper model...")` and `print("[stt] Model ready.")` go to raw stdout.

4. **`version.py` and `pyproject.toml` still show `1.2.0`** — Version was not bumped after the v1.6.0 features (persistent session, status-aware UI) or the current feature additions. The banner in `main.py` reads from `VERSION`. Update all three when releasing.

5. ~~**`memory/extractor.py` uses `LLM_FALLBACK_MODEL`**~~ — **FIXED**: extractor uses `APIManager.current_model`; `LLM_FALLBACK_MODEL` is now an unused dead constant in `config.py` — can be removed.

6. **`_DynCmdLexer.lex_document()` calls `list_commands()` on every keypress** — It reads `data/custom_commands.json` from disk on every character typed. Low-impact now (small file) but would cause I/O thrash if commands file grows. Fix: cache with a short TTL or invalidate on `/cmd add/remove`.

7. **`browser_login` / `browser_open_visible` block the worker thread** — These functions call `asyncio.new_event_loop().run_until_complete()` which can block for `wait_seconds` (default 60–120s). During this time the Ctrl+Q abort event is not checked. The browser window keeps the thread locked. Acceptable for now but means Ctrl+Q won't cancel a browser task.

8. **`data/patterns.json` not created until first pattern is recorded** — `all_patterns()` returns `{}` gracefully, so no crash. Just informational.

### TODO / Missing

- [ ] Bump `version.py` and `pyproject.toml` to `2.0.0` after major feature additions
- [ ] Run `pip install tavily-python crawl4ai` in the venv (added to requirements.txt)
- [ ] Run `playwright install chromium` in venv before first browser use
- [ ] Add `close_app()` and `list_running_apps()` from `app_control.py` to tool registry (they exist but are not registered)
- [ ] `memory/short_term.py` is a no-op placeholder — either implement summarization or delete it
- [ ] Playwright browsers need `playwright install chromium` run once in the venv before first use
- [ ] No rate-limiting on the extraction LLM call — if conversations are very rapid, many concurrent extractor threads could be spawned
- [ ] No error display when Telegram `send()` fails beyond the raw `print()` on line 55 of `telegram_bridge.py`
- [ ] `audio/wake_word.py` prints to stdout directly (lines 22, 43, 52, 54, 59) — should use `_raw()` or be silenced

---

## Key Rules

### Architecture Rules — Never Break These

1. **All user output goes through `_raw()`** — never use `print()` in the main flow. `print()` bypasses `patch_stdout()` and corrupts the terminal. Only use `print()` in audio/ and legacy test files where it's already established.

2. **`_CmdLexer` / `_PROMPT_STYLE` are defined at module level** — they are used by `_DynCmdLexer` (subclass) inside `main_loop()`. Do not move them into `main_loop()` or the subclass reference breaks.

3. **Never touch `data/chroma_db/`** — ChromaDB's internal files. Reading or writing them directly corrupts the vector index.

4. **`core/conversation.py` `get_messages()` is the single source of truth for system prompt construction** — the full prompt is: `SYSTEM_PROMPT + mode_overlay + profile + skills + memory_context`. Do not inject prompts anywhere else.

5. **`_abort_event` and `_worker_busy` are module-level `threading.Event` objects** — they must stay at module level so the Ctrl+Q key binding closure (defined inside `main_loop()`) can access them.

6. **Tool definitions in `core/tool_registry.py` TOOL_DEFINITIONS must be kept in sync with registered tools in `main.py`** — if you add a function to `tools/`, add its JSON schema to `TOOL_DEFINITIONS`, register it with `registry.register()` in `main.py`, and add entries to `TOOL_LABELS`, `TOOL_ANSI`, `TOOL_STATUS` maps.

7. **Auto-learned memories and skills (source="auto") are write-protected** — `delete_by_index()`, `remove_skill()`, `clear_manual()`, `clear_skills()` all check the `source` field. Do not remove this protection.

8. **`orchestrator._api` is the single `APIManager` instance** — call `orchestrator._api.rebuild()` after any call to `add_key()` so the fallback chain is updated without restart.

9. **`memory/extractor.py` runs in a daemon thread** — it must never raise exceptions into the main thread. All errors are caught and silently swallowed (`except Exception: return`). Keep this pattern.

10. **The `_PriorityDeque` worker uses `"__STOP__"` sentinel (not `None`) to stop** — `None` is a valid return from `get()` on timeout. Only `"__STOP__"` breaks the worker loop.

### Coding Patterns

- **All persistent data** lives in `./data/`. Use `pathlib.Path` and `.parent.mkdir(parents=True, exist_ok=True)` before writing.
- **Config** is in `config.py` only — constants are imported by other modules. Don't scatter config values into module-level variables elsewhere.
- **New tools** follow the pattern: function in `tools/`, schema in `TOOL_DEFINITIONS`, `registry.register()` in `main.py`, label/color/status entries in the three maps.
- **New slash commands** follow: function `cmd_xxx()`, add to `handle_slash()`, add command string to `_KNOWN_CMDS`, add to `/help` output.
- **Async Playwright** — always use `asyncio.new_event_loop()` (never `asyncio.get_event_loop()`) because the main thread runs with threading, not asyncio. Close the loop in `finally`.
- **ANSI colors** — use the named constants (`AMBER`, `CYAN`, `GOLD`, etc.) defined at module level. Never hardcode escape sequences inline.
- **`sanitize(text)`** — always wrap user-originated or LLM-originated text through `sanitize()` before passing to `_raw()`. It handles UTF-8 encoding errors.

### Things That Must Never Be Changed Without Full Audit

- The `process_stream()` generator protocol in `core/orchestrator.py` — callers depend on the `__TOOL__` prefix convention for tool events vs plain text tokens.
- `ConversationHistory._trim()` — changing `SHORT_TERM_MAX_TURNS` affects memory, context length, and API costs.
- `PERSONA_PROMPTS` / `EXTENDED_MODES` in `config.py` — every change affects all existing users' active mode behavior.
- The `source` field logic in `memory/long_term.py` and `core/skills.py` — removing protection would let users delete auto-learned data permanently.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** (primary) | Gemini 2.5 Pro — Google AI Studio key |
| `OPENROUTER_API_KEY` | Yes (or Gemini) | OpenRouter — used as fallback |
| `TAVILY_API_KEY` | No | Enables Tavily search; falls back to DuckDuckGo if missing |
| `OPENAI_API_KEY` | No | Fallback / alternative provider |
| `ANTHROPIC_API_KEY` | No | Fallback / alternative provider |
| `GROQ_API_KEY` | No | Fallback / alternative provider |
| `MISTRAL_API_KEY` | No | Fallback / alternative provider |
| `TELEGRAM_BOT_TOKEN` | No | Enables Telegram remote control |
| `TELEGRAM_ALLOWED_ID` | No | Comma-separated numeric Telegram user IDs |

Keys are set via `/add-api <provider> <key>` at runtime (writes to `.env` and `os.environ`).

---

## Data Flow: Message → Response

```
User types message
  → _PriorityDeque.put(raw)          [or put_first() for /first]
  → MsgWorker thread picks up item
    → _worker_busy.set()
    → ask_streaming(text, abort_check=lambda: _abort_event.is_set())
      → retrieve() from ChromaDB     [parallel thread, 3s timeout]
      → orchestrator.process_stream()
        → ConversationHistory.get_messages()   [builds full system prompt]
        → APIManager.get_client()              [current provider client]
        → stream LLM tokens → yield to caller
        → if tool_calls: dispatch via ToolRegistry → loop
        → yield __TOOL__<name> events for spinner
      → print spinner / response tokens live
    → _worker_busy.clear()
    → speak(response)                [daemon thread]
    → extract_and_store_async()      [daemon thread: facts/profile/patterns]
    → task_memory.save(query, resp)  [synchronous: appends to data/task_memory.json]
    → _queue_suggestions_after_delay()[daemon thread: 2.5s delay then pop]
    → _flush_suggestions()           [print /learn save hints]
```

---

## Starting Fresh / Resetting State

```bash
# Clear conversation history only
echo [] > data/session.json

# Clear all memories (WARNING: permanent)
# Delete data/chroma_db/ directory

# Clear skills
# Edit data/skills.json → []

# Clear profile
# Edit data/profile.json → {"name":null,"timezone":null,"language":"English","preferences":{}}

# Run
venv/Scripts/python.exe main.py
```

---

## File Size Reference (approx. as of last mapping)

| File | Purpose | Complexity |
|---|---|---|
| `main.py` | UI, commands, main loop | ~1200 lines, high |
| `core/tool_registry.py` | Tool schemas + dispatcher | ~400 lines, medium |
| `tools/research.py` | Deep research pipeline | ~130 lines, medium |
| `tools/books.py` | LibGen/Anna's Archive | ~246 lines, medium |
| `memory/task_memory.py` | Task history log | ~88 lines, low |
| `core/orchestrator.py` | LLM streaming + tool loop | ~110 lines, high |
| `core/api_manager.py` | Multi-provider management | ~180 lines, medium |
| `core/conversation.py` | History + mode system | ~140 lines, medium |
| `config.py` | All config + prompts | ~130 lines, medium |
| `telegram_bridge.py` | Telegram polling | ~93 lines, low |
| `memory/extractor.py` | Adaptive learning | ~113 lines, medium |
| All other files | ≤ 115 lines each | low |
