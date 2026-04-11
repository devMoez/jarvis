"""YouTube transcript fetcher — youtube-transcript-api"""
import re


def _extract_video_id(url_or_id: str) -> str | None:
    """Pull video ID from a YouTube URL or return raw ID if already bare."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    # Bare 11-char ID
    if re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id.strip()):
        return url_or_id.strip()
    return None


def get_transcript(url: str, with_timestamps: bool = True, language: str = "en") -> str:
    """
    Fetch the transcript of a YouTube video.
    Returns formatted transcript text with optional timestamps.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    except ImportError:
        return "Error: youtube-transcript-api not installed. Run: pip install youtube-transcript-api"

    vid = _extract_video_id(url)
    if not vid:
        return f"Could not extract video ID from: {url}"

    try:
        # Try requested language first, then auto-fallback
        try:
            transcript = YouTubeTranscriptApi.get_transcript(vid, languages=[language])
        except NoTranscriptFound:
            transcript = YouTubeTranscriptApi.get_transcript(vid)

        if not transcript:
            return "No transcript available for this video."

        lines = [f"[YouTube Transcript] https://youtu.be/{vid}\n"]
        for entry in transcript:
            start = entry.get("start", 0)
            text  = entry.get("text", "").replace("\n", " ").strip()
            if not text:
                continue
            if with_timestamps:
                mins, secs = divmod(int(start), 60)
                hrs,  mins = divmod(mins, 60)
                if hrs:
                    ts = f"[{hrs}:{mins:02d}:{secs:02d}]"
                else:
                    ts = f"[{mins}:{secs:02d}]"
                lines.append(f"{ts} {text}")
            else:
                lines.append(text)

        return "\n".join(lines)

    except TranscriptsDisabled:
        return f"Transcripts are disabled for this video (ID: {vid})."
    except Exception as e:
        return f"Transcript error: {e}"
