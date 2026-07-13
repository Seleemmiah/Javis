"""Web search, Wikipedia, weather, YouTube, news."""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Optional

import requests

from jarvis_core.config import OPENWEATHER_API_KEY


def google_search(query: str, open_browser: bool = True, speak_results: bool = True) -> str:
    """Search Google (opens browser) and fetch DuckDuckGo snippets for speech."""
    if not query:
        return "What should I search for?"

    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    if open_browser:
        webbrowser.open(url)

    summary = _ddg_summary(query)
    if summary and speak_results:
        return f"I've opened Google for {query}. Top findings: {summary}"
    if open_browser:
        return f"I've opened Google results for {query}."
    return summary or f"No summary available for {query}."


def _ddg_summary(query: str, max_results: int = 3) -> str:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore

        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        parts = []
        for i, r in enumerate(results, 1):
            title = r.get("title") or ""
            body = r.get("body") or r.get("snippet") or ""
            parts.append(f"{i}. {title}: {body[:160]}")
        return " ".join(parts)
    except Exception:
        return ""


def open_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opening {url}."


def wikipedia_summary(topic: str, sentences: int = 2) -> str:
    try:
        import wikipedia

        return wikipedia.summary(topic, sentences=sentences, auto_suggest=True)
    except Exception as exc:
        return f"I couldn't retrieve a Wikipedia summary for {topic}. ({exc})"


def weather(city: str) -> str:
    if not city:
        return "Which city?"
    if not OPENWEATHER_API_KEY:
        # Fallback: open web weather
        webbrowser.open(
            "https://www.google.com/search?q=" + urllib.parse.quote(f"weather {city}")
        )
        return (
            f"Weather API key not set. I've opened a web forecast for {city}. "
            "Set OPENWEATHER_API_KEY for spoken telemetry."
        )
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={urllib.parse.quote(city)}&appid={OPENWEATHER_API_KEY}&units=metric"
    )
    try:
        data = requests.get(url, timeout=8).json()
        if data.get("main"):
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            return f"{city}: {desc}, {temp:.0f} degrees Celsius."
        return f"No weather data for {city}."
    except Exception as exc:
        return f"Weather service error: {exc}"


def play_youtube(query: str) -> str:
    if not query:
        return "What should I play?"
    try:
        import pywhatkit

        pywhatkit.playonyt(query)
        return f"Playing {query} on YouTube."
    except Exception:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        webbrowser.open(url)
        return f"Opened YouTube search for {query}."


def latest_news(topic: str = "world news") -> str:
    summary = _ddg_summary(topic + " news", max_results=4)
    if summary:
        return f"Headlines regarding {topic}: {summary}"
    webbrowser.open(
        "https://news.google.com/search?q=" + urllib.parse.quote(topic)
    )
    return f"I've opened Google News for {topic}."
