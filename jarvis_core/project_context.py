"""Project / codebase awareness for the current working tree."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from jarvis_core.config import PROJECT_ROOT_OVERRIDE, ROOT


def project_root() -> Path:
    if PROJECT_ROOT_OVERRIDE:
        return Path(PROJECT_ROOT_OVERRIDE).expanduser().resolve()
    # Prefer cwd if it looks like a project, else Javis root
    cwd = Path.cwd()
    markers = ("pyproject.toml", "package.json", "Cargo.toml", ".git", "requirements.txt")
    if any((cwd / m).exists() for m in markers):
        return cwd
    return ROOT


def tree_summary(max_files: int = 40) -> str:
    root = project_root()
    skip = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".jarvis_cache",
        ".mypy_cache",
    }
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(root)
        for fn in filenames:
            if fn.startswith(".") and fn not in (".env.example",):
                continue
            rel = str(rel_dir / fn) if str(rel_dir) != "." else fn
            files.append(rel)
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break
    header = f"Project root: {root}\nFiles (sample {len(files)}):\n"
    return header + "\n".join(f"  - {f}" for f in files)


def read_project_file(rel_path: str, max_chars: int = 4000) -> str:
    root = project_root()
    path = (root / rel_path).resolve()
    if not str(path).startswith(str(root)):
        return "Path escapes project root — blocked."
    if not path.exists():
        return f"File not found: {rel_path}"
    try:
        text = path.read_text(errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + "\n… [truncated]"
        return text
    except Exception as exc:
        return f"Read error: {exc}"


def context_block() -> str:
    return tree_summary()
