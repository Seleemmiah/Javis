"""Open Application plugin for J.A.R.V.I.S."""

from __future__ import annotations

import re
from skills.system_info import open_app

PLUGIN_NAME = "open_app"
PLUGIN_DESCRIPTION = "Open any macOS application by name."
PLUGIN_TRIGGERS = [
    r"(?:jarvis\s+)?open\s+(?:the\s+)?([a-zA-Z0-9\s]+?)(?:\s+app|\s+application)?$"
]

def plugin_execute(raw_match: str = "", **kwargs) -> str:
    # Extract the app name from the trigger
    app_name = ""
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            app_name = m.group(1).strip()
            break
            
    if not app_name:
        return "I didn't catch the application name."
        
    # Prevent catching generic commands if it matches something else
    if app_name.lower() in ("my", "the", "a", "an"):
        return ""
        
    return open_app(app_name)
