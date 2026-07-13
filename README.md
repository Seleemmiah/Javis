# J.A.R.V.I.S. (Just A Rather Very Intelligent System)

J.A.R.V.I.S. is a hyper-intelligent, fully autonomous AI assistant designed for macOS. It acts as an always-on desktop companion that can hear, see, speak, and physically control your computer to automate your daily tasks.

## 🚀 Key Features

*   **🗣️ Always-On Voice Commands:** Double-clap or say "Jarvis" to wake him up. Uses local, zero-latency **MLX Whisper** for near-instant transcription, with intelligent **noise reduction** so he can hear you in a crowded room.
*   **🌍 Multilingual Support:** JARVIS understands and transcribes 99 different languages automatically.
*   **👁️ Computer Vision:** JARVIS can "see" your screen using Gemini 2.0 Flash Vision. Ask him to review your code, explain a graph, or read a document open on your desktop.
*   **🤖 Autonomous Computer Control:** JARVIS can physically move your mouse, click on UI elements, scroll, and type on your keyboard. Just ask him to click something or type a message.
*   **🧠 Long-Term Semantic Memory:** JARVIS remembers facts, preferences, and events. He stores them locally using `sentence-transformers` and recalls them dynamically, so he gets smarter and more personalized the more you use him.
*   **⚡ Streaming Speech:** Responses feel instantaneous. JARVIS starts speaking the first sentence of his answer while his AI brain is still generating the rest of it.
*   **📱 Apple Ecosystem Integration:**
    *   **Reminders:** Syncs directly to your iPhone via iCloud.
    *   **iMessage:** Send messages to contacts without touching your phone.
    *   **Spotlight:** Deep search your entire Mac file system.
*   **🧩 Plugin Architecture:** Easily extensible. Includes plugins for Spotify, iOS Simulators, unit conversion, morning briefings, and more.
*   **🎩 Persona Switcher:** Change how JARVIS acts. Switch between Default, Lab, Code, Focus, or Chill mode depending on your workflow.
*   **🖥️ Mac Menu Bar App:** JARVIS lives quietly in your macOS menu bar with a dynamic status icon.

## 🛠️ Tech Stack

*   **Brain:** Gemini 2.0 Flash (Primary) / OpenAI / Ollama (Local fallback)
*   **Voice (STT):** Apple MLX Whisper (local, Apple Silicon optimized)
*   **Voice (TTS):** Edge TTS (Neural text-to-speech)
*   **Memory:** Sentence-Transformers (Semantic Vector Search) + local JSON
*   **Vision:** Gemini Vision API
*   **UI:** `pystray` (Native macOS Menu Bar)
*   **Control:** `pyautogui`, `osascript`, `AppKit`

## ⚙️ Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Seleemmiah/Javis.git
    cd Javis
    ```

2.  **Install dependencies:**
    *(Recommended to use a virtual environment like conda or venv)*
    ```bash
    pip install -r requirements.txt
    ```
    *Required external tools (install via Homebrew):*
    ```bash
    brew install portaudio ffmpeg
    ```

3.  **Configure API Keys:**
    Create a `.env` file in the root directory (or let JARVIS prompt you on first boot) and add your keys:
    ```env
    GEMINI_API_KEY="your_gemini_key"
    OPENAI_API_KEY="your_openai_key"
    ```

## 🏃‍♂️ Running J.A.R.V.I.S.

You can run JARVIS directly or use the provided control script to run him as a background daemon.

**Using the Control Script (Recommended):**
```bash
./jarvis_control.sh start   # Starts JARVIS in the background
./jarvis_control.sh stop    # Stops JARVIS
./jarvis_control.sh restart # Restarts JARVIS
./jarvis_control.sh logs    # Follow the logs
```

**Running directly (for debugging):**
```bash
python jarvis.py
```

## 🔌 Writing Plugins

JARVIS uses a drop-in plugin system. To add a new skill, just create a `.py` file in `skills/plugins/`. 
The loader automatically parses regex `PLUGIN_TRIGGERS` and routes commands to your `plugin_execute()` function for zero-latency execution!
