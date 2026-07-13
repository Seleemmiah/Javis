"""Speech synthesis (edge-tts neural + system fallback) and recognition."""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import signal
import tempfile
import threading
from pathlib import Path

import speech_recognition as sr
import pyttsx3

from jarvis_core.config import (
    CACHE_DIR,
    EDGE_TTS_PITCH,
    EDGE_TTS_RATE,
    EDGE_TTS_VOICE,
    IS_MAC,
    IS_WINDOWS,
    SPEECH_RATE,
    TTS_ENGINE,
    VOICE_NAME,
    VOICE_PRESET,
    VOICE_PRESETS,
    VOLUME,
)


def _voice_rank(voice, want: str) -> int:
    vid = (voice.id or "").lower()
    name = (getattr(voice, "name", "") or "").lower()
    want = want.lower().strip()
    if want == vid:
        return 0
    if want in vid and "en-gb" in vid:
        return 1
    if want == name or want == name.split("(")[0].strip():
        return 2 if ("en-gb" in vid or "en_gb" in vid) else 20
    if want in name and "en-gb" in vid:
        return 3
    if want in vid:
        return 10
    if want in name:
        return 30
    return 999


class Voice:
    """
    Primary: edge-tts (natural Microsoft neural voices — free, needs network).
    Fallback: macOS/Windows system voices via pyttsx3 (offline).
    """

    def __init__(self, on_speak=None) -> None:
        self.on_speak = on_speak
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self.recognizer.dynamic_energy_threshold = True
        self.tts_engine = TTS_ENGINE  # edge | system
        self.edge_voice = EDGE_TTS_VOICE
        self.active_voice_id = self.edge_voice
        self.active_voice_name = self.edge_voice
        self._play_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._current_proc: subprocess.Popen | None = None
        self._speaking = False
        self._configure_system_voice()
        if self.tts_engine == "edge":
            print(f"[voice] Neural TTS: edge-tts → {self.edge_voice}")
        else:
            print(f"[voice] System TTS: {self.active_voice_name}")

    # ----- system voice (fallback) -----
    def _configure_system_voice(self) -> None:
        preferred = [VOICE_NAME, *VOICE_PRESETS.get(VOICE_PRESET, [])]
        voices = self.engine.getProperty("voices") or []
        for want in preferred:
            best, best_score = None, 999
            for v in voices:
                score = _voice_rank(v, want)
                if score < best_score:
                    best_score, best = score, v
            if best is not None and best_score < 999:
                self.engine.setProperty("voice", best.id)
                if self.tts_engine != "edge":
                    self.active_voice_id = best.id
                    self.active_voice_name = getattr(best, "name", best.id)
                break
        self.engine.setProperty("rate", SPEECH_RATE)
        self.engine.setProperty("volume", VOLUME)

    def set_voice(self, name_or_id: str) -> bool:
        """
        Switch voice.
        edge-tts ids look like en-GB-SoniaNeural.
        Otherwise treats as system voice name.
        """
        name = name_or_id.strip()
        # edge neural voices
        if "Neural" in name or name.startswith("en-") or name.startswith("en_"):
            self.tts_engine = "edge"
            self.edge_voice = name.replace("_", "-")
            self.active_voice_id = self.edge_voice
            self.active_voice_name = self.edge_voice
            return True
        # aliases
        aliases = {
            "sonia": "en-GB-SoniaNeural",
            "libby": "en-GB-LibbyNeural",
            "maisie": "en-GB-MaisieNeural",
            "ryan": "en-GB-RyanNeural",
            "thomas": "en-GB-ThomasNeural",
        }
        key = name.lower()
        if key in aliases:
            return self.set_voice(aliases[key])
        if key in ("edge", "neural"):
            self.tts_engine = "edge"
            self.active_voice_name = self.edge_voice
            self.active_voice_id = self.edge_voice
            return True
        if key in ("system", "local", "offline"):
            self.tts_engine = "system"
            self._configure_system_voice()
            return True

        voices = self.engine.getProperty("voices") or []
        best, best_score = None, 999
        for v in voices:
            score = _voice_rank(v, name)
            if score < best_score:
                best_score, best = score, v
        if best is not None and best_score < 999:
            self.tts_engine = "system"
            self.engine.setProperty("voice", best.id)
            self.active_voice_id = best.id
            self.active_voice_name = getattr(best, "name", best.id)
            return True
        return False

    def list_edge_voices_hint(self) -> str:
        return (
            "Female British neural: en-GB-SoniaNeural, en-GB-LibbyNeural, "
            "en-GB-MaisieNeural. Say 'use voice sonia' or 'use voice libby'."
        )

    def stop(self) -> None:
        """Interrupt current speech."""
        self._stop_event.set()
        proc = self._current_proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    # ----- speak -----
    def speak(self, text: str) -> None:
        if not text:
            return
        self._stop_event.clear()
        self._speaking = True
        try:
            if self.on_speak:
                self.on_speak(text)
            print(f"J.A.R.V.I.S.: {text}")
            if self._stop_event.is_set():
                return
            if self.tts_engine == "edge":
                try:
                    self._speak_edge(text)
                    return
                except Exception as exc:
                    print(f"[voice] edge-tts failed ({exc}); falling back to system voice")
            self._speak_system(text)
        finally:
            self._speaking = False

    def _speak_system(self, text: str) -> None:
        with self._play_lock:
            self.engine.say(text)
            self.engine.runAndWait()

    def _speak_edge(self, text: str) -> None:
        """Synthesize with edge-tts and play via afplay/ffplay."""
        rate = EDGE_TTS_RATE
        pitch = EDGE_TTS_PITCH
        
        # Emotion tags
        if "[fast]" in text:
            rate = "+20%"
            text = text.replace("[fast]", "").strip()
        if "[urgent]" in text:
            rate = "+30%"
            pitch = "+10Hz"
            text = text.replace("[urgent]", "").strip()
        if "[sad]" in text:
            rate = "-15%"
            pitch = "-10Hz"
            text = text.replace("[sad]", "").strip()
        if "[happy]" in text:
            pitch = "+15Hz"
            text = text.replace("[happy]", "").strip()
            
        cache_key = hashlib.sha1(
            f"{self.edge_voice}|{rate}|{pitch}|{text}".encode()
        ).hexdigest()[:24]
        out = CACHE_DIR / f"tts_{cache_key}.mp3"
        if not out.exists():
            asyncio.run(self._edge_save(text, out, rate, pitch))
        self._play_audio(out)

    async def _edge_save(self, text: str, path: Path, rate: str, pitch: str) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(
            text,
            self.edge_voice,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(str(path))

    def _play_audio(self, path: Path) -> None:
        if self._stop_event.is_set():
            return
        with self._play_lock:
            if IS_MAC:
                proc = subprocess.Popen(
                    ["afplay", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._current_proc = proc
                proc.wait()
                self._current_proc = None
            elif IS_WINDOWS:
                ps = (
                    f'Add-Type -AssemblyName presentationCore; '
                    f'$p = New-Object System.Windows.Media.MediaPlayer; '
                    f'$p.Open([uri]"{path}"); $p.Play(); '
                    f'Start-Sleep -Seconds 1; '
                    f'while($p.Position -lt $p.NaturalDuration.TimeSpan){{ Start-Sleep -Milliseconds 200 }}'
                )
                proc = subprocess.Popen(
                    ["powershell", "-Command", ps],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._current_proc = proc
                proc.wait()
                self._current_proc = None
            else:
                for cmd in (
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
                    ["mpg123", "-q", str(path)],
                    ["paplay", str(path)],
                ):
                    try:
                        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self._current_proc = proc
                        proc.wait()
                        self._current_proc = None
                        return
                    except Exception:
                        continue
                self._speak_system("Audio playback unavailable.")

    def speak_streamed(self, text: str) -> None:
        """Speak long text sentence by sentence, allowing interruption."""
        if not text:
            return
        import re as _re
        sentences = _re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if self._stop_event.is_set():
                break
            self.speak(sentence)

    # ----- listen -----
    def listen(
        self,
        timeout: float = 8,
        phrase_time_limit: float = 14,
        ambient: float = 0.5,
    ) -> str:
        with sr.Microphone() as source:
            print("● Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=ambient)
            try:
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            except sr.WaitTimeoutError:
                return ""

        # --- Apply noise reduction if available ---
        raw_data = audio.get_wav_data()
        raw_data = self._reduce_noise(raw_data)

        # --- Try MLX Whisper first (local, zero-latency on Apple Silicon) ---
        try:
            import mlx_whisper
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(raw_data)
                tmp_path = f.name

            # Auto-detect language (multilingual) — no language= constraint
            result = mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo="mlx-community/whisper-small",
            )
            command = (result.get("text") or "").strip()

            # Detect language for logging
            lang = result.get("language", "en")
            if lang != "en":
                print(f"[voice] Detected language: {lang}")

            # Clean up temp file
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass

            if command:
                print(f"You: {command}")
                return command.lower().strip()
            return ""

        except ImportError:
            pass
        except Exception as exc:
            print(f"[voice] MLX Whisper error ({exc}), falling back to Google...")

        # --- Fallback: Google cloud speech recognition ---
        try:
            # Rebuild AudioData from (possibly noise-reduced) raw_data
            fallback_audio = sr.AudioData(raw_data, audio.sample_rate, audio.sample_width)
            command = self.recognizer.recognize_google(fallback_audio)
            print(f"You: {command}")
            return command.lower().strip()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            self.speak("Speech recognition is offline. Check your network.")
            return ""

    def _reduce_noise(self, wav_bytes: bytes) -> bytes:
        """Apply AI noise reduction to WAV audio bytes. Returns cleaned WAV bytes."""
        try:
            import noisereduce as nr
            import numpy as np
            import io
            import wave

            # Read WAV bytes into numpy array
            with io.BytesIO(wav_bytes) as buf:
                with wave.open(buf, "rb") as wf:
                    rate = wf.getframerate()
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    frames = wf.readframes(wf.getnframes())

            dtype = np.int16 if sampwidth == 2 else np.int32
            audio_np = np.frombuffer(frames, dtype=dtype).astype(np.float32)

            # Apply noise reduction
            reduced = nr.reduce_noise(
                y=audio_np,
                sr=rate,
                prop_decrease=0.7,
                stationary=False,
            )

            # Convert back to WAV bytes
            reduced_int = np.clip(reduced, -32768, 32767).astype(np.int16)
            out_buf = io.BytesIO()
            with wave.open(out_buf, "wb") as wf:
                wf.setnchannels(n_channels)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(reduced_int.tobytes())
            return out_buf.getvalue()

        except ImportError:
            # noisereduce not installed — return original
            return wav_bytes
        except Exception:
            # Any error — return original
            return wav_bytes

