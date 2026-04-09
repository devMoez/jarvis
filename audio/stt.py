import numpy as np
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, SAMPLE_RATE

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"[stt] Loading Whisper model '{WHISPER_MODEL}'...")
        _model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
        print("[stt] Model ready.")
    return _model


def transcribe(audio: np.ndarray) -> str:
    """Transcribe a numpy float32 audio array to text."""
    model = _get_model()
    # faster-whisper expects float32 mono at 16kHz
    audio = audio.astype(np.float32)
    segments, _ = model.transcribe(audio, beam_size=1, language="en", vad_filter=True)
    text = " ".join(seg.text for seg in segments).strip()
    return text
