"""
Advanced STT module — Phase 4
Primary:  Whisper via OpenRouter (openai/whisper-large-v3)
Fallback: AssemblyAI (universal-2 model)
Local:    faster-whisper (already in audio/stt.py — used as last resort)

Supports:
  transcribe_file(path, translate=False, summarize=False, speakers=False, language=None)
  listen_once(save=False)  — record mic then transcribe
"""

from __future__ import annotations
import os, io, json, datetime, threading, tempfile
from pathlib import Path
import numpy as np

_TRANSCRIPT_DIR = Path(__file__).parent.parent / "data" / "transcripts"

# ── Whisper via OpenRouter ────────────────────────────────────────────────────
def _whisper_openrouter(
    audio_path: str,
    translate: bool = False,
    language: str | None = None,
) -> tuple[bool, str]:
    """
    Transcribe audio file using Whisper via OpenRouter.
    Returns (success, transcript_text_or_error).
    """
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return False, "no OPENROUTER_API_KEY"

    try:
        import openai
        client = openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
        )
        with open(audio_path, "rb") as f:
            if translate:
                resp = client.audio.translations.create(
                    model="openai/whisper-large-v3",
                    file=f,
                )
            else:
                kwargs: dict = {"model": "openai/whisper-large-v3", "file": f}
                if language:
                    kwargs["language"] = language
                resp = client.audio.transcriptions.create(**kwargs)
        return True, resp.text.strip()
    except Exception as e:
        return False, str(e)


# ── AssemblyAI fallback ───────────────────────────────────────────────────────
def _assemblyai_transcribe(
    audio_path: str,
    translate: bool = False,
    summarize: bool = False,
    speakers: bool = False,
    language: str | None = None,
) -> tuple[bool, str]:
    """
    Transcribe audio file using AssemblyAI.
    Returns (success, formatted_text_or_error).
    """
    key = os.getenv("ASSEMBLYAI_KEY", "").strip()
    if not key:
        return False, "no ASSEMBLYAI_KEY"

    try:
        import assemblyai as aai
        aai.settings.api_key = key

        config_kwargs: dict = {}
        if speakers:
            config_kwargs["speaker_labels"] = True
        if summarize:
            config_kwargs["summarization"] = True
            config_kwargs["summary_model"] = aai.SummarizationModel.informative
            config_kwargs["summary_type"]  = aai.SummarizationType.bullets
        if language and not translate:
            config_kwargs["language_code"] = language
        if translate:
            # AssemblyAI doesn't translate — flag note
            pass

        config = aai.TranscriptionConfig(**config_kwargs)
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_path, config=config)

        if transcript.status == aai.TranscriptStatus.error:
            return False, f"AssemblyAI error: {transcript.error}"

        lines: list[str] = []

        if speakers and transcript.utterances:
            for utt in transcript.utterances:
                ts = _fmt_ts(utt.start)
                lines.append(f"[{ts}] Speaker {utt.speaker}: {utt.text}")
        else:
            lines.append(transcript.text or "")

        if summarize and hasattr(transcript, "summary") and transcript.summary:
            lines.append("\n── Summary ──")
            lines.append(transcript.summary)

        return True, "\n".join(lines).strip()
    except ImportError:
        return False, "assemblyai package not installed"
    except Exception as e:
        return False, str(e)


# ── Local faster-whisper (last resort) ───────────────────────────────────────
def _local_whisper(audio_path: str, translate: bool = False) -> tuple[bool, str]:
    try:
        from faster_whisper import WhisperModel
        from config import WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
        model = WhisperModel("base.en", device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
        task = "translate" if translate else "transcribe"
        segments, _ = model.transcribe(audio_path, beam_size=1, task=task, vad_filter=True)
        return True, " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        return False, str(e)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt_ts(ms: int) -> str:
    """Format milliseconds as HH:MM:SS."""
    s = ms // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _save_transcript(name: str, text: str) -> Path:
    _TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)[:40]
    path = _TRANSCRIPT_DIR / f"{ts}_{safe}.txt"
    path.write_text(text, encoding="utf-8")
    return path


# ── Public: transcribe a file ─────────────────────────────────────────────────
def transcribe_file(
    audio_path: str,
    translate:  bool = False,
    summarize:  bool = False,
    speakers:   bool = False,
    language:   str | None = None,
    save:       bool = True,
) -> tuple[bool, str, str | None]:
    """
    Transcribe an audio file.
    Returns (success, text_or_error, saved_path_or_None).
    Chain: OpenRouter Whisper → AssemblyAI → local faster-whisper.
    If summarize or speakers requested, uses AssemblyAI directly (OpenRouter Whisper doesn't support them).
    """
    text: str | None = None
    error: str = ""

    # If advanced features needed, prefer AssemblyAI
    if summarize or speakers:
        ok, result = _assemblyai_transcribe(
            audio_path, translate=translate, summarize=summarize,
            speakers=speakers, language=language
        )
        if ok:
            text = result
        else:
            error = result

    if text is None:
        # Try OpenRouter Whisper first
        ok, result = _whisper_openrouter(audio_path, translate=translate, language=language)
        if ok:
            text = result
        else:
            error = result
            # Fallback to AssemblyAI
            ok, result = _assemblyai_transcribe(
                audio_path, translate=translate, language=language
            )
            if ok:
                text = result
            else:
                error += f"; {result}"
                # Last resort: local
                ok, result = _local_whisper(audio_path, translate=translate)
                if ok:
                    text = result
                else:
                    error += f"; {result}"

    if text is None:
        return False, f"All STT providers failed: {error}", None

    saved_path: str | None = None
    if save and text:
        try:
            fname = Path(audio_path).stem
            p = _save_transcript(fname, text)
            saved_path = str(p)
        except Exception:
            pass

    return True, text, saved_path


# ── Public: live mic listen + transcribe ──────────────────────────────────────
def listen_once(save: bool = False, language: str | None = None) -> tuple[bool, str, str | None]:
    """
    Record from mic until silence, then transcribe.
    Returns (success, text_or_error, saved_path_or_None).
    """
    try:
        from audio.recorder import record_until_silence
        audio = record_until_silence()
        if audio is None or len(audio) < 1600:
            return False, "No audio captured", None
    except Exception as e:
        return False, f"Recording failed: {e}", None

    # Write numpy array to a temp wav file for API upload
    try:
        import soundfile as sf
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, audio.astype(np.float32), 16000)
    except Exception as e:
        return False, f"Could not save recording: {e}", None

    try:
        ok, text, saved = transcribe_file(tmp_path, language=language, save=save)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return ok, text, saved
