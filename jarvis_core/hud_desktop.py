"""Transparent desktop widget HUD for J.A.R.V.I.S."""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime

class DesktopHUD:
    def __init__(self) -> None:
        self.root = None
        self._running = False
        self._thread = None
        self.mode = "STANDBY"
        self.status = "Systems nominal."
        self.battery = "—"
        self.cpu = "—"
        self.log = []
        self.last_jarvis = ""
        self.last_user = ""
        self._lock = threading.Lock()

    def set_levels(self, battery: str = None, cpu: str = None, **kwargs) -> None:
        with self._lock:
            if battery: self.battery = battery
            if cpu: self.cpu = cpu

    def set_mode(self, mode: str) -> None:
        with self._lock:
            self.mode = mode

    def set_status(self, text: str) -> None:
        with self._lock:
            self.status = text

    def set_exchange(self, user: str = None, jarvis: str = None) -> None:
        with self._lock:
            if jarvis: self.last_jarvis = jarvis
            if user: self.last_user = user

    def log_event(self, msg: str) -> None:
        with self._lock:
            self.log.append(msg)
            if len(self.log) > 5:
                self.log.pop(0)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        # We don't start the thread here anymore. Tkinter runs on main thread.

    def run_main_loop(self) -> None:
        self._run_tk()

    def stop(self) -> None:
        self._running = False
        if self.root:
            self.root.quit()

    def _run_tk(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True) # Frameless
        self.root.attributes('-alpha', 0.85) # Transparent
        self.root.attributes('-topmost', True) # Always on top
        self.root.configure(bg='#000510')

        screen_width = self.root.winfo_screenwidth()
        width = 320
        height = 280
        x = screen_width - width - 20
        y = 40
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.title_lbl = tk.Label(self.root, text="J.A.R.V.I.S.", font=("Courier", 16, "bold"), fg="#00ffff", bg="#000510")
        self.title_lbl.pack(anchor="w", padx=10, pady=(10, 0))

        self.mode_lbl = tk.Label(self.root, text="STANDBY", font=("Courier", 12, "bold"), fg="#0055ff", bg="#000510")
        self.mode_lbl.pack(anchor="w", padx=10)

        self.vitals_lbl = tk.Label(self.root, text="BAT: -- | CPU: --", font=("Courier", 10), fg="#00ffff", bg="#000510")
        self.vitals_lbl.pack(anchor="w", padx=10, pady=5)

        self.status_lbl = tk.Label(self.root, text="Status", font=("Courier", 10), fg="white", bg="#000510", wraplength=300, justify="left")
        self.status_lbl.pack(anchor="w", padx=10)
        
        self.jarvis_lbl = tk.Label(self.root, text="", font=("Courier", 10, "italic"), fg="#00ffff", bg="#000510", wraplength=300, justify="left")
        self.jarvis_lbl.pack(anchor="w", padx=10, pady=5)

        self.log_lbl = tk.Label(self.root, text="", font=("Courier", 9), fg="#888888", bg="#000510", justify="left", wraplength=300)
        self.log_lbl.pack(anchor="w", padx=10, pady=(10, 0))

        self._update_ui()
        self.root.mainloop()

    def _update_ui(self) -> None:
        if not self._running:
            self.root.destroy()
            return
            
        with self._lock:
            self.title_lbl.config(text=f"J.A.R.V.I.S.  [{datetime.now().strftime('%H:%M:%S')}]")
            
            mode_colors = {"STANDBY": "#0055ff", "AWAKE": "#00ff00", "EXECUTING": "#ffff00", "ALERT": "#ff0000"}
            self.mode_lbl.config(text=f"[{self.mode}]", fg=mode_colors.get(self.mode, "white"))
            
            self.vitals_lbl.config(text=f"BAT: {self.battery} | CPU: {self.cpu}")
            self.status_lbl.config(text=self.status[:120])
            self.jarvis_lbl.config(text=self.last_jarvis[:150])
            self.log_lbl.config(text="\n".join(self.log))
            
        self.root.after(200, self._update_ui)
