"""Screen awareness — capture desktop and describe (vision API free-path + OCR)."""

from __future__ import annotations

import base64
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from jarvis_core.config import CACHE_DIR, IS_MAC, OPENAI_API_KEY, JARVIS_MODEL


def capture_screen(path: Optional[str] = None) -> str:
    if not path:
        path = str(
            CACHE_DIR
            / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if IS_MAC:
        subprocess.run(["screencapture", "-x", path], check=False)
    else:
        # best-effort
        try:
            from PIL import ImageGrab

            ImageGrab.grab().save(path)
        except Exception:
            return ""
    return path if Path(path).exists() else ""


def ocr_screen(path: str) -> str:
    """Free OCR via tesseract if installed."""
    try:
        r = subprocess.run(
            ["tesseract", path, "stdout"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (r.stdout or "").strip()
        return text[:3000] if text else ""
    except Exception:
        return ""


def describe_screen(question: str = "What is on the screen?") -> str:
    """
    Capture screen and explain.
    Uses OpenAI vision if OPENAI_API_KEY set (optional).
    Otherwise free OCR (tesseract) or path-only fallback.
    """
    path = capture_screen()
    if not path:
        return "I couldn't capture the screen."

    # Optional vision (uses key if present — not required)
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY)
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            resp = client.chat.completions.create(
                model=JARVIS_MODEL if "mini" not in JARVIS_MODEL else "gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are J.A.R.V.I.S. Describe the screen briefly "
                                    f"and answer: {question}. Be concise (3-6 sentences)."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=400,
            )
            return (resp.choices[0].message.content or "").strip() + f" (Saved: {path})"
        except Exception as exc:
            # fall through to OCR
            vision_err = str(exc)
    else:
        vision_err = "no vision API key"

    ocr = ocr_screen(path)
    if ocr:
        return (
            f"Screen captured to {path}. Visible text (OCR):\n{ocr[:1500]}"
        )
    return (
        f"Screen captured to {path}. "
        f"Vision unavailable ({vision_err}). "
        "Install tesseract for free OCR (`brew install tesseract`), "
        "or set OPENAI_API_KEY for full visual analysis."
    )
