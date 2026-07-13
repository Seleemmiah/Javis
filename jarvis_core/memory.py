"""Persistent memory for J.A.R.V.I.S."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from jarvis_core.config import MEMORY_FILE


def load_memory() -> dict[str, Any]:
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_memory(data: dict[str, Any]) -> None:
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)


class Memory:
    def __init__(self) -> None:
        self.data = load_memory()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        save_memory(self.data)

    def title(self) -> str:
        name = self.data.get("name")
        if name:
            return str(name)
        return str(self.data.get("title", "sir"))

    def note(self, text: str) -> None:
        notes = self.data.setdefault("notes", [])
        notes.append({"text": text, "at": datetime.now().isoformat()})
        save_memory(self.data)

    def history_add(self, role: str, content: str, limit: int = 20) -> None:
        hist = self.data.setdefault("chat_history", [])
        hist.append({"role": role, "content": content, "at": datetime.now().isoformat()})
        self.data["chat_history"] = hist[-limit:]
        save_memory(self.data)

    def history(self) -> list[dict[str, str]]:
        return [
            {"role": h["role"], "content": h["content"]}
            for h in self.data.get("chat_history", [])
            if h.get("role") in ("user", "assistant")
        ]
