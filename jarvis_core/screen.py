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
    Uses Gemini Vision (free) if GEMINI_API_KEY set.
    Otherwise free OCR (tesseract) or path-only fallback.
    """
    path = capture_screen()
    if not path:
        return "I couldn't capture the screen."

    # --- Try Gemini Vision (free + smart) ---
    from jarvis_core.config import GEMINI_API_KEY, GEMINI_MODEL
    if GEMINI_API_KEY:
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            import requests as _requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{
                    "parts": [
                        {
                            "text": (
                                "You are J.A.R.V.I.S., a hyper-intelligent AI assistant. "
                                "You are looking at the user's screen right now. "
                                f"Describe what you see and answer: {question}. "
                                "If you see code, analyze it — mention the language, "
                                "any bugs, and suggest improvements. "
                                "Be concise (3-6 sentences). Speak naturally as JARVIS would."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": b64,
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 600,
                },
            }
            r = _requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return text
            raise Exception("Gemini returned no vision response")
        except Exception as exc:
            vision_err = str(exc)
    else:
        vision_err = "no Gemini API key"

    # --- Fallback: OpenAI Vision ---
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
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            vision_err = str(exc)

    # --- Fallback: OCR ---
    ocr = ocr_screen(path)
    if ocr:
        return (
            f"Screen captured. Visible text (OCR):\n{ocr[:1500]}"
        )
    return (
        f"Screen captured to {path}. "
        f"Vision unavailable ({vision_err}). "
        "Install tesseract for free OCR (`brew install tesseract`), "
        "or set GEMINI_API_KEY for full visual analysis."
    )
