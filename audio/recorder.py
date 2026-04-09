import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE, CHANNELS, SILENCE_THRESHOLD, SILENCE_DURATION, MAX_RECORD_SECONDS


def record_until_silence() -> np.ndarray:
    """Record audio from mic until silence is detected. Returns numpy array."""
    print("[recorder] Listening...")
    frames = []
    silent_chunks = 0
    chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks
    max_chunks = int(MAX_RECORD_SECONDS / 0.1)
    silence_chunks_needed = int(SILENCE_DURATION / 0.1)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32") as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_size)
            frames.append(chunk.copy())
            amplitude = np.abs(chunk).mean()
            if amplitude < SILENCE_THRESHOLD:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed and len(frames) > silence_chunks_needed:
                    break
            else:
                silent_chunks = 0

    audio = np.concatenate(frames, axis=0).flatten()
    return audio


def record_chunk(duration: float = 0.5) -> np.ndarray:
    """Record a fixed-duration audio chunk. Used by wake word detector."""
    samples = int(SAMPLE_RATE * duration)
    audio = sd.rec(samples, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32")
    sd.wait()
    return audio.flatten()
