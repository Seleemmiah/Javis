#!/usr/bin/env python3
"""List / preview J.A.R.V.I.S. voices (edge-tts neural + system).

Usage:
  python3 list_voices.py
  python3 list_voices.py --edge
  python3 list_voices.py --preview sonia
  python3 list_voices.py --preview Shelley
  python3 list_voices.py --british
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def list_system(british_only: bool) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    voices = engine.getProperty("voices") or []
    print("\n=== System voices (pyttsx3 / offline) ===")
    print(f"{'NAME':<40} ID")
    print("-" * 90)
    for v in voices:
        name = getattr(v, "name", "") or ""
        vid = v.id or ""
        langs = str(getattr(v, "languages", ""))
        blob = (name + vid + langs).lower()
        if british_only and not any(x in blob for x in ("en_gb", "en-gb", "british")):
            continue
        print(f"{name:<40} {vid}")


async def list_edge() -> None:
    import edge_tts

    voices = await edge_tts.list_voices()
    print("\n=== edge-tts neural voices (en-GB female recommended) ===")
    for v in voices:
        if not v["Locale"].startswith("en-GB"):
            continue
        mark = " ← default" if v["ShortName"] == "en-GB-SoniaNeural" else ""
        print(f"{v['ShortName']:<28} {v['Gender']:<8}{mark}")


def main() -> None:
    parser = argparse.ArgumentParser(description="List / preview TTS voices")
    parser.add_argument("--preview", "-p", help="Preview voice (sonia, libby, Shelley, …)")
    parser.add_argument("--british", action="store_true", help="UK system voices only")
    parser.add_argument("--edge", action="store_true", help="List edge-tts voices")
    parser.add_argument("--system", action="store_true", help="List system voices only")
    args = parser.parse_args()

    if args.preview:
        from jarvis_core.voice import Voice

        v = Voice()
        if not v.set_voice(args.preview):
            print(f"Voice not found: {args.preview}")
            return
        print(f"Previewing: {v.active_voice_name} (engine={v.tts_engine})")
        v.speak(
            "Hello. I am J.A.R.V.I.S. All systems are operational. "
            "How may I assist you?"
        )
        return

    if not args.system:
        try:
            asyncio.run(list_edge())
        except Exception as exc:
            print(f"[edge-tts list failed: {exc}]")
    if not args.edge:
        list_system(args.british)

    print(
        "\nTips:\n"
        "  export JARVIS_EDGE_VOICE=en-GB-SoniaNeural\n"
        "  export JARVIS_EDGE_VOICE=en-GB-LibbyNeural\n"
        "  python3 jarvis.py\n"
        "  In chat: 'use voice libby' / 'use voice sonia' / 'use voice system'\n"
    )


if __name__ == "__main__":
    main()

