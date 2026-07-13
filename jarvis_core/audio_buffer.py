"""Rolling Audio Buffer for J.A.R.V.I.S."""
from __future__ import annotations

import collections
import threading
import wave
from pathlib import Path

from jarvis_core.config import ROOT

try:
    import pyaudio
except ImportError:
    pyaudio = None

class RollingAudioBuffer:
    def __init__(self, duration_sec: int = 30) -> None:
        self.duration_sec = duration_sec
        self.chunk = 1024
        self.format = pyaudio.paInt16 if pyaudio else 8
        self.channels = 1
        self.rate = 16000
        self.frames_per_sec = self.rate // self.chunk
        self.max_frames = self.frames_per_sec * self.duration_sec
        self.buffer = collections.deque(maxlen=self.max_frames)
        self._stop = threading.Event()
        self._thread = None
        self._pyaudio = None

    def start(self) -> None:
        if not pyaudio:
            print("PyAudio not available for RollingAudioBuffer.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._record_loop, daemon=True, name="jarvis-audio-buffer")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            
    def _record_loop(self) -> None:
        self._pyaudio = pyaudio.PyAudio()
        stream = self._pyaudio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        try:
            while not self._stop.is_set():
                data = stream.read(self.chunk, exception_on_overflow=False)
                self.buffer.append(data)
        except Exception as e:
            print(f"Audio buffer error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            self._pyaudio.terminate()

    def get_recent_transcription(self) -> str:
        if len(self.buffer) == 0:
            return "No audio in buffer."
            
        temp_wav = ROOT / "temp_buffer.wav"
        frames = list(self.buffer)
        
        try:
            import speech_recognition as sr
        except ImportError:
            return "SpeechRecognition not available."
            
        try:
            wf = wave.open(str(temp_wav), 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self._pyaudio.get_sample_size(self.format) if self._pyaudio else 2)
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            r = sr.Recognizer()
            with sr.AudioFile(str(temp_wav)) as source:
                audio = r.record(source)
            text = r.recognize_google(audio)
            return f"Transcribed from the last {self.duration_sec} seconds: '{text}'"
        except sr.UnknownValueError:
            return "Audio in buffer was silent or unintelligible."
        except Exception as e:
            return f"Error transcribing buffer: {e}"

_rab = None

def get_audio_buffer() -> RollingAudioBuffer:
    global _rab
    if _rab is None:
        _rab = RollingAudioBuffer()
    return _rab
