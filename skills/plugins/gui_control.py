"""Full OS GUI Automation plugin for J.A.R.V.I.S."""
from __future__ import annotations

import time

PLUGIN_NAME = "gui_control"
PLUGIN_DESCRIPTION = "Take physical control of the mouse and keyboard to interact with the screen natively. Set action_type to one of: click, type, press, scroll, position. Pass x, y for click. Pass text for type. Pass key for press."
PLUGIN_TRIGGERS = [
    r"click\s+at\s+(\d+)[,\s]+(\d+)",
    r"type\s+text\s+(.+)",
    r"press\s+(enter|return|esc|space|tab)",
    r"scroll\s+(up|down)"
]

def plugin_execute(
    action_type: str = "click",
    x: int = 0,
    y: int = 0,
    text: str = "",
    key: str = "",
    **kwargs,
) -> str:
    try:
        import pyautogui
    except ImportError:
        return "pyautogui is not installed. GUI automation is unavailable."
        
    # Fail-safe settings
    pyautogui.FAILSAFE = True
    
    if action_type == "click":
        pyautogui.click(x=int(x), y=int(y))
        return f"Clicked at ({x}, {y})."
    
    elif action_type == "type":
        if not text:
            return "No text provided to type."
        pyautogui.write(text, interval=0.02)
        return f"Typed: {text}"
        
    elif action_type == "press":
        if not key:
            return "No key provided to press."
        pyautogui.press(key)
        return f"Pressed {key}."
        
    elif action_type == "scroll":
        amount = 10 if text == "up" else -10
        pyautogui.scroll(amount)
        return f"Scrolled {text}."
        
    elif action_type == "position":
        pos = pyautogui.position()
        return f"Mouse is currently at {pos}."
        
    return f"Unknown GUI action: {action_type}"
