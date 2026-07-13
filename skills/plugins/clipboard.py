"""Clipboard intelligence plugin for J.A.R.V.I.S."""

from __future__ import annotations

import subprocess

PLUGIN_NAME = "clipboard"
PLUGIN_DESCRIPTION = "Read, analyze, or act on clipboard contents"
PLUGIN_TRIGGERS = [
    r"(?:read|show|get|what's on|whats on|what is on|what did i copy|check)\s+(?:my\s+)?clipboard",
    r"(?:read|show|get)\s+what\s+i\s+(?:just\s+)?copied",
    r"(?:translate|summarize|summarise|analyze|analyse)\s+(?:my\s+)?(?:clipboard|what\s+i\s+copied)",
]


def plugin_execute(raw_match: str = "", **kwargs) -> str:
    try:
        r = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        content = r.stdout.strip()
    except Exception as e:
        return f"Failed to read clipboard: {e}"

    if not content:
        return "Your clipboard is empty."

    # Truncate if very long
    display = content if len(content) <= 500 else content[:500] + "... (truncated)"

    lower = raw_match.lower()
    if "translate" in lower:
        return f"Clipboard contents for translation:\n{display}"
    elif "summar" in lower:
        return f"Clipboard contents for summary:\n{display}"
    elif "analy" in lower:
        return f"Clipboard contents for analysis:\n{display}"
    else:
        return f"Your clipboard contains:\n{display}"
