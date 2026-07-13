"""iMessage integration plugin for J.A.R.V.I.S."""
from __future__ import annotations

import subprocess

PLUGIN_NAME = "imessage"
PLUGIN_DESCRIPTION = "Send an iMessage or SMS to a phone number or contact (e.g. 'text 555-0100 saying hello'). Requires Full Disk Access for python/terminal."
PLUGIN_TRIGGERS = [
    r"text\s+(.+?)\s+saying\s+(.+)",
    r"send (?:an )?(?:imessage|message|text) to\s+(.+?)\s+saying\s+(.+)"
]

def plugin_execute(
    contact: str = "",
    message: str = "",
    raw_match: str = "",
    **kwargs,
) -> str:
    # If triggered by regex, parse groups
    if raw_match:
        import re
        for trigger in PLUGIN_TRIGGERS:
            m = re.search(trigger, raw_match, re.IGNORECASE)
            if m:
                contact = m.group(1).strip()
                message = m.group(2).strip()
                break

    if not contact or not message:
        return "Need a contact and a message to send."
    
    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{contact}" of targetService
        send "{message}" to targetBuddy
    end tell
    '''
    
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return f"Message sent to {contact}."
    except subprocess.CalledProcessError as e:
        return f"Failed to send iMessage. Ensure contact is valid and JARVIS has Automation permissions: {e.stderr}"
    except Exception as e:
        return f"Failed to send iMessage: {e}"
