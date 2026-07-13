"""Proactive background alerts — battery, disk, calendar, optional news."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from jarvis_core.config import (
    ALERT_INTERVAL,
    BATTERY_WARN_PERCENT,
    DISK_WARN_PERCENT,
    IS_MAC,
    PROACTIVE_NEWS,
)
from skills import system_info
from skills import web


class AlertMonitor:
    def __init__(
        self,
        on_alert: Callable[[str], None],
        on_vitals: Optional[Callable[[str, str], None]] = None,
        interval: float = ALERT_INTERVAL,
    ) -> None:
        self.on_alert = on_alert
        self.on_vitals = on_vitals
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._warned_battery = False
        self._warned_disk = False
        self._last_calendar_ping = 0.0
        self._last_news_ping = 0.0
        self._morning_done_day = -1

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="jarvis-alerts"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                print(f"[alerts] {exc}")
            self._stop.wait(self.interval)

    def _tick(self) -> None:
        bat = system_info.battery_status()
        cpu = system_info.cpu_percent()
        if self.on_vitals:
            self.on_vitals(bat, cpu)

        percent = None
        for token in bat.replace("%", " % ").split():
            token = token.strip("%")
            if token.replace(".", "", 1).isdigit():
                percent = float(token)
                break

        if percent is not None:
            if percent <= BATTERY_WARN_PERCENT and "charg" not in bat.lower():
                if not self._warned_battery:
                    self._warned_battery = True
                    self.on_alert(
                        f"Power levels critical at {percent:.0f} percent. "
                        "I recommend connecting a charger."
                    )
            else:
                self._warned_battery = False

        disk = system_info.disk_usage_percent()
        if disk >= DISK_WARN_PERCENT:
            if not self._warned_disk:
                self._warned_disk = True
                self.on_alert(
                    f"Disk usage is elevated at {disk:.0f} percent. "
                    "You may want to free some space."
                )
        else:
            self._warned_disk = False

        now = time.time()

        if IS_MAC:
            if not hasattr(self, "_last_dl_count"):
                self._last_dl_count = -1
            if now - getattr(self, "_last_dl_ping", 0) > 300:
                self._last_dl_ping = now
                import os
                from pathlib import Path
                dl_dir = Path(os.path.expanduser("~/Downloads"))
                if dl_dir.exists():
                    count = len(list(dl_dir.glob("*")))
                    if count > self._last_dl_count and self._last_dl_count != -1:
                        self.on_alert("A new file has finished downloading.")
                    self._last_dl_count = count
            
            if now - getattr(self, "_last_git_ping", 0) > 3600:
                self._last_git_ping = now
                try:
                    from skills import shell as shell_mod
                    from jarvis_core.config import ROOT
                    out = shell_mod.run_shell(f"cd {ROOT} && git status --porcelain")
                    if out.strip():
                        self.on_alert("You have uncommitted changes in the JARVIS repository.")
                except Exception:
                    pass
            
            if now - getattr(self, "_last_arp_ping", 0) > 600:
                self._last_arp_ping = now
                if not hasattr(self, "_known_macs"):
                    self._known_macs = set()
                try:
                    from skills import shell as shell_mod
                    out = shell_mod.run_shell("arp -a")
                    macs = set()
                    import re
                    for line in out.splitlines():
                        m = re.search(r'([0-9a-f]{1,2}(:[0-9a-f]{1,2}){5})', line.lower())
                        if m:
                            macs.add(m.group(1))
                    if not self._known_macs:
                        self._known_macs = macs
                    else:
                        new_macs = macs - self._known_macs
                        if new_macs:
                            self.on_alert("Security Alert: Unrecognized device detected on the local network.")
                            self._known_macs.update(new_macs)
                except Exception:
                    pass

            if now - getattr(self, "_last_cpu_ping", 0) > 60:
                self._last_cpu_ping = now
                try:
                    import psutil
                    high_cpu = []
                    for proc in psutil.process_iter(['name', 'cpu_percent']):
                        if proc.info['cpu_percent'] is not None and proc.info['cpu_percent'] > 90.0:
                            high_cpu.append(proc.info['name'])
                    if high_cpu:
                        names = ", ".join(high_cpu[:2])
                        self.on_alert(f"Warning: High CPU usage detected from: {names}.")
                except Exception:
                    pass

            if now - getattr(self, "_last_imessage_ping", 0) > 30:
                self._last_imessage_ping = now
                try:
                    import sqlite3
                    import os
                    from pathlib import Path
                    chat_db = Path(os.path.expanduser("~/Library/Messages/chat.db"))
                    if chat_db.exists():
                        conn = sqlite3.connect(str(chat_db))
                        c = conn.cursor()
                        mac_now = time.time() - 978307200
                        five_mins_ago = mac_now - 300
                        query = """
                        SELECT text, handle.id, message.date 
                        FROM message 
                        JOIN handle ON message.handle_id = handle.ROWID 
                        WHERE is_from_me = 0 AND date > ? ORDER BY date DESC LIMIT 5
                        """
                        c.execute(query, (five_mins_ago * 1000000000,)) 
                        rows = c.fetchall()
                        conn.close()
                        if not hasattr(self, "_processed_imessages"):
                            self._processed_imessages = set()
                        for text, sender, date in rows:
                            if text and date not in self._processed_imessages:
                                self._processed_imessages.add(date)
                                if text.lower().startswith("jarvis"):
                                    self.on_alert(f"Incoming command from {sender} via iMessage: {text}")
                except Exception:
                    pass

            if now - getattr(self, "_last_context_ping", 0) > 120:
                self._last_context_ping = now
                try:
                    import subprocess
                    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                    res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
                    app_name = res.stdout.strip()
                    if app_name in ("Code", "Cursor", "Terminal", "Safari", "Google Chrome", "Pages", "Word"):
                        script_win = f'tell application "System Events" to tell process "{app_name}" to get name of front window'
                        res_win = subprocess.run(["osascript", "-e", script_win], capture_output=True, text=True)
                        win_title = res_win.stdout.strip()
                        if win_title and len(win_title) > 3:
                            from jarvis_core.indexer import get_indexer
                            results = get_indexer().search(win_title, top_k=1)
                            if results and results[0]["score"] < 0.8:
                                self.on_alert(f"Sir, I found a document related to your active work ({win_title[:30]}): {results[0]['text'][:80]}...")
                except Exception:
                    pass

        now = time.time()
        hour = datetime.now().hour
        day = datetime.now().day

        # Morning briefing once per day (7–10 local)
        if 7 <= hour <= 10 and self._morning_done_day != day:
            self._morning_done_day = day
            msg = f"Good morning briefing. Battery {bat}. CPU {cpu}."
            if IS_MAC:
                try:
                    from jarvis_core import calendar_mac

                    cal = calendar_mac.todays_events()
                    if cal and "No events" not in cal:
                        msg += " " + cal.replace("\n", "; ")[:280]
                except Exception:
                    pass
            self.on_alert(msg)

        # Calendar refresh every ~30 min during work hours
        if IS_MAC and 8 <= hour <= 20 and now - self._last_calendar_ping > 1800:
            self._last_calendar_ping = now
            # silent vitals only — avoid nagging; morning covers main case

        if PROACTIVE_NEWS and now - self._last_news_ping > 6 * 3600:
            self._last_news_ping = now
            try:
                headline = web.latest_news("top technology")
                self.on_alert("Tech pulse: " + headline[:280])
            except Exception:
                pass
