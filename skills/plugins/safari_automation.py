"""Safari automation plugin for J.A.R.V.I.S."""

from __future__ import annotations

import platform
import re
import subprocess
import urllib.parse

PLUGIN_NAME = "safari_automation"
PLUGIN_DESCRIPTION = "Control Safari to open web pages and search"
PLUGIN_TRIGGERS = [
    r"open\s+safari\s+and\s+(.+)",
    r"search\s+safari\s+for\s+(.+)",
    r"go\s+to\s+(.+)\s+in\s+safari",
]

def plugin_execute(raw_match: str = "", **kwargs) -> str:
    if platform.system() != "Darwin":
        return "Safari automation is only supported on macOS."

    # Extract the query/url
    query = ""
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            break
            
    if not query:
        return "What would you like to do in Safari?"

    # Decide if it's a URL or a search
    is_url = "." in query and (" " not in query or query.startswith("http"))
    
    if is_url:
        if not query.startswith("http"):
            url = f"https://{query}"
        else:
            url = query
        action = f"Opening {url} in Safari."
    else:
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        action = f"Searching Safari for '{query}'."

    applescript = f'''
    tell application "Safari"
        activate
        if (count of windows) = 0 then
            make new document
        end if
        set URL of document 1 to "{url}"
    end tell
    '''

    try:
        subprocess.run(["osascript", "-e", applescript], check=True, capture_output=True)
        return action
    except Exception as e:
        return f"Failed to automate Safari. (Error: {e})"
