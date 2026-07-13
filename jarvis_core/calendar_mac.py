"""macOS Calendar integration via AppleScript (free, local)."""

from __future__ import annotations

import subprocess
from jarvis_core.config import IS_MAC


def todays_events(limit: int = 12) -> str:
    if not IS_MAC:
        return "Calendar integration is currently available on macOS only."
    script = """
    set output to ""
    set todayStart to current date
    set time of todayStart to 0
    set todayEnd to todayStart + (1 * days)
    tell application "Calendar"
        set calList to every calendar
        repeat with c in calList
            try
                set evs to (every event of c whose start date ≥ todayStart and start date < todayEnd)
                repeat with e in evs
                    set s to start date of e
                    set sh to hours of s as string
                    set sm to minutes of s as string
                    if (count of sm) is 1 then set sm to "0" & sm
                    set output to output & sh & ":" & sm & " — " & (summary of e) & linefeed
                end repeat
            end try
        end repeat
    end tell
    return output
    """
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=25,
        )
        text = (r.stdout or "").strip()
        if not text:
            err = (r.stderr or "").strip()
            if err:
                return (
                    "I couldn't read Calendar. Grant Automation/Calendar access "
                    f"to Terminal in System Settings. ({err[:120]})"
                )
            return "No events on the calendar for today."
        lines = [ln for ln in text.splitlines() if ln.strip()][:limit]
        return "Today's schedule:\n" + "\n".join(lines)
    except Exception as exc:
        return f"Calendar error: {exc}"


def upcoming_events(hours: int = 24) -> str:
    """Broader window: next N hours (approx via today + list)."""
    base = todays_events()
    if hours <= 24:
        return base
    return base
