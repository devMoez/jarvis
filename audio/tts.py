import asyncio
import io
import tempfile
import os
import sounddevice as sd
import soundfile as sf
import edge_tts
from config import TTS_VOICE, TTS_RATE

_is_speaking = False


def is_speaking() -> bool:
    return _is_speaking


def speak(text: str) -> None:
    """Convert text to speech and play it. Blocks until done."""
    global _is_speaking
    if not text.strip():
        return
    _is_speaking = True
    try:
        asyncio.run(_speak_async(text))
    finally:
        _is_speaking = False


async def _speak_async(text: str) -> None:
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await communicate.save(tmp_path)
        data, samplerate = sf.read(tmp_path)
        sd.play(data, samplerate)
        sd.wait()
    finally:
        os.unlink(tmp_path)


def speak_async_nonblocking(text: str) -> None:
    """Speak in a background thread (non-blocking)."""
    import threading
    t = threading.Thread(target=speak, args=(text,), daemon=True)
    t.start()
