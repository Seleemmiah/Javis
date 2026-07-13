"""Browser helpers — open, search, basic page fetch (free)."""

from __future__ import annotations

import re
import urllib.parse
import webbrowser

import requests


def open_url(url: str) -> str:
    if not url:
        return "No URL provided."
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}."


def open_and_search(query: str) -> str:
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url)
    return f"Browser search opened for {query}."


def fetch_page_text(url: str, max_chars: int = 2500) -> str:
    """Lightweight page text fetch for the agent to read results."""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "JARVIS/2.0 (personal assistant)"},
        )
        r.raise_for_status()
        html = r.text
        # crude strip tags
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars] if text else "Page had no extractable text."
    except Exception as exc:
        return f"Fetch failed: {exc}"
