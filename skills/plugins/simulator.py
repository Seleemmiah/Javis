"""iOS Simulator launcher plugin for J.A.R.V.I.S."""

from __future__ import annotations

import json
import re
import subprocess

PLUGIN_NAME = "simulator"
PLUGIN_DESCRIPTION = "Launch a specific iOS Simulator by name (e.g. iPhone 17 Pro Max)"
PLUGIN_TRIGGERS = [
    r"(?:open|launch|start|boot|run)\s+(?:the\s+)?(?:ios\s+)?simulator\s+(?:for\s+)?(?:the\s+)?(.+)",
    r"(?:open|launch|start|boot|run)\s+(?:the\s+)?(.+?)\s+simulator",
    r"simulator\s+(.+)",
]


def _list_simulators() -> list[dict]:
    """Get all available simulators from xcrun simctl."""
    try:
        r = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        devices = []
        for runtime, devs in data.get("devices", {}).items():
            for d in devs:
                if d.get("isAvailable"):
                    devices.append({
                        "name": d["name"],
                        "udid": d["udid"],
                        "state": d.get("state", "Unknown"),
                        "runtime": runtime.split(".")[-1],
                    })
        return devices
    except Exception:
        return []


def _find_best_match(query: str, devices: list) -> dict:
    """Fuzzy match a device name from the query."""
    query_lower = query.lower().strip()
    
    # Exact match first
    for d in devices:
        if d["name"].lower() == query_lower:
            return d
    
    # Substring match
    for d in devices:
        if query_lower in d["name"].lower():
            return d
    
    # Word-by-word matching
    query_words = set(query_lower.split())
    best, best_score = None, 0
    for d in devices:
        name_words = set(d["name"].lower().split())
        score = len(query_words & name_words)
        if score > best_score:
            best_score = score
            best = d
    
    return best if best_score > 0 else None


def plugin_execute(raw_match: str = "", **kwargs) -> str:
    # Extract device name from trigger
    device_query = ""
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            device_query = m.group(1).strip()
            break

    if not device_query:
        device_query = raw_match

    # Clean up common filler words
    device_query = re.sub(
        r"\b(the|a|an|please|for|me|on|my|open|launch|start|boot|run|ios|simulator)\b",
        "",
        device_query,
        flags=re.IGNORECASE,
    ).strip()

    devices = _list_simulators()
    if not devices:
        return "No iOS simulators found. Make sure Xcode is installed."

    if not device_query:
        # List available simulators
        names = [d["name"] for d in devices[:8]]
        return f"Which simulator? Available: {', '.join(names)}."

    match = _find_best_match(device_query, devices)
    if not match:
        names = [d["name"] for d in devices[:8]]
        return (
            f"I couldn't find a simulator matching '{device_query}'. "
            f"Available simulators: {', '.join(names)}."
        )

    # Boot the simulator if it's shut down
    if match["state"] == "Shutdown":
        try:
            subprocess.run(
                ["xcrun", "simctl", "boot", match["udid"]],
                capture_output=True,
                timeout=15,
            )
        except Exception as e:
            return f"Failed to boot {match['name']}: {e}"

    # Open the Simulator app to show it
    subprocess.run(
        ["open", "-a", "Simulator"],
        capture_output=True,
        timeout=5,
    )

    return f"Launching {match['name']} simulator. It should appear on your screen momentarily."
