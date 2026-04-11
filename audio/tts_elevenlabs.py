"""
TTS module — ElevenLabs primary, OpenAI TTS via OpenRouter fallback, edge-tts last resort.
Tracks monthly usage in data/tts_usage.json.
"""
import os, json, datetime, tempfile, threading
from pathlib import Path

_AUDIO_DIR   = Path(__file__).parent.parent / "audio_out"
_USAGE_FILE  = Path(__file__).parent.parent / "data" / "tts_usage.json"

# ElevenLabs default voice: Rachel
_EL_DEFAULT_VOICE    = "21m00Tcm4TlvDq8ikWAM"
_EL_VOICE_NAMES: dict[str, str] = {
    "rachel":  "21m00Tcm4TlvDq8ikWAM",
    "domi":    "AZnzlk1XvdvUeBnXmlld",
    "bella":   "EXAVITQu4vr4xnSDxMaL",
    "antoni":  "ErXwobaYiN019PkySvjV",
    "elli":    "MF3mGyEYCl7XYWbV9V6O",
    "josh":    "TxGEqnHWrfWFTfGW9XjX",
    "arnold":  "VR6AewLTigWG4xSOukaG",
    "adam":    "pNInz6obpgDQGcFmaJgB",
    "sam":     "yoZ06aMxZJJ28mfd3POQ",
}

# OpenAI TTS voices (via OpenRouter)
_OAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


# ── Usage tracking ────────────────────────────────────────────────────────────
def _load_usage() -> dict:
    if _USAGE_FILE.exists():
        try:
            return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_usage(data: dict) -> None:
    _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_usage(service: str, chars: int) -> None:
    month = datetime.date.today().strftime("%Y-%m")
    data  = _load_usage()
    m = data.setdefault(month, {})
    m[service] = m.get(service, 0) + chars
    _save_usage(data)


def get_usage_summary() -> str:
    data  = _load_usage()
    month = datetime.date.today().strftime("%Y-%m")
    m = data.get(month, {})
    lines = [f"TTS usage — {month}"]
    el   = m.get("elevenlabs", 0)
    oai  = m.get("openai", 0)
    edge = m.get("edge", 0)
    lines.append(f"  ElevenLabs : {el:,} chars  (free tier: 10,000/mo)")
    if el >= 8000:
        lines.append("  ⚠ Approaching ElevenLabs free tier limit (80%+)")
    lines.append(f"  OpenAI TTS : {oai:,} chars")
    lines.append(f"  edge-tts   : {edge:,} chars  (free, unlimited)")
    return "\n".join(lines)


# ── Save to file ──────────────────────────────────────────────────────────────
def _save_audio(data: bytes, ext: str = "mp3") -> Path:
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _AUDIO_DIR / f"{ts}.{ext}"
    path.write_bytes(data)
    return path


# ── Playback ──────────────────────────────────────────────────────────────────
def _play_file(path: Path) -> None:
    try:
        import soundfile as sf
        import sounddevice as sd
        data, sr = sf.read(str(path))
        sd.play(data, sr)
        sd.wait()
    except Exception:
        pass


# ── ElevenLabs ────────────────────────────────────────────────────────────────
def _speak_elevenlabs(text: str, voice: str = "", save: bool = False) -> tuple[bool, str]:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return False, "no key"

    voice_id = _EL_VOICE_NAMES.get(voice.lower(), voice or _EL_DEFAULT_VOICE)
    if not voice_id:
        voice_id = _EL_DEFAULT_VOICE

    try:
        import httpx
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=30,
        )
        if r.status_code != 200:
            return False, f"ElevenLabs {r.status_code}"

        audio = r.content
        record_usage("elevenlabs", len(text))
        path  = _save_audio(audio, "mp3")
        if not save:
            _play_file(path)
        return True, str(path)
    except Exception as e:
        return False, str(e)


# ── OpenAI TTS via OpenRouter ─────────────────────────────────────────────────
def _speak_openai_tts(text: str, voice: str = "onyx", save: bool = False) -> tuple[bool, str]:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return False, "no key"

    voice = voice if voice in _OAI_VOICES else "onyx"
    try:
        import openai
        client = openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
        )
        response = client.audio.speech.create(
            model="openai/tts-1",
            voice=voice,
            input=text,
        )
        audio = response.content
        record_usage("openai", len(text))
        path  = _save_audio(audio, "mp3")
        if not save:
            _play_file(path)
        return True, str(path)
    except Exception as e:
        return False, str(e)


# ── edge-tts fallback ─────────────────────────────────────────────────────────
def _speak_edge(text: str, save: bool = False) -> tuple[bool, str]:
    try:
        import asyncio, edge_tts
        from config import TTS_VOICE, TTS_RATE

        _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = _AUDIO_DIR / f"{ts}.mp3"

        async def _gen():
            comm = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
            await comm.save(str(path))

        asyncio.run(_gen())
        record_usage("edge", len(text))
        if not save:
            _play_file(path)
        return True, str(path)
    except Exception as e:
        return False, str(e)


# ── Public API ────────────────────────────────────────────────────────────────
def tts_speak(text: str, voice: str = "", save: bool = False, speed: float = 1.0) -> tuple[bool, str]:
    """
    Speak text. Tries ElevenLabs → OpenAI TTS → edge-tts.
    Returns (success, path_or_error).
    """
    if not text.strip():
        return False, "empty text"

    # Chunk if very long
    if len(text) > 5000:
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        paths  = []
        for chunk in chunks:
            ok, result = tts_speak(chunk, voice=voice, save=True)
            if ok:
                paths.append(result)
        if paths and not save:
            for p in paths:
                _play_file(Path(p))
        return bool(paths), ", ".join(paths)

    ok, result = _speak_elevenlabs(text, voice=voice, save=save)
    if ok:
        return True, result

    ok, result = _speak_openai_tts(text, voice=voice or "onyx", save=save)
    if ok:
        return True, result

    return _speak_edge(text, save=save)


def tts_speak_async(text: str, voice: str = "") -> None:
    """Non-blocking TTS."""
    threading.Thread(target=tts_speak, args=(text, voice), daemon=True).start()


def list_voices() -> str:
    lines = ["Available TTS voices:\n"]
    lines.append("ElevenLabs (requires ELEVENLABS_API_KEY):")
    for name in _EL_VOICE_NAMES:
        lines.append(f"  {name}")
    lines.append("\nOpenAI TTS via OpenRouter:")
    for v in _OAI_VOICES:
        lines.append(f"  {v}")
    lines.append("\nedge-tts: en-US-GuyNeural (default, always available)")
    return "\n".join(lines)
