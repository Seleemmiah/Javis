"""Full local shell access for J.A.R.V.I.S."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from jarvis_core.config import DESTRUCTIVE_PATTERNS


def is_destructive(command: str) -> bool:
    c = command.lower().strip()
    return any(p in c for p in DESTRUCTIVE_PATTERNS)


def run_shell(
    command: str,
    timeout: int = 60,
    cwd: str | None = None,
    confirm_destructive: bool = True,
) -> str:
    """
    Execute a shell command with full local privileges of the user.
    Returns stdout+stderr summary for speech/HUD.
    """
    if not command or not command.strip():
        return "No command provided."

    if confirm_destructive and is_destructive(command):
        return (
            "That command looks highly destructive. "
            f"I will not run it without explicit override: {command}"
        )

    workdir = cwd or str(Path.home())
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
            env=os.environ.copy(),
            executable=os.environ.get("SHELL") or None,
        )
        out = (completed.stdout or "").strip()
        err = (completed.stderr or "").strip()
        code = completed.returncode

        pieces = []
        if out:
            pieces.append(out[:2500])
        if err:
            pieces.append(f"stderr: {err[:800]}")
        if not pieces:
            pieces.append(f"Command finished with exit code {code}.")
        elif code != 0:
            pieces.append(f"(exit {code})")
        return "\n".join(pieces)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s: {command}"
    except Exception as exc:
        return f"Shell error: {exc}"


def file_search(query: str, limit: int = 15) -> str:
    """macOS Spotlight (mdfind) or find fallback."""
    if not query:
        return "What should I search for?"
    home = str(Path.home())
    try:
        # Prefer Spotlight on macOS
        r = subprocess.run(
            ["mdfind", "-onlyin", home, query],
            capture_output=True,
            text=True,
            timeout=20,
        )
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][:limit]
        if lines:
            preview = "\n".join(lines)
            return f"Found {len(lines)} items:\n{preview}"
    except Exception:
        pass

    # Fallback find by name
    try:
        r = subprocess.run(
            ["find", home, "-iname", f"*{query}*", "-type", "f"],
            capture_output=True,
            text=True,
            timeout=25,
        )
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][:limit]
        if lines:
            return f"Found {len(lines)} files:\n" + "\n".join(lines)
        return f"No files matched '{query}'."
    except Exception as exc:
        return f"Search failed: {exc}"
