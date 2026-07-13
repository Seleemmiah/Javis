"""Webcam vision module for J.A.R.V.I.S."""
from __future__ import annotations

import base64
import os
from typing import Optional

from jarvis_core.config import OPENAI_API_KEY


def capture_frame_b64() -> Optional[str]:
    """Capture a single frame from the default webcam and return it as a base64 string."""
    try:
        import cv2
    except ImportError:
        print("opencv-python not installed.")
        return None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None

    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None

    # Encode to JPEG
    _, buffer = cv2.imencode('.jpg', frame)
    img_b64 = base64.b64encode(buffer).decode('utf-8')
    return img_b64


def describe_webcam() -> str:
    """Capture a frame and use OpenAI Vision to describe it."""
    if not OPENAI_API_KEY:
        return "Webcam vision requires OPENAI_API_KEY."

    img_b64 = capture_frame_b64()
    if not img_b64:
        return "Failed to capture webcam frame."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe what you see in this image briefly and accurately. If someone is holding something, describe what they are holding."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ],
                }
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content or "No description returned."
    except Exception as e:
        return f"Vision API error: {e}"
