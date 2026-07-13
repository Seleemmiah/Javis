"""Configuration and environment for J.A.R.V.I.S."""

from __future__ import annotations

import os
import platform
from pathlib import Path

# Project root (parent of jarvis_core/)
ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

MEMORY_FILE = ROOT / "memory.json"
LONG_TERM_MEMORY_FILE = ROOT / "long_term_memory.json"
LOG_FILE = ROOT / "jarvis.log"
CACHE_DIR = ROOT / ".jarvis_cache"
CACHE_DIR.mkdir(exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
JARVIS_MODEL = os.getenv("JARVIS_MODEL", "gpt-4o-mini")

# Google Gemini (FREE tier — 15 RPM, no credit card needed)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Local LLM (Ollama) — free offline brain
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:12b")
USE_OLLAMA = os.getenv("JARVIS_USE_OLLAMA", "auto")  # auto | always | never

# Brain priority: gemini → openai → ollama
BRAIN_PRIORITY = os.getenv("JARVIS_BRAIN", "gemini")  # gemini | openai | ollama

IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Wake / conversation
WAKE_WORD = "jarvis"
REQUIRE_WAKE_WORD = False
CONVERSATION_TIMEOUT_SEC = 90
CLAP_ENABLED = True

# Clap detection
CLAP_THRESHOLD = 0.45
CLAP_MIN_GAP = 0.12
CLAP_MAX_GAP = 0.85
CLAP_COOLDOWN = 2.0
CLAP_SAMPLE_RATE = 16000
CLAP_CHUNK = 1024

DESTRUCTIVE_PATTERNS = (
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "diskutil erase",
    ":(){",
    "dd if=",
    "format c:",
)

# Proactive alerts
ALERT_INTERVAL = 90
BATTERY_WARN_PERCENT = 15
DISK_WARN_PERCENT = 90
PROACTIVE_NEWS = os.getenv("JARVIS_PROACTIVE_NEWS", "0") == "1"

# --- Voice / TTS ---
# engine: edge (natural neural, free) | system (pyttsx3 offline)
TTS_ENGINE = os.getenv("JARVIS_TTS", "edge")
# Best free female British neural voices (edge-tts):
#   en-GB-SoniaNeural  en-GB-LibbyNeural  en-GB-MaisieNeural
EDGE_TTS_VOICE = os.getenv("JARVIS_EDGE_VOICE", "en-GB-SoniaNeural")
EDGE_TTS_RATE = os.getenv("JARVIS_EDGE_RATE", "+0%")
EDGE_TTS_PITCH = os.getenv("JARVIS_EDGE_PITCH", "+0Hz")

# System voice fallback (pyttsx3)
VOICE_NAME = os.getenv("JARVIS_VOICE", "Shelley")
SPEECH_RATE = int(os.getenv("JARVIS_SPEECH_RATE", "165"))
VOLUME = float(os.getenv("JARVIS_VOLUME", "1.0"))
VOICE_PRESET = os.getenv("JARVIS_VOICE_PRESET", "female_british")
VOICE_PRESETS = {
    "female_british": [
        "com.apple.eloquence.en-GB.Shelley",
        "com.apple.eloquence.en-GB.Flo",
        "com.apple.eloquence.en-GB.Sandy",
        "shelley",
        "flo",
        "sandy",
    ],
    "male_british": [
        "com.apple.voice.compact.en-GB.Daniel",
        "com.apple.eloquence.en-GB.Reed",
        "daniel",
        "reed",
    ],
}

# Agent / Personas / Plugins
AGENT_MAX_STEPS = int(os.getenv("JARVIS_AGENT_MAX_STEPS", "6"))
PROJECT_ROOT_OVERRIDE = os.getenv("JARVIS_PROJECT_ROOT", "")
PERSONA_MODE = os.getenv("JARVIS_PERSONA", "default")
PLUGINS_ENABLED = os.getenv("JARVIS_PLUGINS", "1") == "1"
