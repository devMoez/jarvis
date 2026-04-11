"""
Video Generation — Phase 7
Providers:
  - Runway ML (Gen-3 Alpha) — text-to-video, image-to-video
  - Stability AI (Stable Video Diffusion) — image-to-video
  - Replicate (AnimateDiff / Zeroscope) — text-to-video fallback

All outputs saved to videos_out/ directory.
"""
from __future__ import annotations
import os, time, base64, datetime
from pathlib import Path

_VID_OUT = Path(__file__).parent.parent / "videos_out"


def _save_video(data: bytes, ext: str = "mp4", prefix: str = "vid") -> Path:
    _VID_OUT.mkdir(parents=True, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _VID_OUT / f"{prefix}_{ts}.{ext}"
    path.write_bytes(data)
    return path


# ── Runway ML — text-to-video ─────────────────────────────────────────────────
def _runway_text_to_video(
    prompt:   str,
    duration: int = 4,
    ratio:    str = "1280:768",
) -> tuple[bool, str]:
    """
    Generate video with Runway Gen-3 Alpha via their API.
    Requires RUNWAYML_API_KEY.
    """
    key = os.getenv("RUNWAYML_API_KEY", "").strip()
    if not key:
        return False, "no RUNWAYML_API_KEY"

    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
            "X-Runway-Version": "2024-11-06",
        }
        payload = {
            "promptText":  prompt,
            "model":       "gen3a_turbo",
            "duration":    duration,
            "ratio":       ratio,
            "watermark":   False,
        }
        r = httpx.post(
            "https://api.dev.runwayml.com/v1/image_to_video",
            json=payload, headers=headers, timeout=30,
        )
        if r.status_code not in (200, 201):
            return False, f"Runway {r.status_code}: {r.text[:200]}"

        task_id = r.json().get("id")
        if not task_id:
            return False, "No task id returned"

        # Poll for completion (max 5 min)
        for _ in range(60):
            time.sleep(5)
            poll = httpx.get(
                f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                headers=headers, timeout=30,
            )
            pdata = poll.json()
            status = pdata.get("status")
            if status == "SUCCEEDED":
                outputs = pdata.get("output", [])
                if not outputs:
                    return False, "No output in Runway response"
                vid_url = outputs[0]
                vid_r   = httpx.get(vid_url, timeout=120)
                out     = _save_video(vid_r.content, "mp4", "runway")
                return True, str(out)
            if status in ("FAILED", "CANCELLED"):
                return False, f"Runway task {status}: {pdata.get('failure','')}"

        return False, "Runway video generation timed out (5 min)"
    except Exception as e:
        return False, str(e)


def _runway_image_to_video(
    image_path: str,
    prompt:     str  = "",
    duration:   int  = 4,
    ratio:      str  = "1280:768",
) -> tuple[bool, str]:
    """
    Animate an image into a video with Runway Gen-3.
    """
    key = os.getenv("RUNWAYML_API_KEY", "").strip()
    if not key:
        return False, "no RUNWAYML_API_KEY"

    img = Path(image_path)
    if not img.exists():
        return False, f"File not found: {image_path}"

    try:
        import httpx
        ext  = img.suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        b64  = base64.b64encode(img.read_bytes()).decode()
        data_uri = f"data:{mime};base64,{b64}"

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
            "X-Runway-Version": "2024-11-06",
        }
        payload: dict = {
            "promptImage": data_uri,
            "model":       "gen3a_turbo",
            "duration":    duration,
            "ratio":       ratio,
            "watermark":   False,
        }
        if prompt:
            payload["promptText"] = prompt

        r = httpx.post(
            "https://api.dev.runwayml.com/v1/image_to_video",
            json=payload, headers=headers, timeout=30,
        )
        if r.status_code not in (200, 201):
            return False, f"Runway {r.status_code}: {r.text[:200]}"

        task_id = r.json().get("id")
        for _ in range(60):
            time.sleep(5)
            poll   = httpx.get(
                f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                headers=headers, timeout=30,
            )
            pdata  = poll.json()
            status = pdata.get("status")
            if status == "SUCCEEDED":
                vid_url = (pdata.get("output") or [""])[0]
                vid_r   = httpx.get(vid_url, timeout=120)
                out     = _save_video(vid_r.content, "mp4", "runway_i2v")
                return True, str(out)
            if status in ("FAILED", "CANCELLED"):
                return False, f"Runway {status}: {pdata.get('failure','')}"

        return False, "Runway image-to-video timed out"
    except Exception as e:
        return False, str(e)


# ── Replicate — text-to-video fallback (Zeroscope v2 XL) ─────────────────────
def _replicate_text_to_video(
    prompt:  str,
    fps:     int = 24,
    seconds: int = 3,
) -> tuple[bool, str]:
    key = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not key:
        return False, "no REPLICATE_API_TOKEN"

    try:
        import httpx
        headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
        payload = {
            "version": "9f747673945c62801b13b84701c783929c0ee784e4748ec062204894dda1a351",  # zeroscope_v2_xl
            "input":   {
                "prompt":    prompt,
                "num_frames": fps * seconds,
                "fps":       fps,
                "width":     576,
                "height":    320,
                "num_inference_steps": 40,
            },
        }
        r = httpx.post("https://api.replicate.com/v1/predictions",
                       json=payload, headers=headers, timeout=30)
        if r.status_code not in (200, 201):
            return False, f"Replicate {r.status_code}: {r.text}"

        pred_id = r.json().get("id")
        for _ in range(60):
            time.sleep(5)
            poll  = httpx.get(f"https://api.replicate.com/v1/predictions/{pred_id}",
                              headers=headers, timeout=30)
            pdata = poll.json()
            status = pdata.get("status")
            if status == "succeeded":
                output = pdata.get("output")
                if isinstance(output, list):
                    output = output[0]
                vid_r = httpx.get(output, timeout=120)
                out   = _save_video(vid_r.content, "mp4", "replicate")
                return True, str(out)
            if status in ("failed", "canceled"):
                return False, f"Replicate {status}: {pdata.get('error','')}"

        return False, "Replicate video generation timed out"
    except Exception as e:
        return False, str(e)


# ── Stability AI — image-to-video ─────────────────────────────────────────────
def _stability_image_to_video(
    image_path: str,
    motion_bucket_id: int = 127,
    cond_aug: float = 0.02,
) -> tuple[bool, str]:
    key = os.getenv("STABILITY_API_KEY", "").strip()
    if not key:
        return False, "no STABILITY_API_KEY"

    img = Path(image_path)
    if not img.exists():
        return False, f"File not found: {image_path}"

    try:
        import httpx
        with open(image_path, "rb") as f:
            r = httpx.post(
                "https://api.stability.ai/v2beta/image-to-video",
                headers={"authorization": f"Bearer {key}"},
                files={"image": (img.name, f, "image/png")},
                data={
                    "seed": 0,
                    "cfg_scale": 2.5,
                    "motion_bucket_id": motion_bucket_id,
                },
                timeout=60,
            )
        if r.status_code != 200:
            return False, f"Stability {r.status_code}: {r.text[:200]}"

        gen_id = r.json().get("id")
        if not gen_id:
            return False, "No generation id returned"

        # Poll for result
        for _ in range(60):
            time.sleep(5)
            poll = httpx.get(
                f"https://api.stability.ai/v2beta/image-to-video/result/{gen_id}",
                headers={"authorization": f"Bearer {key}", "accept": "video/*"},
                timeout=30,
            )
            if poll.status_code == 202:
                continue  # still generating
            if poll.status_code == 200:
                out = _save_video(poll.content, "mp4", "stability_i2v")
                return True, str(out)
            return False, f"Stability result error {poll.status_code}: {poll.text[:200]}"

        return False, "Stability image-to-video timed out"
    except Exception as e:
        return False, str(e)


# ── Public API ────────────────────────────────────────────────────────────────
def text_to_video(
    prompt:   str,
    duration: int = 4,
    provider: str = "auto",
) -> tuple[bool, str]:
    """
    Generate a video from a text prompt.
    Chain: Runway (if key) → Replicate fallback
    """
    if provider in ("runway", "auto"):
        ok, result = _runway_text_to_video(prompt, duration=duration)
        if ok:
            return True, result

    if provider in ("replicate", "auto"):
        ok, result = _replicate_text_to_video(prompt, seconds=min(duration, 4))
        if ok:
            return True, result

    return False, result


def image_to_video(
    image_path: str,
    prompt:     str  = "",
    duration:   int  = 4,
    provider:   str  = "auto",
) -> tuple[bool, str]:
    """
    Animate an image into a video.
    Chain: Runway (if key) → Stability AI (if key) → error
    """
    if provider in ("runway", "auto"):
        ok, result = _runway_image_to_video(image_path, prompt=prompt, duration=duration)
        if ok:
            return True, result

    if provider in ("stability", "auto"):
        ok, result = _stability_image_to_video(image_path)
        if ok:
            return True, result

    return False, result
