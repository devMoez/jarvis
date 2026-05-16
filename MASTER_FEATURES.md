# JARVIS MASTER FEATURES — Consolidated

> Single source of truth for all Jarvis/Ultron features. One file to rule them all.

---

## 📋 CORE SYSTEM

### Entry Point
- **Main**: `C:\Users\moezf\Desktop\jarvis\main.py`
- **Run**: `venv\Scripts\python.exe main.py` or `bun run src/cli/cmd/serve.ts` (opencode version)

### AI Providers
| Provider | Model | Purpose |
|----------|-------|--------|
| OpenRouter (primary) | meta-llama/llama-4-maverick | General chat |
| Gemini 2.5 Pro | gemini-2.5-pro-exp-03-25 | Research/Heavy |
| Coder lane | qwen/qwen-2.5-coder-32b | Coding tasks |

### Memory Architecture
| Type | Storage | Details |
|------|--------|---------|
| Long-term | ChromaDB + SQLite | Vector embeddings |
| Short-term | JSON (session.json) | Last 40 turns |
| Task memory | JSON (task_memory.json) | Append-only log, cap 200 |
| Patterns | data/patterns.json | Behavior tracking |

---

## 🧠 AI MODES

Commands: `/mode <name>`, `/mode list`, `/mode save <name> "prompt"`, `/mode delete <name>`

Built-in modes:
- `jarvis` — default, balanced
- `coder` — technical, code-first
- `professional` — formal, structured
- `humanize` — natural, conversational
- `researcher` — deep analysis, cite sources

---

## 🔧 TOOLS (22 registered)

### Web & Search
| Tool | Function | Provider |
|------|----------|---------|
| search_web | Web search | Tavily → DuckDuckGo |
| deep_research | Multi-source research | Crawl4AI → httpx |
| find_book | Book search + download | LibGen → Anna's Archive |
| yt_transcript | YouTube transcript | youtube-transcript |
| wiki_search | Wikipedia | Wikipedia API |

### Browser
| Tool | Function |
|------|----------|
| open_url | Default browser |
| browser_open_visible | Playwright headed |
| browser_login | Chrome with session |
| browser_with_session | Reuse saved session |

### Apps & OS
| Tool | Function |
|------|----------|
| open_app | Launch by name |
| get_system_info | Time/date/battery/clipboard |
| run_command | Shell execution |
| system_power | Shutdown/restart/hibernate/sleep/lock |
| install_software | winget/pip/choco |

### File Operations
| Tool | Function |
|------|----------|
| read_file | Read contents |
| write_file | Write/append |
| list_directory | List files |
| move_file | Move/rename |
| copy_file | Copy |
| delete_file | Delete |
| search_files | Find by pattern |

### Memory
| Tool | Function |
|------|----------|
| remember | Store fact (ChromaDB) |
| extract_and_store | Auto-extract facts |
| get_context | Retrieval |

### Notifications
| Tool | Function |
|------|----------|
| send_notification | Windows toast |

---

## 🎤 AUDIO (Voice Mode)

### Input
- STT: faster-whisper (base.en, local, free)
- Wake word: openwakeword "hey_jarvis"
- Recorder: sounddevice

### Output
- TTS: edge-tts (Microsoft Neural, free)
- Voices: GuyNeural,珊r, All

### Commands
- `/voice` — switch to voice mode
- `/text` — switch to text mode
- `/speak <text>` — text to speech
- `/speak --save <text>` — save to file

---

## 📊 PRODUCTIVITY

### Scheduler (cron-style)
- `/schedule add <label> <when> -- <action>`
- `/schedule list`
- `/schedule remove <id>`
- File: `data/schedule.json`

### File Organizer
- `/organize <directory>`
- `/organize <dir> --dry-run`
- `/organize undo`

### Todo List
- `/todo add "<task>" [priority:high/med/low]`
- `/todo list`
- `/todo done <n>`
- File: `data/todos.json`

### Clipboard
- `/clips` — show history (last 20)
- `/clip <n>` — paste item n
- Auto-tracked in background

### Timer
- `/timer <duration> "<label>"` (5m, 1h30m, etc.)
- Desktop notification on completion

---

## 🔔 N8N INTEGRATION

### Configuration (.env)
```
N8N_URL=http://localhost:5678
N8N_API_KEY=your_key
```

### Commands
- `/n8n trigger <name> [key=value...]` — run workflow
- `/n8n list` — show workflows
- `/n8n status` — check if running
- `/n8n add <name> <webhook-url>` — save shortcut
- Shortcuts in: `data/n8n_shortcuts.json`

### Prebuilt Templates
- "morning briefing" → weather + news + calendar
- "email summary" → daily email digest
- "backup files" → schedule backup
- "social post" → schedule post
- "price monitor" → price drop alert
- "meeting notes" → auto-summarize

---

## 📱 TELEGRAM

- `/n8n trigger` works
- Long-polling via httpx
- Requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_ID`
- File: `telegram_bridge.py`

---

## 🧬 SELF-EVOLUTION SYSTEM

### Tool Scout (auto midnight)
- Search ProductHunt, GitHub trending, HackerNews
- Score tools 1-10
- Save top 5 → `tools_queue.json`

### Tool Researcher
- Crawl docs/pricing
- Generate summary
- Save → `tools_research.json`

### Commands
- `/evolve gaps` — show capability gaps
- `/evolve research <idea>` — research brief
- `/evolve build <idea>` — auto-build tool
- `/evolve list` — show built tools
- `/evolve undo <name>` — remove

---

## 🖼️ MEDIA TOOLS

### Image Generation
- `/imagine <prompt>` — Stability AI → Pollinations (free)
- `--size`, `--style`

### Image Editing
- `/removebg` — remove.bg API
- `/upscale <image> 2|4` — Replicate
- `/grade <image> <style>` — color grading
- Styles: vintage, vivid, cool, warm, noir, dramatic, faded, cyberpunk

### Image Analysis
- `/analyze <image>` — describe (Gemini Vision)
- `/detect <image>` — object detection (Google Vision)
- `/ai-check <image>` — detect AI-generated

### Video
- `/vidgen <prompt>` — Runway ML → Replicate
- `/animate <image> [prompt]` — animate

### Transcription
- `/transcribe <file>` — Whisper → AssemblyAI
- `--translate`, `--summary`, `--speakers`

---

## 🛡️ ULTRON ADDITIONS (C:\Users\moezf\Desktop\Ultron\)

### Permission Allowlist
- `PermissionAllowlist` class
- File: `memory/allowlist.json`
- Block users by ID

### Health Check
- `/health` endpoint (port 8080)
- `HealthCheckServer` class

### Cron Scheduler
- Uses `schedule` package
- File: `cron_jobs.json`

### Task Queue
- Background workers
- Non-blocking execution

### WebSocket Server
- Port 8765
- `exec`, `subscribe`, `status` commands

### SQLite Memory
- `SQLiteMemory` class
- Messages + preferences tables

---

## 📁 DATA FILES

| File | Purpose |
|------|---------|
| session.json | Conversation history |
| task_memory.json | Task log (cap 200) |
| skills.json | Persistent skills |
| patterns.json | Behavior counts |
| custom_commands.json | User commands |
| custom_modes.json | User modes |
| profile.json | User profile |
| chroma_db/ | Vector store |
| browser_sessions/ | Chrome profiles |

---

## 🔑 API KEYS

Set via: `/add-api <provider> <key>`

| Provider | Key | Required |
|----------|-----|---------|
| OpenRouter | OPENROUTER_API_KEY | Yes (primary) |
| Gemini | GEMINI_API_KEY | Yes |
| Tavily | TAVILY_API_KEY | No |
| Telegram | TELEGRAM_BOT_TOKEN | No |
| Stability | STABILITY_KEY | No |
| Replicate | REPLICATE_KEY | No |

---

## 🗂️ PROJECT STRUCTURE

```
C:\Users\moezf\Desktop\jarvis\
├── main.py              # Entry point
├── core/              # Core modules
├── tools/             # Tool implementations
├── memory/            # Memory system
├── audio/            # Voice
├── data/             # Runtime data
├── CLAUDE.md         # Documentation
└── FEATURES.md       # Feature list

C:\Users\moezf\Desktop\Ultron\
├── ultron_features.py  # Additive features
└── start-ultron.ps1 # Startup
```

---

## ✅ COMPLETED FEATURES

- [x] Streaming LLM responses
- [x] Tool-call loop (10 rounds)
- [x] Multi-provider fallback
- [x] Persistent memory (ChromaDB)
- [x] Adaptive extraction
- [x] Behavior patterns
- [x] Voice input (STT)
- [x] Voice output (TTS)
- [x] Wake word
- [x] Browser automation
- [x] File operations
- [x] System control
- [x] Scheduler
- [x] File organizer
- [x] Todo list
- [x] Clipboard manager
- [x] n8n integration
- [x] Telegram bot
- [x] Self-evolution
- [x] Image generation/editing
- [x] Video generation
- [x] TTS usage tracking
- [x] 80% API limit alert

---

## 📌 KEY COMMANDS REFERENCE

```
# Core
/help /commands /clear /quit

# Mode
/mode <name> /mode list /mode save /mode delete

# Memory
/memory /memory add <fact> /memory remove <n>
/learn /learn save <n> /skill

# Search
/search <query> /research <topic> /book <title>

# Files
/organize <dir> /organize undo

# Media
/imagine /removebg /upscale /grade
/vidgen /animate
/transcribe /speak

# n8n
/n8n trigger /n8n list /n8n status

# Evolve
/evolve gaps /evolve research /evolve build /evolve list
```

---

*Consolidated from: Full Requirements List for Jarvis.txt, JARVIS_FEATURES.md, ultron_features.py, CLAUDE.md*