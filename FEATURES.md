# Jarvis AI — Feature Registry

> Auto-maintained. Add new features here whenever a capability is added.
> Format: `- [LABEL] Description — file:function`

---

## Slash Commands
- `/help`     — Show usage, how to run, basic info
- `/commands` — List all capabilities with labels
- `/voice`    — Switch to voice input mode (STT, no TTS output yet)
- `/text`     — Switch to text input mode (default)
- `/clear`    — Clear terminal and redraw banner
- `/memory`   — Show all stored long-term memories
- `/mode`     — Show current input mode
- `/quit`     — Exit Jarvis

---

## Web & Search
- `[SEARCH]`  Search the web via DuckDuckGo (no API key needed) — `tools/search.py:search_web`
- `[FETCH]`   Scrape and read text content from any URL — `tools/browser.py:scrape_page`
- `[OPEN]`    Open any URL in the default browser — `tools/browser.py:open_url`

---

## Apps & OS Control
- `[LAUNCH]`  Open applications by name (Chrome, Notepad, Spotify, etc.) — `tools/app_control.py:open_app`
- `[RUN]`     Execute any shell/terminal command, get output — `tools/os_control.py:run_command`
- `[SYSTEM]`  Get time, date, battery level, clipboard contents — `tools/system_info.py:get_system_info`
- `[POWER]`   Shutdown / restart / hibernate / sleep / lock screen — `tools/os_control.py:system_power`
- `[INSTALL]` Install software via winget, pip, or choco — `tools/os_control.py:install_software`

---

## File Operations
- `[READ]`    Read file contents — `tools/file_ops.py:read_file`
- `[WRITE]`   Write or append to files — `tools/file_ops.py:write_file`
- `[LIST]`    List directory contents — `tools/file_ops.py:list_directory`
- `[MOVE]`    Move or rename files and folders — `tools/os_control.py:move_file`
- `[COPY]`    Copy files and folders — `tools/os_control.py:copy_file`
- `[DELETE]`  Delete files and folders permanently — `tools/os_control.py:delete_file`
- `[FILES]`   Search for files by name pattern — `tools/os_control.py:search_files`

---

## Memory
- `[MEMORY]`  Store facts in persistent long-term memory (ChromaDB + embeddings) — `memory/long_term.py:remember`
- Auto-extraction of memorable facts after each conversation — `memory/extractor.py`
- Short-term conversation history (last 20 turns) — `core/conversation.py`

---

## Notifications
- `[NOTIFY]`  Send Windows desktop toast notifications — `tools/file_ops.py:send_notification`

---

## Audio (Voice Mode)
- Voice input via microphone — `audio/recorder.py`
- Speech-to-text via faster-whisper (local, free) — `audio/stt.py`
- Text-to-speech via edge-tts Microsoft Neural voices (free) — `audio/tts.py`
- Wake word detection "Hey Jarvis" via openwakeword — `audio/wake_word.py`
- Fallback: Enter key to activate when wake word unavailable

---

## AI Engine
- LLM: OpenRouter free models with automatic fallback rotation
  - Primary: `openai/gpt-oss-120b:free`
  - Fallback: `meta-llama/llama-3.3-70b-instruct:free`
  - Fallback: `qwen/qwen3-coder:free`
  - Fallback: `meta-llama/llama-3.2-3b-instruct:free`
- Streaming responses (token by token)
- Tool calling loop (up to 10 rounds per query)
- Model rotation on rate limit or error

---

## UI
- Rich terminal with colors, spinner, live streaming
- Operation labels with distinct colors per action type
- Clean banner on startup
- Slash command system

---

## Planned / Not Yet Built
- [ ] TTS voice output in voice mode (edge-tts integration with voice input)
- [ ] Custom wake word training (hey_jarvis.onnx model)
- [ ] Screenshot / screen reading
- [ ] Email drafting and sending
- [ ] Calendar integration
- [ ] Spotify / media control API
- [ ] GUI tray icon (pystray)
- [ ] Windows startup automation (Task Scheduler)
