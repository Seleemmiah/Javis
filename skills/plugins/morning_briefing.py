"""Morning briefing plugin for J.A.R.V.I.S."""

from __future__ import annotations

import datetime

from jarvis_core.calendar_mac import todays_events
from skills.system_info import battery_status
from skills.web import weather

PLUGIN_NAME = "morning_briefing"
PLUGIN_DESCRIPTION = "Provides a morning summary of weather, battery, and calendar events."
PLUGIN_TRIGGERS = [
    r"good\s+morning",
    r"morning\s+briefing",
    r"daily\s+briefing",
    r"start\s+my\s+day",
]

def plugin_execute(raw_match: str = "", **kwargs) -> str:
    now = datetime.datetime.now()
    time_str = now.strftime("%I:%M %p")
    
    # Get weather (defaulting to London if OPENWEATHER_API_KEY isn't set perfectly, or IP based if we could, but we'll ask the weather module for a default city or just skip it if it requires args)
    # The weather function in web.py requires a city. We will default to a placeholder or ask them to configure it.
    w = weather("London") # You can change this city in the code!
    
    # Get battery
    batt = battery_status()
    
    # Get calendar
    cal = todays_events(limit=5)
    if "No events" in cal:
        cal_summary = "Your calendar is clear for today."
    elif "Calendar error" in cal or "Grant Automation" in cal:
        cal_summary = "I don't have permission to read your Apple Calendar yet."
    else:
        # Count lines that have times (rough estimate of events)
        event_count = len([line for line in cal.splitlines() if "—" in line])
        cal_summary = f"You have {event_count} events scheduled for today. {cal}"

    briefing = (
        f"Good morning, sir. It is currently {time_str}. "
        f"System battery is at {batt}. "
        f"Weather update: {w}. "
        f"{cal_summary}"
    )
    
    return briefing
