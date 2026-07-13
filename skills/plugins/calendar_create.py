"""Calendar event creation plugin for J.A.R.V.I.S."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta

PLUGIN_NAME = "calendar_create"
PLUGIN_DESCRIPTION = "Create a new event in the Apple Calendar app."
PLUGIN_TRIGGERS = [
    r"schedule\s+(?:a|an)\s+(.+?)\s+(?:for|at|on)\s+(.+)",
    r"block\s+off\s+(\d+)\s*(hour|hr|minute|min)s?\s+(?:for\s+)?(.+?)\s+(?:at|on|for)\s+(.+)",
    r"add\s+(?:an\s+)?event\s+(?:called\s+)?(.+?)\s+(?:for|at|on)\s+(.+)",
]


def _parse_time_and_duration(time_text: str, duration_hours: float = 1.0) -> tuple[int, int, int]:
    """Parse time text like '5pm', 'tomorrow at 2:30pm', 'in 2 hours'."""
    now = datetime.now()
    target = now
    
    time_text_lower = time_text.lower()
    
    if "tomorrow" in time_text_lower:
        target += timedelta(days=1)
        
    # Check for "in X hours/minutes"
    m = re.search(r"in\s+(\d+)\s*(hour|hr|minute|min)s?", time_text_lower)
    if m:
        val = int(m.group(1))
        if m.group(2).startswith("hour") or m.group(2).startswith("hr"):
            target += timedelta(hours=val)
        else:
            target += timedelta(minutes=val)
        return target.hour, target.minute, target.day

    # Check for exact time like "5pm", "14:30", "5:30 pm"
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_text_lower)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        target = target.replace(hour=hour, minute=minute, second=0)
        
        # If the time has already passed today, assume tomorrow
        if target < now and "tomorrow" not in time_text_lower:
            target += timedelta(days=1)
            
        return target.hour, target.minute, target.day
        
    return now.hour + 1, 0, now.day # Default to next hour if unparseable


def plugin_execute(raw_match: str = "", **kwargs) -> str:
    title = ""
    time_text = ""
    duration_hours = 1.0
    
    # 1. "block off X hours for Y at Z"
    m = re.search(PLUGIN_TRIGGERS[1], raw_match, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("min"):
            duration_hours = val / 60.0
        else:
            duration_hours = float(val)
        title = m.group(3).strip()
        time_text = m.group(4).strip()
    else:
        # 2. "schedule a X for Y" / "add event X for Y"
        for pattern in [PLUGIN_TRIGGERS[0], PLUGIN_TRIGGERS[2]]:
            m = re.search(pattern, raw_match, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
                time_text = m.group(2).strip()
                break
                
    if not title or not time_text:
        return "I need an event name and a time to schedule it."
        
    hour, minute, day = _parse_time_and_duration(time_text, duration_hours)
    
    # Convert duration to minutes for AppleScript
    duration_mins = int(duration_hours * 60)
    
    safe_title = title.replace('"', '\\"')
    
    # AppleScript to create event in default calendar
    script = f'''
    tell application "Calendar"
        set startDate to current date
        set day of startDate to {day}
        set hours of startDate to {hour}
        set minutes of startDate to {minute}
        set seconds of startDate to 0
        
        set endDate to startDate + ({duration_mins} * minutes)
        
        tell calendar 1
            make new event with properties {{summary:"{safe_title}", start date:startDate, end date:endDate}}
        end tell
    end tell
    '''
    
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            err = r.stderr.strip()[:100]
            return f"Failed to create event. Make sure JARVIS has Calendar permissions. ({err})"
            
        time_str = f"{hour % 12 or 12}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"
        return f"Event '{title}' scheduled for {time_str} ({int(duration_mins)} mins)."
    except Exception as e:
        return f"Calendar error: {e}"
