"""Apple Reminders plugin for J.A.R.V.I.S. — syncs to iPhone via iCloud."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta

PLUGIN_NAME = "reminders"
PLUGIN_DESCRIPTION = "Create reminders in Apple Reminders app (syncs to iPhone)"
PLUGIN_TRIGGERS = [
    r"remind\s+me\s+(?:to\s+)?(.+)",
    r"set\s+(?:a\s+)?reminder\s+(?:to|for)\s+(.+)",
    r"add\s+(?:a\s+)?reminder\s+(.+)",
]


def _parse_time(text: str):
    """Extract time from text like 'at 5pm', 'at 14:30', 'in 30 minutes'."""
    # "at 5pm" / "at 5:30pm"
    m = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        # Remove the time part from the reminder text
        clean = text[: m.start()].strip().rstrip(",").strip()
        return hour, minute, clean

    # "in 30 minutes" / "in 2 hours"
    m = re.search(r"in\s+(\d+)\s*(minute|min|hour|hr)s?", text, re.IGNORECASE)
    if m:
        value = int(m.group(1))
        unit = m.group(2).lower()
        now = datetime.now()
        if unit in ("hour", "hr"):
            target = now + timedelta(hours=value)
        else:
            target = now + timedelta(minutes=value)
        clean = text[: m.start()].strip().rstrip(",").strip()
        return target.hour, target.minute, clean

    return None, None, text


def plugin_execute(raw_match: str = "", **kwargs) -> str:
    # Extract reminder text from trigger
    reminder_text = ""
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            reminder_text = m.group(1).strip()
            break

    if not reminder_text:
        reminder_text = raw_match.strip()

    if not reminder_text:
        return "What should I remind you about?"

    # Parse time
    hour, minute, clean_text = _parse_time(reminder_text)
    if not clean_text:
        clean_text = reminder_text

    # Escape quotes for AppleScript
    safe_text = clean_text.replace('"', '\\"')

    if hour is not None:
        # Reminder with a specific time
        script = f'''
        tell application "Reminders"
            set reminderDate to current date
            set hours of reminderDate to {hour}
            set minutes of reminderDate to {minute}
            set seconds of reminderDate to 0
            make new reminder in default list with properties {{name:"{safe_text}", remind me date:reminderDate}}
        end tell
        '''
        time_str = f"{hour % 12 or 12}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"
        confirm = f"Reminder set: '{clean_text}' at {time_str}. It will sync to your iPhone."
    else:
        # Reminder without time
        script = f'''
        tell application "Reminders"
            make new reminder in default list with properties {{name:"{safe_text}"}}
        end tell
        '''
        confirm = f"Reminder created: '{clean_text}'. It will sync to your iPhone."

    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            err = r.stderr.strip()[:120]
            return f"Failed to create reminder. macOS may need permission. ({err})"
        return confirm
    except Exception as e:
        return f"Reminder error: {e}"
