#!/usr/bin/env python3
# ===============================
# J.A.R.V.I.S. v2 — Iron Man edition
# Double-clap wake · HUD · full system access · Google · proactive alerts
# ===============================

from __future__ import annotations

import re
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_core.agent import Agent
from jarvis_core.alerts import AlertMonitor
from jarvis_core.brain import Brain
from jarvis_core.clap import ClapDetector
from jarvis_core import config as jarvis_config
from jarvis_core.config import (
    CONVERSATION_TIMEOUT_SEC,
    OPENAI_API_KEY,
    WAKE_WORD,
)
from jarvis_core.hud_desktop import DesktopHUD
from jarvis_core.long_memory import LongTermMemory
from jarvis_core.memory import Memory
from jarvis_core.voice import Voice
from jarvis_core import calendar_mac
from jarvis_core import screen as screen_mod
from skills.executor import ActionExecutor
from skills import shell as shell_mod
from skills import system_info
from skills import web


class Jarvis:
    def __init__(self, use_hud: bool = True) -> None:
        self.memory = Memory()
        self.long_memory = LongTermMemory()
        self.hud = DesktopHUD() if use_hud else None
        self.voice = Voice(on_speak=self._on_speak)
        self.brain = Brain(title=self.memory.title())
        self.executor = ActionExecutor(
            speak=self.voice.speak,
            on_log=self._log,
            long_memory=self.long_memory,
        )
        self.agent = Agent(
            brain=self.brain,
            executor=self.executor,
            memory=self.memory,
            long_memory=self.long_memory,
            speak=self.voice.speak,
            on_log=self._log,
        )
        self.awake = False
        self._awake_until = 0.0
        self._wake_event = threading.Event()
        self._lock = threading.Lock()
        self._running = True
        self.clap: ClapDetector | None = None
        self.alerts: AlertMonitor | None = None

    # ---------- HUD helpers ----------
    def _log(self, msg: str) -> None:
        if self.hud:
            self.hud.log_event(msg)
        else:
            print(f"[log] {msg}")

    def _on_alert(self, text: str) -> None:
        self._log(f"[ALERT] {text}")
        try:
            import subprocess
            safe_text = text.replace('"', '\\"')
            subprocess.run(["osascript", "-e", f'display notification "{safe_text}" with title "J.A.R.V.I.S."'], check=False)
        except Exception:
            pass
        self.voice.speak(text)

    def _on_speak(self, text: str) -> None:
        if self.hud:
            self.hud.set_exchange(jarvis=text)
            self.hud.log_event(f"Said: {text[:80]}")

    def _set_mode(self, mode: str) -> None:
        if self.hud:
            self.hud.set_mode(mode)

    def _status(self, text: str) -> None:
        if self.hud:
            self.hud.set_status(text)

    # ---------- Wake ----------
    def wake(self, reason: str = "command") -> None:
        with self._lock:
            self.awake = True
            self._awake_until = time.time() + CONVERSATION_TIMEOUT_SEC
        self._wake_event.set()
        self._set_mode("AWAKE")
        self._status(f"Online — {reason}")
        self._log(f"Woke via {reason}")

    def standby(self, say: bool = True) -> None:
        with self._lock:
            self.awake = False
            self._awake_until = 0.0
        self._set_mode("STANDBY")
        self._status("Standing by. Clap twice or say Jarvis.")
        if say:
            self.voice.speak(f"Standing by, {self.memory.title()}.")
        if self.clap:
            self.clap.resume()

    def _extend_awake(self) -> None:
        with self._lock:
            if self.awake:
                self._awake_until = time.time() + CONVERSATION_TIMEOUT_SEC

    def _is_awake(self) -> bool:
        with self._lock:
            if not self.awake:
                return False
            if time.time() > self._awake_until:
                self.awake = False
                return False
            return True

    # ---------- Boot ----------
    def boot(self) -> None:
        if self.hud:
            self.hud.start()
            self._status("Running systems diagnostic...")
            self._log("Boot sequence initiated")

        title = self.memory.title()
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greet = "Good morning"
        elif 12 <= hour < 17:
            greet = "Good afternoon"
        elif 17 <= hour < 22:
            greet = "Good evening"
        else:
            greet = "Working late"

        backend = self.brain.backend_name()
        mem_stats = self.long_memory.summary_stats()
        self.voice.speak(
            f"{greet}, {title}. All systems are operational. "
            f"Neural voice online. Cognition backend: {backend}. "
            f"Long-term memory holds {mem_stats}. "
            f"Clap twice to wake me, or speak a command. I am at your service."
        )
        self._status("Systems nominal. Double-clap or speak to engage.")
        self._set_mode("STANDBY")
        self._log(f"Brain backend: {backend}")
        self._log(f"Memory: {mem_stats}")
        if not OPENAI_API_KEY and not self.brain._ollama_available():
            self._log(
                "No OpenAI key and no Ollama — install Ollama free for smart agent mode"
            )

        # Proactive alerts
        def on_alert(msg: str) -> None:
            self._set_mode("ALERT")
            self._log(f"ALERT: {msg}")
            # Don't steal mic mid-conversation harshly; still announce
            if self.clap:
                self.clap.pause()
            try:
                self.voice.speak(msg)
            finally:
                if self.clap and not self._is_awake():
                    self.clap.resume()
                self._set_mode("AWAKE" if self._is_awake() else "STANDBY")

        def on_vitals(bat: str, cpu: str) -> None:
            if self.hud:
                self.hud.set_levels(battery=bat, cpu=cpu)

        from jarvis_core.audio_buffer import get_audio_buffer
        get_audio_buffer().start()

        self.alerts = AlertMonitor(on_alert=on_alert, on_vitals=on_vitals)
        self.alerts.start()

        from jarvis_core.config import PLUGINS_ENABLED
        if PLUGINS_ENABLED:
            try:
                from jarvis_core.skill_loader import discover_plugins
                discover_plugins()
                self._log("Plugins discovered")
            except Exception as e:
                self._log(f"Failed to load plugins: {e}")

        # Double-clap
        if jarvis_config.CLAP_ENABLED:
            self.clap = ClapDetector(
                on_double_clap=self._on_double_clap,
                on_level=lambda lv: self.hud.set_levels(mic=lv) if self.hud else None,
            )
            t = threading.Thread(
                target=self.clap.listen_forever, daemon=True, name="jarvis-clap"
            )
            t.start()
        else:
            self._log("Double-clap wake disabled")

    def _on_double_clap(self) -> None:
        """Called from clap thread — only signal wake; main loop speaks."""
        if self._is_awake():
            self._extend_awake()
            return
        if self.clap:
            self.clap.pause()
        self.wake(reason="double clap")
        # Speech happens on main thread after standby wait returns

    # ---------- Command pipeline ----------
    def strip_wake(self, command: str) -> str:
        for prefix in ("hey jarvis", "ok jarvis", "okay jarvis", "jarvis"):
            if command.startswith(prefix):
                return command[len(prefix) :].strip(" ,.")
        return command

    def handle(self, command: str) -> bool:
        """
        Process one command.
        Returns False if JARVIS should exit entirely.
        """
        if not command:
            return True

        if self.hud:
            self.hud.set_exchange(user=command)

        raw = command
        command = self.strip_wake(command)

        # Wake phrases
        if raw.strip() in (WAKE_WORD, "hey jarvis", "ok jarvis", "okay jarvis") or (
            not command and WAKE_WORD in raw
        ):
            self.wake(reason="voice")
            self.voice.speak(f"Yes, {self.memory.title()}?")
            return True

        # If not awake and no wake word used, ignore soft utterances
        has_wake = WAKE_WORD in raw
        if not self._is_awake() and not has_wake:
            # Still allow explicit full commands without wake for usability
            # when they clearly address a skill — keep open: always process
            pass

        if not command:
            if has_wake or self._is_awake():
                self.wake(reason="voice")
                self.voice.speak(f"Yes, {self.memory.title()}?")
            return True

        self.wake(reason="command")
        self._extend_awake()
        self._set_mode("EXECUTING")
        self.brain.set_title(self.memory.title())

        # Hardcoded high-priority local skills (fast path)
        if self._fast_path(command):
            self._set_mode("AWAKE")
            return True

        # Multi-step agent (smart path)
        self._log(f"Agent engaged ({self.brain.backend_name()})")
        outcome = self.agent.run(command)
        if outcome.get("standby") or any(
            x in command for x in ("standby", "go to sleep", "that's all", "that is all")
        ):
            self.standby(say=True)
        else:
            self._set_mode("AWAKE")
            self._status("Listening for next instruction…")

        if any(
            command == x or command.startswith(x + " ")
            for x in ("go offline", "power down jarvis", "goodbye forever")
        ):
            self.voice.speak(f"Powering down. Goodbye, {self.memory.title()}.")
            return False

        return True

    def _fast_path(self, command: str) -> bool:
        """Handle common commands without the model. Returns True if handled."""
        title = self.memory.title()

        # Standby / offline
        if command in (
            "standby",
            "sleep",
            "go to sleep",
            "that's all",
            "that is all",
            "dismiss",
        ):
            self.standby(say=True)
            return True

        if command in ("goodbye", "good night", "go offline", "power down"):
            self.voice.speak(f"Going offline. Call if you need me, {title}.")
            # Soft offline -> standby; hard quit via "exit program"
            self.standby(say=False)
            return True

        if command in ("exit program", "quit program", "shutdown jarvis"):
            self.voice.speak(f"Shutting down J.A.R.V.I.S. Goodbye, {title}.")
            self._running = False
            return True

        if command.startswith("stop") or command.startswith("shut up") or command.startswith("enough"):
            self.voice.stop()
            self._log("Interrupted speech")
            return True

        # Identity / status
        if any(
            p in command
            for p in ("who are you", "what are you", "introduce yourself")
        ):
            self.voice.speak(
                f"I am J.A.R.V.I.S. — Just A Rather Very Intelligent System. "
                f"I have access to this machine, the web, and whatever you need, {title}."
            )
            return True

        if "status report" in command or "system status" in command or command == "status":
            self.voice.speak(system_info.system_report())
            return True

        # Memory
        if "remember my name is" in command or (
            "remember" in command and "name is" in command
        ):
            name = command.split("name is", 1)[-1].strip()
            if name:
                self.memory.set("name", name)
                self.brain.set_title(name)
                self.voice.speak(f"Logged. I'll call you {name}.")
                return True

        if command.startswith("remember "):
            note = command.replace("remember ", "", 1).strip()
            if note:
                self.memory.note(note)
                self.long_memory.remember_fact(note)
                self.voice.speak(f"I've filed that away in long-term memory, {title}.")
                return True

        if command.startswith("recall ") or "what do you remember" in command:
            q = command.replace("recall ", "", 1).replace("what do you remember about", "").replace("what do you remember", "").strip()
            block = self.long_memory.context_block(q or "facts preferences", k=6)
            self.voice.speak(block or f"I have nothing matching that yet, {title}.")
            return True

        if "what is my name" in command or "what's my name" in command:
            name = self.memory.get("name")
            self.voice.speak(f"You are {name}." if name else "I don't have your name yet.")
            return True

        # Time / date
        if "what time" in command or command in ("time", "the time"):
            self.voice.speak(
                f"The time is {datetime.now().strftime('%I:%M %p')}, {title}."
            )
            return True

        if "what day" in command or "what date" in command or "today's date" in command:
            self.voice.speak(f"Today is {datetime.now().strftime('%A, %d %B %Y')}.")
            return True

        # Open sites
        if "open youtube" in command:
            webbrowser.open("https://youtube.com")
            self.voice.speak("YouTube is ready.")
            return True
        if "open google" in command:
            webbrowser.open("https://google.com")
            self.voice.speak("Google is open.")
            return True

        # Google search
        m = re.search(
            r"(?:google|search(?:\s+google)?(?:\s+for)?|look up)\s+(.+)", command
        )
        if m:
            q = m.group(1).strip()
            self.voice.speak(web.google_search(q))
            return True

        # Run shell: "run command …" / "execute …" / "in terminal …"
        m = re.search(
            r"(?:run command|run shell|execute command|execute|in terminal|shell)\s+(.+)",
            command,
        )
        if m:
            cmd = m.group(1).strip()
            self._log(f"$ {cmd}")
            out = shell_mod.run_shell(cmd)
            summary = out if len(out) < 400 else out[:380] + "…"
            self.voice.speak(summary or f"Done, {title}.")
            return True

        # Open app
        m = re.search(r"open (?:app |application |the app )?(.+)", command)
        if m and "youtube" not in command and "google" not in command:
            name = m.group(1).strip()
            # avoid "open folder" style
            if not name.startswith("folder") and not name.startswith("http"):
                self.voice.speak(system_info.open_app(name))
                return True

        # Weather
        if "weather" in command:
            city = command
            for token in (
                "what's the weather in",
                "what is the weather in",
                "weather in",
                "weather for",
                "weather",
                "the",
            ):
                city = city.replace(token, " ")
            city = " ".join(city.split())
            self.voice.speak(web.weather(city))
            return True

        # Wikipedia
        if command.startswith("who is") or command.startswith("what is"):
            if "weather" not in command:
                topic = (
                    command.replace("who is", "", 1)
                    if command.startswith("who is")
                    else command.replace("what is", "", 1)
                ).strip()
                if topic:
                    self.voice.speak(web.wikipedia_summary(topic))
                    return True

        # Play youtube
        if command.startswith("play "):
            self.voice.speak(web.play_youtube(command[5:].strip()))
            return True

        # Screenshot / see screen
        if any(
            p in command
            for p in (
                "what's on my screen",
                "whats on my screen",
                "what is on my screen",
                "what do you see",
                "analyze screen",
                "see the screen",
                "look at my screen",
            )
        ):
            self.voice.speak(screen_mod.describe_screen("What is on the user's screen?"))
            return True

        if "screenshot" in command or "capture screen" in command:
            self.voice.speak(system_info.take_screenshot())
            return True

        # Calendar
        if any(
            p in command
            for p in (
                "calendar",
                "what's on today",
                "whats on today",
                "my schedule",
                "today's events",
                "todays events",
            )
        ):
            self.voice.speak(calendar_mac.todays_events())
            return True

        # Volume
        m = re.search(r"(?:set )?volume (?:to )?(\d+)", command)
        if m:
            self.voice.speak(system_info.set_volume(int(m.group(1))))
            return True

        # File search
        m = re.search(r"(?:find file|search files?|locate file)\s+(.+)", command)
        if m:
            out = shell_mod.file_search(m.group(1).strip())
            summary = out if len(out) < 400 else out[:380] + "…"
            self.voice.speak(summary)
            return True

        # News
        if "news" in command:
            topic = command.replace("news", "").replace("about", "").strip() or "world"
            self.voice.speak(web.latest_news(topic))
            return True

        # Change voice: neural (sonia/libby) or system (shelley/daniel)
        m = re.search(r"(?:use|change|set) voice(?: to)? (.+)", command)
        if m:
            name = m.group(1).strip()
            if self.voice.set_voice(name):
                self.voice.speak(
                    f"Voice updated to {self.voice.active_voice_name}, {title}."
                )
            else:
                self.voice.speak(
                    f"I couldn't find that voice. Try sonia, libby, maisie, "
                    f"shelley, flo, or daniel. {self.voice.list_edge_voices_hint()}"
                )
            return True

        # Shutdown / restart machine
        if "shutdown computer" in command or "shut down the computer" in command:
            self.voice.speak(system_info.shutdown_pc())
            return True
        if "restart computer" in command or "restart the computer" in command:
            self.voice.speak(system_info.restart_pc())
            return True

        return False

    # ---------- Main loops ----------
    def run(self) -> None:
        """
        STANDBY: mic owned by double-clap detector (and optional short wake-word polls).
        AWAKE: clap paused; continuous conversation via speech recognition.
        """
        self.boot()
        try:
            while self._running:
                if not self._is_awake():
                    self._standby_wait()
                    if not self._running:
                        break
                    if not self._is_awake():
                        continue

                # Conversation mode
                if self.clap:
                    self.clap.pause()
                self._set_mode("AWAKE")
                self._status("Conversation active — speak naturally")

                try:
                    command = self.voice.listen(
                        timeout=7,
                        phrase_time_limit=16,
                        ambient=0.35,
                    )
                except Exception as exc:
                    self._log(f"Listen error: {exc}")
                    command = ""

                if command:
                    if not self.handle(command):
                        break
                    if not self._running:
                        break
                else:
                    # Silence while awake — expire conversation window
                    if time.time() > self._awake_until:
                        self.standby(say=True)

        except KeyboardInterrupt:
            self.voice.speak(f"Interrupted. Standing down, {self.memory.title()}.")
        finally:
            self.shutdown()

    def _standby_wait(self) -> None:
        """Wait for double-clap; periodically allow a short 'Jarvis' wake-word listen."""
        self._set_mode("STANDBY")
        self._status("Standby — clap twice, or say 'Jarvis'")

        # Prefer clap ownership of the mic
        if self.clap and jarvis_config.CLAP_ENABLED:
            self.clap.resume()
            # Wait for clap wake (event set in _on_double_clap)
            # Also wake-word poll every ~12s by briefly taking the mic
            for _ in range(12):
                if not self._running or self._is_awake():
                    break
                if self._wake_event.wait(timeout=1.0):
                    self._wake_event.clear()
                    break
            if not self._running:
                if self.clap:
                    self.clap.pause()
                return
            if self._is_awake():
                if self.clap:
                    self.clap.pause()
                # Greet once when woken by clap
                self.voice.speak(f"Yes, {self.memory.title()}?")
                return

            # Brief wake-word window
            if self.clap:
                self.clap.pause()
            try:
                heard = self.voice.listen(timeout=3, phrase_time_limit=4, ambient=0.3)
            except Exception:
                heard = ""
            if heard and (
                WAKE_WORD in heard
                or heard.strip() in ("hey jarvis", "ok jarvis", "okay jarvis")
            ):
                self.wake(reason="voice")
                self.voice.speak(f"Yes, {self.memory.title()}?")
            elif heard:
                # Full command without wake while in standby — still accept it
                self.handle(heard)
            return

        # No clap: listen for wake word / any command
        try:
            heard = self.voice.listen(timeout=8, phrase_time_limit=12, ambient=0.4)
        except Exception:
            heard = ""
        if heard:
            self.handle(heard)

    def shutdown(self) -> None:
        self._running = False
        if self.clap:
            self.clap.stop()
        if self.alerts:
            self.alerts.stop()
        if self.hud:
            self.hud.stop()
        self._log("J.A.R.V.I.S. offline")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. — Iron Man style AI")
    parser.add_argument("--no-hud", action="store_true", help="Disable live HUD")
    parser.add_argument("--no-clap", action="store_true", help="Disable double-clap wake")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Text input mode (no microphone listening loop)",
    )
    parser.add_argument("--run", type=str, help="Run a Python script with JARVIS self-healing overwatch")
    args = parser.parse_args()

    if args.no_clap:
        jarvis_config.CLAP_ENABLED = False

    jarvis = Jarvis(use_hud=not args.no_hud)

    if args.text:
        jarvis.boot()
        print("Text mode. Type commands (or 'exit program').")
        while True:
            try:
                line = input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if not jarvis.handle(line.lower()):
                break
            if not jarvis._running:
                break
        jarvis.shutdown()
        return

    import threading
    t = threading.Thread(target=jarvis.run, daemon=True, name="jarvis-main-loop")
    t.start()

    if jarvis.hud and hasattr(jarvis.hud, 'run_main_loop'):
        jarvis.hud.run_main_loop()
    else:
        try:
            while t.is_alive():
                t.join(timeout=1.0)
        except KeyboardInterrupt:
            jarvis.shutdown()

    if args.run:
        script_file = args.run
        import subprocess
        print(f"JARVIS is running {script_file} with self-healing overwatch...")
        try:
            res = subprocess.run([sys.executable, script_file], capture_output=True, text=True)
            if res.returncode != 0:
                print("Execution failed. Analyzing traceback...")
                error_msg = res.stderr.strip()
                prompt = f"The script '{script_file}' crashed with this error:\n\n{error_msg}\n\nAnalyze the error, rewrite the code to fix the issue, and return only the fixed python code without markdown formatting."
                
                response = jarvis.agent.run(prompt)
                
                fixed_code = response.get("speech", "")
                if "```python" in fixed_code:
                    fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
                    
                with open(script_file, "w") as f:
                    f.write(fixed_code)
                print(f"JARVIS applied a fix to {script_file}. Please re-run to test.")
                jarvis.voice.speak(f"Sir, I detected an error and have automatically patched {script_file}.")
            else:
                print(res.stdout)
        except Exception as e:
            print(f"JARVIS runner error: {e}")
        jarvis.shutdown()
        return

    jarvis.run()


if __name__ == "__main__":
    main()
