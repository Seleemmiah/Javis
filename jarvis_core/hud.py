"""Iron Man style terminal HUD using Rich."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from typing import Deque, Optional

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from jarvis_core import __version__


class HUD:
    """Live-updating cyan/gold HUD for J.A.R.V.I.S."""

    def __init__(self) -> None:
        self.console = Console()
        self.mode = "STANDBY"  # STANDBY | AWAKE | EXECUTING | ALERT
        self.status_line = "Systems nominal. Awaiting double-clap or voice command."
        self.mic_level = 0.0
        self.battery: Optional[str] = None
        self.cpu: Optional[str] = None
        self.last_user = ""
        self.last_jarvis = ""
        self.log: Deque[str] = deque(maxlen=8)
        self._lock = threading.Lock()
        self._live: Optional[Live] = None
        self._running = False

    def log_event(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.log.appendleft(f"[dim]{ts}[/] {msg}")

    def set_mode(self, mode: str) -> None:
        with self._lock:
            self.mode = mode

    def set_status(self, text: str) -> None:
        with self._lock:
            self.status_line = text

    def set_levels(self, mic: float = None, battery: str = None, cpu: str = None) -> None:
        with self._lock:
            if mic is not None:
                self.mic_level = mic
            if battery is not None:
                self.battery = battery
            if cpu is not None:
                self.cpu = cpu

    def set_exchange(self, user: str = None, jarvis: str = None) -> None:
        with self._lock:
            if user is not None:
                self.last_user = user
            if jarvis is not None:
                self.last_jarvis = jarvis

    def _meter(self, value: float, width: int = 20) -> str:
        filled = int(max(0.0, min(1.0, value)) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[cyan]{bar}[/]"

    def _mode_style(self) -> str:
        m = self.mode
        if m == "AWAKE":
            return "[bold green]● AWAKE[/]"
        if m == "EXECUTING":
            return "[bold yellow]◆ EXECUTING[/]"
        if m == "ALERT":
            return "[bold red]▲ ALERT[/]"
        return "[bold blue]○ STANDBY[/]"

    def render(self) -> Panel:
        with self._lock:
            mode = self._mode_style()
            status = self.status_line
            mic = self.mic_level
            battery = self.battery or "—"
            cpu = self.cpu or "—"
            user = self.last_user or "—"
            jarvis = self.last_jarvis or "—"
            logs = list(self.log)

        header = Table.grid(expand=True)
        header.add_column(justify="left")
        header.add_column(justify="center")
        header.add_column(justify="right")
        now = datetime.now().strftime("%A %d %b  %H:%M:%S")
        header.add_row(
            f"[bold cyan]J.A.R.V.I.S.[/] [dim]v{__version__}[/]",
            mode,
            f"[dim]{now}[/]",
        )

        vitals = Table.grid(expand=True)
        vitals.add_column()
        vitals.add_column()
        vitals.add_column()
        vitals.add_row(
            f"Battery  [cyan]{battery}[/]",
            f"CPU  [cyan]{cpu}[/]",
            f"Mic  {self._meter(mic)}",
        )

        body = Table.grid(padding=(0, 1))
        body.add_column(ratio=1)
        body.add_row(f"[bold]Status[/]  {status}")
        body.add_row(f"[bold green]You[/]     {user[:120]}")
        body.add_row(f"[bold cyan]J.A.R.V.I.S.[/]  {jarvis[:120]}")

        log_text = "\n".join(logs) if logs else "[dim]No events yet[/]"
        footer = Text.from_markup(
            "[dim]Clap twice to wake  ·  Say commands while awake  ·  "
            "'standby' or 'go offline' to sleep  ·  Ctrl+C to exit[/]"
        )

        group = Group(
            header,
            Text(""),
            vitals,
            Text(""),
            body,
            Text(""),
            Panel(log_text, title="[cyan]Event log[/]", border_style="cyan", height=10),
            footer,
        )
        return Panel(
            group,
            title="[bold cyan]◆ STARK INDUSTRIES — PERSONAL AI INTERFACE ◆[/]",
            border_style="cyan",
            padding=(1, 2),
        )

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        def _run() -> None:
            with Live(
                self.render(),
                console=self.console,
                refresh_per_second=8,
                screen=True,
            ) as live:
                self._live = live
                while self._running:
                    live.update(self.render())
                    time.sleep(0.12)

        t = threading.Thread(target=_run, daemon=True, name="jarvis-hud")
        t.start()

    def stop(self) -> None:
        self._running = False
        self._live = None

    def print_fallback(self, msg: str) -> None:
        """When HUD is not suitable, still print."""
        self.console.print(f"[cyan]J.A.R.V.I.S.[/] {msg}")
