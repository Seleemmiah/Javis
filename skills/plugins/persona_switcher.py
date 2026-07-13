"""Persona switcher plugin for J.A.R.V.I.S."""

from __future__ import annotations

import re

from jarvis_core.personas import set_active_persona, list_personas

PLUGIN_NAME = "persona_switcher"
PLUGIN_DESCRIPTION = "Switch JARVIS's personality mode (e.g. code, chill, focus, lab, default)"
PLUGIN_TRIGGERS = [
    r"switch\s+to\s+(\w+)\s+mode",
    r"activate\s+(\w+)\s+protocol",
    r"change\s+persona\s+to\s+(\w+)",
]

def plugin_execute(raw_match: str = "", **kwargs) -> str:
    # Extract the requested mode from the trigger match
    mode = "default"
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            mode = m.group(1).lower()
            break

    available = list_personas()
    if mode not in available:
        return f"I don't have a '{mode}' mode. Available modes are: {', '.join(available)}."

    new_persona = set_active_persona(mode)
    return new_persona.greeting
