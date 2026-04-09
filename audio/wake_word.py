import threading
import numpy as np
import sounddevice as sd
from typing import Callable
from config import SAMPLE_RATE, WAKE_WORD_SENSITIVITY

_listener_thread: threading.Thread | None = None
_stop_event = threading.Event()


def start_listening(on_detected: Callable[[], None]) -> None:
    """Start wake word listener in background thread."""
    global _listener_thread
    _stop_event.clear()
    _listener_thread = threading.Thread(
        target=_listen_loop,
        args=(on_detected,),
        daemon=True,
        name="WakeWordListener"
    )
    _listener_thread.start()
    print("[wake_word] Listening for 'Hey Jarvis'...")


def stop_listening() -> None:
    _stop_event.set()


def _listen_loop(on_detected: Callable[[], None]) -> None:
    try:
        import openwakeword
        from openwakeword.model import Model

        oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        chunk_size = 1280  # ~80ms at 16kHz

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=chunk_size) as stream:
            while not _stop_event.is_set():
                audio_chunk, _ = stream.read(chunk_size)
                audio_int16 = audio_chunk.flatten()
                prediction = oww_model.predict(audio_int16)

                for model_name, score in prediction.items():
                    if score >= WAKE_WORD_SENSITIVITY:
                        print(f"[wake_word] Detected! (score={score:.2f})")
                        oww_model.reset()
                        on_detected()
                        break

    except Exception as e:
        print(f"[wake_word] Error: {e}")
        print("[wake_word] Falling back to keyboard trigger (press Enter to activate)")
        _keyboard_fallback(on_detected)


def _keyboard_fallback(on_detected: Callable[[], None]) -> None:
    """Fallback: press Enter to activate Jarvis."""
    print("[wake_word] Press ENTER to talk to Jarvis (Ctrl+C to quit)")
    while not _stop_event.is_set():
        try:
            input()
            on_detected()
        except (EOFError, KeyboardInterrupt):
            break
