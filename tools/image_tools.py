"""
Image Tools — Phase 6
Provides:
  - analyze_image(path)          — describe/analyze an image via AI (Google Vision or LLM vision)
  - remove_bg(path)              — remove background (remove.bg API)
  - upscale_image(path, scale)   — upscale via Replicate (Real-ESRGAN)
  - generate_image(prompt, ...)  — generate image via Stability AI or Replicate (SDXL)
  - color_grade(path, style)     — apply a color grade / filter style

All outputs saved to images_out/ directory.
"""
from __future__ import annotations
import os, io, base64, datetime, json, tempfile
from pathlib import Path

_IMG_OUT = Path(__file__).parent.parent / "images_out"


def _save_output(data: bytes, ext: str = "png", prefix: str = "img") -> Path:
    _IMG_OUT.mkdir(parents=True, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _IMG_OUT / f"{prefix}_{ts}.{ext}"
    path.write_bytes(data)
    return path


# ── Analyze / describe an image ────────────────────────────────────────────────
def analyze_image(path: str, question: str = "") -> str:
    """
    Send an image to the LLM (vision model) and get a description or answer.
    Uses OpenRouter with a vision-capable model.
    Returns text description.
    """
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return "Error: no OPENROUTER_API_KEY set"

    img_path = Path(path)
    if not img_path.exists():
        return f"Error: file not found: {path}"

    ext = img_path.suffix.lower().lstrip(".")
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif",  "webp": "image/webp", "bmp": "image/bmp",
    }
    mime = mime_map.get(ext, "image/png")

    try:
        import base64, openai
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        client = openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
        )
        prompt_text = question or "Describe this image in detail."
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",       "text": prompt_text},
                    {"type": "image_url",  "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error analyzing image: {e}"


# ── Remove background ─────────────────────────────────────────────────────────
def remove_bg(path: str) -> tuple[bool, str]:
    """
    Remove background from an image using remove.bg API.
    Returns (success, output_path_or_error).
    Requires REMOVEBG_API_KEY env var.
    """
    key = os.getenv("REMOVEBG_API_KEY", "").strip()
    if not key:
        return False, "Error: no REMOVEBG_API_KEY set"

    img_path = Path(path)
    if not img_path.exists():
        return False, f"File not found: {path}"

    try:
        import httpx
        with open(path, "rb") as f:
            r = httpx.post(
                "https://api.remove.bg/v1.0/removebg",
                headers={"X-Api-Key": key},
                files={"image_file": f},
                data={"size": "auto"},
                timeout=60,
            )
        if r.status_code != 200:
            try:
                err = r.json().get("errors", [{}])[0].get("title", r.text)
            except Exception:
                err = r.text
            return False, f"remove.bg error {r.status_code}: {err}"

        out = _save_output(r.content, "png", "nobg")
        return True, str(out)
    except Exception as e:
        return False, str(e)


# ── Upscale image ─────────────────────────────────────────────────────────────
def upscale_image(path: str, scale: int = 4) -> tuple[bool, str]:
    """
    Upscale an image using Replicate (Real-ESRGAN).
    Returns (success, output_path_or_error).
    Requires REPLICATE_API_TOKEN env var.
    """
    key = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not key:
        return False, "Error: no REPLICATE_API_TOKEN set"

    img_path = Path(path)
    if not img_path.exists():
        return False, f"File not found: {path}"

    try:
        import httpx, time
        # Encode image as data URI
        ext  = img_path.suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        b64  = base64.b64encode(img_path.read_bytes()).decode()
        data_uri = f"data:{mime};base64,{b64}"

        # Clamp scale to supported values
        scale = min(max(scale, 2), 4)

        headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
        payload = {
            "version": "42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73abf41610695738c1d7b",  # Real-ESRGAN 4x
            "input":   {"image": data_uri, "scale": scale, "face_enhance": False},
        }
        # Create prediction
        r = httpx.post("https://api.replicate.com/v1/predictions",
                       json=payload, headers=headers, timeout=30)
        if r.status_code not in (200, 201):
            return False, f"Replicate error {r.status_code}: {r.text}"

        pred_id = r.json().get("id")
        if not pred_id:
            return False, "No prediction id returned"

        # Poll for completion (max 120s)
        for _ in range(40):
            time.sleep(3)
            poll = httpx.get(f"https://api.replicate.com/v1/predictions/{pred_id}",
                             headers=headers, timeout=30)
            pdata = poll.json()
            status = pdata.get("status")
            if status == "succeeded":
                output_url = pdata.get("output")
                if isinstance(output_url, list):
                    output_url = output_url[0]
                img_r = httpx.get(output_url, timeout=60)
                out = _save_output(img_r.content, "png", "upscaled")
                return True, str(out)
            if status in ("failed", "canceled"):
                return False, f"Replicate job {status}: {pdata.get('error','')}"

        return False, "Upscale timed out after 120s"
    except Exception as e:
        return False, str(e)


# ── Generate image ─────────────────────────────────────────────────────────────
def generate_image(
    prompt:          str,
    negative_prompt: str  = "",
    width:           int  = 1024,
    height:          int  = 1024,
    steps:           int  = 30,
    provider:        str  = "auto",
) -> tuple[bool, str]:
    """
    Generate an image from a text prompt.
    provider: "stability" | "replicate" | "auto"
    Returns (success, output_path_or_error).
    """
    # Try Stability AI first
    if provider in ("stability", "auto"):
        ok, result = _gen_stability(prompt, negative_prompt, width, height, steps)
        if ok:
            return True, result

    # Fallback: Replicate SDXL
    if provider in ("replicate", "auto"):
        ok, result = _gen_replicate(prompt, negative_prompt, width, height, steps)
        if ok:
            return True, result

    return False, result


def _gen_stability(prompt, negative_prompt, width, height, steps) -> tuple[bool, str]:
    key = os.getenv("STABILITY_API_KEY", "").strip()
    if not key:
        return False, "no STABILITY_API_KEY"
    try:
        import httpx
        body: dict = {
            "text_prompts": [{"text": prompt, "weight": 1.0}],
            "cfg_scale":    7,
            "width":        min(width, 1536),
            "height":       min(height, 1536),
            "steps":        min(steps, 50),
            "samples":      1,
        }
        if negative_prompt:
            body["text_prompts"].append({"text": negative_prompt, "weight": -1.0})

        r = httpx.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        if r.status_code != 200:
            return False, f"Stability {r.status_code}: {r.text[:200]}"

        data = r.json()
        img_b64 = data["artifacts"][0]["base64"]
        out = _save_output(base64.b64decode(img_b64), "png", "gen")
        return True, str(out)
    except Exception as e:
        return False, str(e)


def _gen_replicate(prompt, negative_prompt, width, height, steps) -> tuple[bool, str]:
    key = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not key:
        return False, "no REPLICATE_API_TOKEN"
    try:
        import httpx, time
        headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
        payload = {
            "version": "7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",  # SDXL
            "input":   {
                "prompt":          prompt,
                "negative_prompt": negative_prompt,
                "width":           width,
                "height":          height,
                "num_inference_steps": steps,
            },
        }
        r = httpx.post("https://api.replicate.com/v1/predictions",
                       json=payload, headers=headers, timeout=30)
        if r.status_code not in (200, 201):
            return False, f"Replicate {r.status_code}: {r.text}"

        pred_id = r.json().get("id")
        for _ in range(40):
            time.sleep(3)
            poll  = httpx.get(f"https://api.replicate.com/v1/predictions/{pred_id}",
                              headers=headers, timeout=30)
            pdata = poll.json()
            status = pdata.get("status")
            if status == "succeeded":
                output_url = pdata.get("output")
                if isinstance(output_url, list):
                    output_url = output_url[0]
                img_r = httpx.get(output_url, timeout=60)
                out   = _save_output(img_r.content, "png", "gen")
                return True, str(out)
            if status in ("failed", "canceled"):
                return False, f"Replicate {status}: {pdata.get('error','')}"

        return False, "Image generation timed out"
    except Exception as e:
        return False, str(e)


# ── Color grade / filter ───────────────────────────────────────────────────────
_GRADE_STYLES = {
    "vintage":       {"brightness": 1.05, "contrast": 0.85, "saturation": 0.70, "sepia": 0.35},
    "vivid":         {"brightness": 1.1,  "contrast": 1.3,  "saturation": 1.6,  "sepia": 0.0},
    "cool":          {"brightness": 1.0,  "contrast": 1.1,  "saturation": 1.1,  "sepia": 0.0, "tint": (0.9, 0.95, 1.15)},
    "warm":          {"brightness": 1.05, "contrast": 1.05, "saturation": 1.1,  "sepia": 0.0, "tint": (1.1, 1.0, 0.85)},
    "noir":          {"brightness": 1.0,  "contrast": 1.5,  "saturation": 0.0,  "sepia": 0.0},
    "dramatic":      {"brightness": 0.9,  "contrast": 1.7,  "saturation": 1.2,  "sepia": 0.0},
    "faded":         {"brightness": 1.1,  "contrast": 0.7,  "saturation": 0.8,  "sepia": 0.15},
    "cyberpunk":     {"brightness": 1.0,  "contrast": 1.3,  "saturation": 2.0,  "sepia": 0.0, "tint": (1.0, 0.8, 1.4)},
}

def list_grade_styles() -> list[str]:
    return list(_GRADE_STYLES.keys())


def color_grade(path: str, style: str) -> tuple[bool, str]:
    """
    Apply a color grading style to an image using Pillow.
    Returns (success, output_path_or_error).
    """
    try:
        from PIL import Image, ImageEnhance
        import numpy as _np
    except ImportError:
        return False, "Pillow not installed (pip install Pillow)"

    img_path = Path(path)
    if not img_path.exists():
        return False, f"File not found: {path}"

    style_lower = style.lower()
    if style_lower not in _GRADE_STYLES:
        return False, f"Unknown style '{style}'. Available: {', '.join(_GRADE_STYLES)}"

    try:
        from PIL import Image, ImageEnhance
        import numpy as _np

        params = _GRADE_STYLES[style_lower]
        img = Image.open(path).convert("RGB")

        # Brightness
        img = ImageEnhance.Brightness(img).enhance(params.get("brightness", 1.0))
        # Contrast
        img = ImageEnhance.Contrast(img).enhance(params.get("contrast", 1.0))
        # Saturation
        img = ImageEnhance.Color(img).enhance(params.get("saturation", 1.0))

        # Sepia
        sepia = params.get("sepia", 0.0)
        if sepia > 0:
            arr = _np.array(img, dtype=_np.float32) / 255.0
            r = arr[:,:,0] * (1 - sepia * 0.4) + arr[:,:,1] * sepia * 0.3 + arr[:,:,2] * sepia * 0.1
            g = arr[:,:,0] * sepia * 0.2         + arr[:,:,1] * (1 - sepia * 0.2)       + arr[:,:,2] * sepia * 0.0
            b = arr[:,:,0] * sepia * 0.1         + arr[:,:,1] * sepia * 0.1              + arr[:,:,2] * (1 - sepia * 0.2)
            arr[:,:,0] = _np.clip(r, 0, 1)
            arr[:,:,1] = _np.clip(g, 0, 1)
            arr[:,:,2] = _np.clip(b, 0, 1)
            img = Image.fromarray((_np.clip(arr, 0, 1) * 255).astype(_np.uint8))

        # Color tint
        tint = params.get("tint")
        if tint:
            arr = _np.array(img, dtype=_np.float32) / 255.0
            arr[:,:,0] = _np.clip(arr[:,:,0] * tint[0], 0, 1)
            arr[:,:,1] = _np.clip(arr[:,:,1] * tint[1], 0, 1)
            arr[:,:,2] = _np.clip(arr[:,:,2] * tint[2], 0, 1)
            img = Image.fromarray((_np.clip(arr, 0, 1) * 255).astype(_np.uint8))

        out = _save_output(b"", "png", f"grade_{style_lower}")
        img.save(str(out))
        return True, str(out)
    except Exception as e:
        return False, str(e)
