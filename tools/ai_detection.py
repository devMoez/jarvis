"""
AI Detection — Phase 8
Detect whether content was AI-generated.

Image AI detection:
  - Hive Moderation API (primary)
  - Illuminarty API (fallback)

Text AI detection:
  - Sapling AI API (primary)
  - ZeroGPT API (fallback)
  - Winston AI API (third fallback)
"""
from __future__ import annotations
import os
from pathlib import Path


# ── Image AI detection ────────────────────────────────────────────────────────

def detect_image(path: str) -> dict:
    """
    Detect if an image was AI-generated.
    Returns {
        "is_ai":      bool,
        "confidence": float (0-100),
        "provider":   str,
        "detail":     str,
    }
    """
    result = _hive_image(path)
    if result.get("provider") != "error":
        return result
    result = _illuminarty_image(path)
    return result


def _hive_image(path: str) -> dict:
    key = os.getenv("HIVE_API_KEY", "").strip()
    if not key:
        return {"provider": "error", "detail": "no HIVE_API_KEY"}

    img = Path(path)
    if not img.exists():
        return {"provider": "error", "detail": f"File not found: {path}"}

    try:
        import httpx
        with open(path, "rb") as f:
            r = httpx.post(
                "https://api.thehive.ai/api/v2/task/sync",
                headers={"token": key},
                files={"media": (img.name, f)},
                data={"model": "ai-generated-image-detection"},
                timeout=60,
            )
        if r.status_code != 200:
            return {"provider": "error", "detail": f"Hive {r.status_code}: {r.text[:200]}"}

        data    = r.json()
        classes = (
            data.get("status", [{}])[0]
                .get("response", {})
                .get("output", [{}])[0]
                .get("classes", [])
        )
        ai_score = 0.0
        for cls in classes:
            if cls.get("class") == "ai-generated":
                ai_score = cls.get("score", 0.0) * 100
                break

        return {
            "is_ai":      ai_score >= 50,
            "confidence": round(ai_score, 1),
            "provider":   "Hive AI",
            "detail":     f"{ai_score:.1f}% AI-generated probability",
        }
    except Exception as e:
        return {"provider": "error", "detail": str(e)}


def _illuminarty_image(path: str) -> dict:
    key = os.getenv("ILLUMINARTY_API_KEY", "").strip()
    if not key:
        return {"provider": "error", "detail": "no ILLUMINARTY_API_KEY"}

    img = Path(path)
    if not img.exists():
        return {"provider": "error", "detail": f"File not found: {path}"}

    try:
        import httpx, base64
        b64 = base64.b64encode(img.read_bytes()).decode()
        r   = httpx.post(
            "https://api.illuminarty.ai/v1/detect",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"image": b64},
            timeout=60,
        )
        if r.status_code != 200:
            return {"provider": "error", "detail": f"Illuminarty {r.status_code}: {r.text[:200]}"}

        data  = r.json()
        score = data.get("ai_probability", 0.0) * 100
        return {
            "is_ai":      score >= 50,
            "confidence": round(score, 1),
            "provider":   "Illuminarty",
            "detail":     f"{score:.1f}% AI-generated probability",
        }
    except Exception as e:
        return {"provider": "error", "detail": str(e)}


# ── Text AI detection ─────────────────────────────────────────────────────────

def detect_text(text: str) -> dict:
    """
    Detect if text was AI-generated.
    Returns {
        "is_ai":      bool,
        "confidence": float (0-100),
        "provider":   str,
        "sentences":  list[{"sentence": str, "score": float}] | None,
        "detail":     str,
    }
    """
    result = _sapling_text(text)
    if result.get("provider") != "error":
        return result
    result = _zerogpt_text(text)
    if result.get("provider") != "error":
        return result
    return _winston_text(text)


def _sapling_text(text: str) -> dict:
    key = os.getenv("SAPLING_API_KEY", "").strip()
    if not key:
        return {"provider": "error", "detail": "no SAPLING_API_KEY"}

    try:
        import httpx
        r = httpx.post(
            "https://api.sapling.ai/api/v1/aidetect",
            json={"key": key, "text": text[:50000]},
            timeout=30,
        )
        if r.status_code != 200:
            return {"provider": "error", "detail": f"Sapling {r.status_code}: {r.text[:200]}"}

        data       = r.json()
        score      = data.get("score", 0.0) * 100
        sentences  = [
            {"sentence": s.get("sentence", ""), "score": round(s.get("score", 0.0) * 100, 1)}
            for s in data.get("sentence_scores", [])
        ]
        return {
            "is_ai":      score >= 50,
            "confidence": round(score, 1),
            "provider":   "Sapling AI",
            "sentences":  sentences[:10],
            "detail":     f"{score:.1f}% AI-generated",
        }
    except Exception as e:
        return {"provider": "error", "detail": str(e)}


def _zerogpt_text(text: str) -> dict:
    key = os.getenv("ZEROGPT_API_KEY", "").strip()
    if not key:
        return {"provider": "error", "detail": "no ZEROGPT_API_KEY"}

    try:
        import httpx
        r = httpx.post(
            "https://api.zerogpt.com/api/detect/detectText",
            headers={"ApiKey": key, "Content-Type": "application/json"},
            json={"input_text": text[:10000]},
            timeout=30,
        )
        if r.status_code != 200:
            return {"provider": "error", "detail": f"ZeroGPT {r.status_code}: {r.text[:200]}"}

        data  = r.json().get("data", {})
        score = float(data.get("fakePercentage", 0))
        return {
            "is_ai":      score >= 50,
            "confidence": round(score, 1),
            "provider":   "ZeroGPT",
            "sentences":  None,
            "detail":     f"{score:.1f}% AI-generated  |  words: {data.get('textWords', '?')}",
        }
    except Exception as e:
        return {"provider": "error", "detail": str(e)}


def _winston_text(text: str) -> dict:
    key = os.getenv("WINSTON_API_KEY", "").strip()
    if not key:
        return {"provider": "error", "detail": "no WINSTON_API_KEY — all text AI detection providers failed"}

    try:
        import httpx
        r = httpx.post(
            "https://api.gowinston.ai/functions/v1/predict",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"text": text[:50000], "language": "en", "sentences": True},
            timeout=30,
        )
        if r.status_code != 200:
            return {"provider": "error", "detail": f"Winston {r.status_code}: {r.text[:200]}"}

        data  = r.json()
        score = float(data.get("score", 0))
        return {
            "is_ai":      score >= 50,
            "confidence": round(score, 1),
            "provider":   "Winston AI",
            "sentences":  None,
            "detail":     f"{score:.1f}% AI-generated",
        }
    except Exception as e:
        return {"provider": "error", "detail": str(e)}


# ── Format result ─────────────────────────────────────────────────────────────
def fmt_detection_result(result: dict, label: str = "Content") -> str:
    if result.get("provider") == "error":
        return f"Detection failed: {result.get('detail', 'unknown error')}"

    verdict   = "AI-GENERATED" if result["is_ai"] else "HUMAN / NOT AI"
    emoji     = "🤖" if result["is_ai"] else "✅"
    conf      = result["confidence"]
    provider  = result["provider"]
    bar_fill  = int(conf / 5)
    bar       = "█" * bar_fill + "░" * (20 - bar_fill)

    lines = [
        f"  {emoji}  {label} — {verdict}",
        f"  Confidence:  {conf:.1f}%  [{bar}]",
        f"  Provider:    {provider}",
    ]
    if result.get("detail"):
        lines.append(f"  Detail:      {result['detail']}")

    sentences = result.get("sentences")
    if sentences:
        lines.append(f"\n  Sentence-level scores:")
        for s in sentences[:5]:
            sc = s["score"]
            flag = "🤖" if sc >= 50 else "  "
            lines.append(f"    {flag} {sc:5.1f}%  {s['sentence'][:80]}")

    return "\n".join(lines)
