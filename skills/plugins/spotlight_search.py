"""macOS Spotlight deep search plugin for J.A.R.V.I.S."""

from __future__ import annotations

import re
import subprocess

PLUGIN_NAME = "spotlight_search"
PLUGIN_DESCRIPTION = "Search your entire Mac for files, documents, PDFs, etc. using macOS Spotlight"
PLUGIN_TRIGGERS = [
    r"(?:find|search|locate|look\s+for|where\s+is)\s+(?:the\s+)?(?:file|document|pdf|folder|image|photo|video)?\s*(?:called|named)?\s*(.+)",
]


def plugin_execute(raw_match: str = "", **kwargs) -> str:
    # Extract query
    query = ""
    for pattern in PLUGIN_TRIGGERS:
        m = re.search(pattern, raw_match, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            break

    if not query:
        query = raw_match.strip()

    # Clean up common filler
    query = re.sub(
        r"\b(please|for\s+me|on\s+my\s+(?:mac|computer|laptop))\b",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip()

    if not query:
        return "What file should I search for?"

    try:
        r = subprocess.run(
            ["mdfind", "-name", query],
            capture_output=True,
            text=True,
            timeout=10,
        )
        results = [line.strip() for line in r.stdout.strip().splitlines() if line.strip()]

        if not results:
            # Try a broader content search
            r2 = subprocess.run(
                ["mdfind", query],
                capture_output=True,
                text=True,
                timeout=10,
            )
            results = [line.strip() for line in r2.stdout.strip().splitlines() if line.strip()]

        if not results:
            return f"I couldn't find any files matching '{query}' on your Mac."

        # Show top results
        top = results[:5]
        summary = "\n".join(f"  • {path}" for path in top)
        extra = f" ({len(results) - 5} more results)" if len(results) > 5 else ""

        return f"I found {len(results)} file{'s' if len(results) != 1 else ''} matching '{query}':{extra}\n{summary}"

    except Exception as e:
        return f"Spotlight search failed: {e}"
