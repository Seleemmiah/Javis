"""Spotify search and playlist plugin for J.A.R.V.I.S."""

from __future__ import annotations

import platform
import re
import subprocess
import urllib.parse

PLUGIN_NAME = "spotify_playlist"
PLUGIN_DESCRIPTION = "Search Spotify for songs, genres, or playlists and play them"
PLUGIN_TRIGGERS = [
    r"(?:play|find|search|create|make)\s+(?:a\s+)?(?:spotify\s+)?(?:playlist|songs?|music)\s+(?:of|for|about|with|called)?\s*(.+)",
    r"play\s+(.+)\s+on\s+spotify",
    r"spotify\s+(?:play|search|find)\s+(.+)",
]


def plugin_execute(raw_match: str = "", **kwargs) -> str:
    if platform.system() != "Darwin":
        return "Spotify automation is only supported on macOS."

    # Extract the query from the trigger match
    query = ""
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            break

    if not query:
        # Try to use the whole raw_match minus common words
        query = re.sub(
            r"\b(play|find|search|create|make|spotify|playlist|songs?|music|for|me|a|on|of|with|please)\b",
            "",
            raw_match,
            flags=re.IGNORECASE,
        ).strip()

    if not query:
        return "What would you like me to search for on Spotify?"

    # First, make sure Spotify is open
    subprocess.run(
        ["osascript", "-e", 'tell application "Spotify" to activate'],
        capture_output=True,
        timeout=5,
    )

    # Open Spotify with a search query using the Spotify URI scheme
    encoded_query = urllib.parse.quote(query)
    spotify_uri = f"spotify:search:{encoded_query}"

    try:
        subprocess.run(["open", spotify_uri], check=True, capture_output=True, timeout=5)
        return (
            f"I've opened Spotify and searched for '{query}'. "
            f"You should see the results now — just hit play on the one you like!"
        )
    except Exception:
        # Fallback: open Spotify web search
        web_url = f"https://open.spotify.com/search/{encoded_query}"
        subprocess.run(["open", web_url], capture_output=True)
        return f"I've opened Spotify search for '{query}' in your browser."
