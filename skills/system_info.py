"""Battery, CPU, disk, and macOS system helpers."""

from __future__ import annotations

import platform
import subprocess
from typing import Optional


def battery_status() -> str:
    try:
        import psutil

        bat = psutil.sensors_battery()
        if bat is None:
            return _mac_battery_fallback() or "No battery telemetry"
        plug = "charging" if bat.power_plugged else "on battery"
        return f"{bat.percent:.0f}% ({plug})"
    except Exception:
        return _mac_battery_fallback() or "Unknown"


def _mac_battery_fallback() -> Optional[str]:
    if platform.system() != "Darwin":
        return None
    try:
        out = subprocess.check_output(["pmset", "-g", "batt"], text=True)
        # e.g. " -InternalBattery-0 (id=...)	82%; discharging; ..."
        for line in out.splitlines():
            if "%" in line:
                return line.strip().split("\t")[-1]
        return out.strip()[:80]
    except Exception:
        return None


def cpu_percent() -> str:
    try:
        import psutil

        return f"{psutil.cpu_percent(interval=0.3):.0f}%"
    except Exception:
        return "—"


def disk_usage_percent() -> float:
    try:
        import psutil

        return float(psutil.disk_usage("/").percent)
    except Exception:
        return 0.0


def system_report() -> str:
    try:
        import psutil

        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        host = platform.node()
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"Host {host}. Current Date/Time: {now}. CPU {psutil.cpu_percent(interval=0.2):.0f} percent. "
            f"Memory {vm.percent:.0f} percent used of {vm.total // (1024**3)} gigabytes. "
            f"Disk {disk.percent:.0f} percent used. "
            f"Battery {battery_status()}."
        )
    except Exception as exc:
        return f"System report unavailable: {exc}"


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    if platform.system() == "Darwin":
        # macOS volume 0–100 mapped to 0–100
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            check=False,
        )
        return f"Volume set to {level} percent."
    return "Volume control is only automated on macOS in this build."


def set_brightness(level: int) -> str:
    """Best-effort brightness (may require permissions)."""
    level = max(0, min(100, int(level)))
    if platform.system() == "Darwin":
        # brightness 0.0–1.0 via osascript is limited; try brightness CLI if present
        try:
            subprocess.run(
                ["brightness", f"{level / 100:.2f}"],
                check=True,
                capture_output=True,
            )
            return f"Brightness set to {level} percent."
        except Exception:
            return (
                "I couldn't adjust brightness without the brightness utility. "
                "Install with: brew install brightness"
            )
    return "Brightness control not available on this platform."


def take_screenshot(path: str = "") -> str:
    import datetime
    from pathlib import Path

    if not path:
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        path = str(
            desktop
            / f"JARVIS_Screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
    if platform.system() == "Darwin":
        subprocess.run(["screencapture", "-x", path], check=False)
        return f"Screenshot saved to {path}."
    if platform.system() == "Windows":
        return "Use Win+PrintScreen on Windows, or install a capture tool."
    subprocess.run(["import", path], check=False)
    return f"Attempted screenshot at {path}."


def open_app(name: str) -> str:
    if platform.system() == "Darwin":
        r = subprocess.run(["open", "-a", name], capture_output=True, text=True)
        if r.returncode == 0:
            return f"Launching {name}."
        # try without exact name
        r2 = subprocess.run(["open", "-a", name.title()], capture_output=True, text=True)
        if r2.returncode == 0:
            return f"Launching {name.title()}."
        return f"Could not open application '{name}'."
    if platform.system() == "Windows":
        subprocess.Popen(name, shell=True)
        return f"Launching {name}."
    subprocess.Popen([name])
    return f"Launching {name}."


def shutdown_pc() -> str:
    if platform.system() == "Darwin":
        subprocess.Popen(
            ["osascript", "-e", 'tell app "System Events" to shut down']
        )
    elif platform.system() == "Windows":
        subprocess.Popen("shutdown /s /t 5", shell=True)
    else:
        subprocess.Popen(["shutdown", "-h", "now"])
    return "Initiating shutdown sequence."


def restart_pc() -> str:
    if platform.system() == "Darwin":
        subprocess.Popen(
            ["osascript", "-e", 'tell app "System Events" to restart']
        )
    elif platform.system() == "Windows":
        subprocess.Popen("shutdown /r /t 5", shell=True)
    else:
        subprocess.Popen(["reboot"])
    return "Restarting systems."
