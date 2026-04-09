"""
Quick test: mic → STT → TTS pipeline
Run: python scripts/test_audio.py
"""
import sys
sys.path.insert(0, "..")

from audio.recorder import record_until_silence
from audio.stt import transcribe
from audio.tts import speak

print("Testing TTS...")
speak("Jarvis audio system online. Testing microphone now.")

print("\nSpeak something (will stop after 1.5s silence)...")
audio = record_until_silence()
print(f"Recorded {len(audio)} samples ({len(audio)/16000:.1f}s)")

print("Transcribing...")
text = transcribe(audio)
print(f"You said: '{text}'")

speak(f"I heard you say: {text}")
print("Audio test complete.")
