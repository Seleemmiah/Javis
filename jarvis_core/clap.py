"""Double-clap wake detection using the microphone stream."""

from __future__ import annotations

import struct
import time
from typing import Callable, Optional

from jarvis_core.config import (
    CLAP_CHUNK,
    CLAP_COOLDOWN,
    CLAP_MAX_GAP,
    CLAP_MIN_GAP,
    CLAP_SAMPLE_RATE,
    CLAP_THRESHOLD,
)


class ClapDetector:
    """
    Listens for two sharp volume spikes (claps) in quick succession.
    Uses PyAudio so we do not need sounddevice.
    """

    def __init__(
        self,
        on_double_clap: Optional[Callable[[], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
        threshold: float = CLAP_THRESHOLD,
    ) -> None:
        self.on_double_clap = on_double_clap
        self.on_level = on_level
        self.threshold = threshold
        self._running = False
        self._paused = False
        self._last_peak = 0.0
        self._last_wake = 0.0
        self._ambient = 0.02
        self._pa = None
        self._stream = None

    def _rms(self, data: bytes) -> float:
        count = len(data) // 2
        if count == 0:
            return 0.0
        fmt = f"<{count}h"
        samples = struct.unpack(fmt, data[: count * 2])
        acc = sum(s * s for s in samples) / count
        return (acc ** 0.5) / 32768.0

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._last_peak = 0.0

    def stop(self) -> None:
        self._running = False
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass
        self._stream = None
        self._pa = None

    def listen_forever(self) -> None:
        """Blocking loop — run in a background thread."""
        try:
            import pyaudio
        except ImportError:
            print("[clap] PyAudio not installed — double-clap wake disabled.")
            return

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=CLAP_SAMPLE_RATE,
            input=True,
            frames_per_buffer=CLAP_CHUNK,
        )
        self._running = True
        print("[clap] Double-clap detector armed. Clap twice to wake J.A.R.V.I.S.")

        # Short ambient calibration
        samples = []
        for _ in range(20):
            raw = self._stream.read(CLAP_CHUNK, exception_on_overflow=False)
            samples.append(self._rms(raw))
        if samples:
            self._ambient = max(0.01, sorted(samples)[len(samples) // 2] * 1.5)

        while self._running:
            try:
                raw = self._stream.read(CLAP_CHUNK, exception_on_overflow=False)
            except Exception:
                time.sleep(0.05)
                continue

            level = self._rms(raw)
            # Slow ambient adapt when quiet
            if level < self._ambient * 1.2:
                self._ambient = 0.95 * self._ambient + 0.05 * max(level, 0.005)

            norm = level / max(self._ambient, 0.01)
            if self.on_level:
                try:
                    self.on_level(min(1.0, level * 4))
                except Exception:
                    pass

            if self._paused:
                continue

            now = time.time()
            if now - self._last_wake < CLAP_COOLDOWN:
                continue

            # Peak = significantly above ambient
            is_peak = norm >= (1.0 + self.threshold * 3) and level > 0.08
            if not is_peak:
                continue

            if self._last_peak == 0.0:
                self._last_peak = now
                continue

            gap = now - self._last_peak
            if CLAP_MIN_GAP <= gap <= CLAP_MAX_GAP:
                self._last_peak = 0.0
                self._last_wake = now
                print("[clap] ★ Double clap detected — waking.")
                if self.on_double_clap:
                    try:
                        self.on_double_clap()
                    except Exception as exc:
                        print(f"[clap] wake handler error: {exc}")
            elif gap > CLAP_MAX_GAP:
                # First clap of a new pair
                self._last_peak = now
            else:
                # Too close (noise) — keep first peak
                pass
