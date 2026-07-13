"""Menu Bar (System Tray) HUD for J.A.R.V.I.S."""
from __future__ import annotations

import threading
import time
from datetime import datetime

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item


class DesktopHUD:
    def __init__(self) -> None:
        self.mode = "STANDBY"
        self.status = "Systems nominal."
        self.battery = "—"
        self.cpu = "—"
        self.last_jarvis = ""
        self.last_user = ""
        self._lock = threading.Lock()
        
        self.icon = pystray.Icon(
            "jarvis", 
            self._create_image("gray"), 
            menu=self._build_menu()
        )
        self._running = False
        self._update_thread = None

    def _create_image(self, color: str) -> Image.Image:
        """Generate a 64x64 icon."""
        width = 64
        height = 64
        
        colors = {
            "gray": (100, 100, 100),
            "blue": (0, 120, 255),
            "green": (0, 255, 0),
            "yellow": (255, 200, 0),
            "red": (255, 0, 0)
        }
        fill = colors.get(color, colors["gray"])
        
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        # Draw a circle for the core
        dc.ellipse((8, 8, 56, 56), fill=fill)
        # Draw inner ring
        dc.ellipse((16, 16, 48, 48), fill=(255, 255, 255, 128))
        return image

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            item(lambda text: f"Mode: {self.mode}", lambda icon, item: None, enabled=False),
            item(lambda text: f"{self.status[:40]}", lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(lambda text: f"JARVIS: {self.last_jarvis[:60]}", lambda icon, item: None, enabled=False),
            item(lambda text: f"You: {self.last_user[:60]}", lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(lambda text: f"BAT: {self.battery} | CPU: {self.cpu}", lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item('Quit J.A.R.V.I.S.', self._on_quit)
        )

    def _on_quit(self, icon, item):
        self.stop()
        
    def set_levels(self, battery: str = None, cpu: str = None, **kwargs) -> None:
        with self._lock:
            if battery: self.battery = battery
            if cpu: self.cpu = cpu

    def set_mode(self, mode: str) -> None:
        with self._lock:
            self.mode = mode
            
        color = "gray"
        if mode == "STANDBY":
            color = "blue"
        elif mode == "AWAKE":
            color = "green"
        elif mode == "EXECUTING":
            color = "yellow"
        elif mode == "ALERT":
            color = "red"
            
        self.icon.icon = self._create_image(color)

    def set_status(self, text: str) -> None:
        with self._lock:
            self.status = text

    def set_exchange(self, user: str = None, jarvis: str = None) -> None:
        with self._lock:
            if jarvis: self.last_jarvis = jarvis
            if user: self.last_user = user

    def log_event(self, msg: str) -> None:
        pass  # We don't show full logs in the menu bar to save space

    def _updater_loop(self):
        """Periodically refresh the menu text."""
        while self._running:
            time.sleep(2)
            try:
                # Force menu text update
                if hasattr(self.icon, 'update_menu'):
                    self.icon.update_menu()
            except Exception:
                pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._update_thread = threading.Thread(target=self._updater_loop, daemon=True)
        self._update_thread.start()

    def run_main_loop(self) -> None:
        """Blocks and runs the menu bar app."""
        self.icon.run()

    def stop(self) -> None:
        self._running = False
        try:
            self.icon.stop()
        except Exception:
            pass
