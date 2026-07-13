"""Timer / countdown plugin for J.A.R.V.I.S."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

PLUGIN_NAME = "timer"
PLUGIN_DESCRIPTION = "Set countdown timers and alarms"
PLUGIN_TRIGGERS = [
    r"(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(\d+)\s*(second|minute|hour|min|sec|hr)s?",
    r"(?:remind|alert)\s+me\s+in\s+(\d+)\s*(second|minute|hour|min|sec|hr)s?",
    r"countdown\s+(\d+)\s*(second|minute|hour|min|sec|hr)s?",
]

_active_timers: list[dict] = []
_timer_lock = threading.Lock()


def _unit_to_seconds(value: int, unit: str) -> int:
    unit = unit.lower().strip()
    if unit in ("second", "sec", "s"):
        return value
    if unit in ("minute", "min", "m"):
        return value * 60
    if unit in ("hour", "hr", "h"):
        return value * 3600
    return value * 60


def _timer_thread(name: str, seconds: int, speak) -> None:
    time.sleep(seconds)
    msg = f"Timer complete: {name}. {seconds} seconds have elapsed."
    with _timer_lock:
        _active_timers[:] = [t for t in _active_timers if t["name"] != name]
    if speak:
        speak(msg)
    else:
        print(f"[timer] {msg}")


def plugin_execute(
    value: int = 0,
    unit: str = "minute",
    speak=None,
    raw_match: str = "",
    **kwargs,
) -> str:
    if value <= 0:
        return "Please specify a positive duration."

    seconds = _unit_to_seconds(value, unit)
    end_time = datetime.now() + timedelta(seconds=seconds)
    name = f"{value} {unit}{'s' if value != 1 else ''}"

    timer_info = {
        "name": name,
        "seconds": seconds,
        "end_time": end_time.isoformat(),
    }
    with _timer_lock:
        _active_timers.append(timer_info)

    t = threading.Thread(
        target=_timer_thread,
        args=(name, seconds, speak),
        daemon=True,
        name=f"jarvis-timer-{name}",
    )
    t.start()

    end_str = end_time.strftime("%H:%M:%S")
    return f"Timer set for {name}. I'll alert you at {end_str}."
