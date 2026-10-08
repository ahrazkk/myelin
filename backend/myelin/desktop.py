"""Myelin as a Windows app.

One process runs everything:
- the local server (which also feeds the Lively wallpaper),
- an app window using Windows' built-in Edge engine (WebView2),
- a tray icon: open, quick add, start focus, quit,
- a global hotkey, Ctrl+Alt+M, that jumps straight to the command box,
- Windows notifications: prayer reminders, block starts and focus endings.

Closing the window keeps Myelin running in the tray. Quit from the tray to stop it.
Run it with `pythonw -m myelin.desktop` (add --background to start hidden in the tray).
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Callable, Optional

import uvicorn

from . import __version__
from .__main__ import network_config
from .app import create_app
from .config import Config, load_config
from .db import make_engine

log = logging.getLogger("myelin.desktop")

APP_ID = "Myelin"
HOTKEY_LABEL = "Ctrl+Alt+M"


# ---------- Local HTTP helpers (the app talks to its own server like the wallpaper does) ----------

def _get(base: str, path: str, timeout: float = 3) -> dict:
    with urllib.request.urlopen(base + path, timeout=timeout) as r:  # noqa: S310 - localhost only
        return json.loads(r.read().decode("utf-8"))


def _post(base: str, path: str, body: Optional[dict] = None, timeout: float = 5) -> dict:
    req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - localhost only
        return json.loads(r.read().decode("utf-8"))


def server_running(base: str) -> bool:
    try:
        return _get(base, "/api/health", timeout=1).get("ok") is True
    except Exception:
        return False


def server_version(base: str) -> Optional[str]:
    """The version of the Myelin server answering at `base`, or None if nothing answers."""
    try:
        health = _get(base, "/api/health", timeout=1)
    except Exception:
        return None
    return str(health.get("version")) if health.get("ok") else None


# ---------- Replacing an older Myelin ----------
# People who ran Myelin from source before installing the app can still have that old server running
# (often started at sign-in by the old Startup shortcut). It holds port 8765, so the new app would
# show the old interface. The app replaces it instead.

def is_myelin_process(name: str, cmdline: str) -> bool:
    name, cmdline = name.lower(), cmdline.lower().replace("\\", "/")
    if name == "myelin.exe":
        return True
    is_python = name.startswith("python") or name.startswith("pythonw")
    return is_python and ("-m myelin" in cmdline or "myelin/__main__" in cmdline or "myelin.desktop" in cmdline)


def stop_old_myelin(port: int, own_pid: Optional[int] = None) -> bool:
    """Stop an older Myelin listening on `port`. True if the port is free afterwards.

    Never touches a process that isn't Myelin, or this process.
    """
    try:
        import psutil
    except ImportError:
        log.warning("psutil is missing, so an older Myelin on port %s can't be replaced.", port)
        return False
    import os

    own_pid = own_pid or os.getpid()
    stopped = False
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.pid == own_pid:
                continue
            if not is_myelin_process(proc.info["name"] or "", " ".join(proc.info["cmdline"] or [])):
                continue
            if not any(c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN
                       for c in proc.net_connections(kind="tcp")):
                continue
            log.info("Stopping an older Myelin (pid %s) that holds port %s.", proc.pid, port)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
            stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if stopped:
        for _ in range(50):
            if server_version(f"http://127.0.0.1:{port}") is None:
                return True
            time.sleep(0.1)
    return server_version(f"http://127.0.0.1:{port}") is None


def remove_old_startup_shortcut() -> None:
    """Older versions started Myelin at sign-in with a Startup-folder shortcut to a source checkout."""
    if sys.platform != "win32":
        return
    import os
    from pathlib import Path

    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut = startup / "Myelin.lnk"
    try:
        if shortcut.exists():
            shortcut.unlink()
            log.info("Removed the old Startup shortcut %s", shortcut)
    except OSError:
        log.warning("Couldn't remove the old Startup shortcut %s", shortcut)


# ---------- Single instance ----------

def _single_instance() -> bool:
    """True if this is the only Myelin app running (Windows named mutex)."""
    if sys.platform != "win32":
        return True
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\MyelinDesktopApp")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def _message_box(title: str, text: str) -> None:
    """A plain Windows message box, for errors before the window exists."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)  # MB_ICONERROR


# ---------- Start with Windows ----------

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" -m myelin.desktop --background'


def autostart_enabled() -> Optional[bool]:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_ID)
            return True
    except FileNotFoundError:
        return False


def set_autostart(enabled: bool) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Start with Windows is only available on Windows.")
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, APP_ID)
            except FileNotFoundError:
                pass


# ---------- Tray icon ----------

def tray_image(size: int = 64):
    """The Myelin mark, in the night palette: two myelin sheaths on an axon with a node between them,
    on a dark tile so it stays readable on light and dark taskbars."""
    from PIL import Image, ImageDraw

    field, myelin, node = (14, 21, 48, 255), (87, 196, 229, 255), (208, 123, 232, 255)
    scale = 4  # draw large, then shrink, for smooth edges at tray sizes
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = big / 32
    d.rounded_rectangle([0, 0, 32 * u - 1, 32 * u - 1], radius=7 * u, fill=field)
    d.line([(3 * u, 16 * u), (29 * u, 16 * u)], fill=myelin, width=max(2, round(1.6 * u)))
    d.rounded_rectangle([4 * u, 12.5 * u, 14 * u, 19.5 * u], radius=3.5 * u, fill=myelin)
    d.rounded_rectangle([18 * u, 12.5 * u, 28 * u, 19.5 * u], radius=3.5 * u, fill=myelin)
    d.ellipse([13.8 * u, 13.8 * u, 18.2 * u, 18.2 * u], fill=node)
    return img.resize((size, size), Image.LANCZOS)


# ---------- Global hotkey ----------

def watch_hotkey(on_press: Callable[[], None]) -> None:
    """Ctrl+Alt+M anywhere in Windows. Runs its own message loop on a daemon thread."""
    if sys.platform != "win32":
        return

    def loop():
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x0312
        if not user32.RegisterHotKey(None, 1, MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, ord("M")):
            log.warning("Couldn't register %s; another app may be using it.", HOTKEY_LABEL)
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                try:
                    on_press()
                except Exception:
                    log.exception("Hotkey handler failed")

    threading.Thread(target=loop, name="myelin-hotkey", daemon=True).start()


# ---------- Notifications ----------

class Notifier:
    """Checks every 30 seconds what's coming up and shows a Windows notification once per event."""

    PRAYER_LEAD = timedelta(minutes=10)

    def __init__(self, base: str, on_click: Callable[[], None]):
        self.base = base
        self.on_click = on_click
        self.sent: set[str] = set()
        self._toaster = None
        if sys.platform == "win32":
            try:
                from windows_toasts import WindowsToaster

                self._toaster = WindowsToaster(APP_ID)
            except Exception:
                log.warning("Windows notifications are unavailable.")

    def show(self, title: str, body: str) -> None:
        if self._toaster is None:
            return
        from windows_toasts import Toast

        toast = Toast([title, body])
        toast.on_activated = lambda _: self.on_click()
        self._toaster.show_toast(toast)

    def _once(self, key: str, title: str, body: str) -> None:
        if key not in self.sent:
            self.sent.add(key)
            self.show(title, body)

    def check(self, now: Optional[datetime] = None) -> None:
        settings = _get(self.base, "/api/settings")
        if not settings.get("notifications", True):
            return
        today = _get(self.base, "/api/today")
        now = now or datetime.fromisoformat(today["now"])

        prayers = today.get("prayers")
        if prayers:
            for t in prayers["times"]:
                if t["name"] == "sunrise":
                    continue
                at = datetime.fromisoformat(t["at"])
                if timedelta(0) < at - now <= self.PRAYER_LEAD:
                    name = t["name"].capitalize()
                    minutes = max(1, round((at - now).total_seconds() / 60))
                    self._once(f"prayer:{t['at']}", f"{name} in {minutes} minutes",
                               f"{name} is at {at.strftime('%I:%M %p').lstrip('0').lower()}.")

        focus = _get(self.base, "/api/focus")
        active = focus.get("active")
        for item in today["plan"]:
            if item["done"] or item.get("status") != "scheduled" or not item.get("start"):
                continue
            start = datetime.fromisoformat(item["start"])
            if timedelta(0) <= now - start <= timedelta(minutes=2) and not active:
                self._once(f"block:{item['id']}:{item['start']}", f"Time for {item['title']}",
                           "Open Myelin and press Start for a focus timer.")

        if active:
            ends = datetime.fromisoformat(active["ends_at"])
            if now >= ends:
                self._once(f"focus:{active['id']}", f"Time's up: {active['label']}",
                           "Mark it done or keep going for 10 more minutes.")

    def run_forever(self) -> None:
        while True:
            try:
                self.check()
            except Exception:
                log.debug("Notification check failed", exc_info=True)
            time.sleep(30)


# ---------- The app ----------

class DesktopApp:
    def __init__(self, config: Config, background: bool):
        self.config = config
        self.base = f"http://127.0.0.1:{config.port}"
        self.background = background
        self.window = None
        self.quitting = False
        self.server: Optional[uvicorn.Server] = None

    # server
    def start_server(self) -> None:
        running = server_version(self.base)
        if running == __version__:
            return  # the same version, e.g. started by scripts\\start.ps1: share it
        if running is not None:
            # An older (or newer) Myelin holds the port. Replace it so the window shows this version.
            if not stop_old_myelin(self.config.port):
                raise RuntimeError(
                    f"Myelin {running} is already running on port {self.config.port} and couldn't be stopped. "
                    "Quit it from its tray icon or Task Manager, then open Myelin again.")
        engine = make_engine(self.config.db_url)
        self.config = network_config(self.config, engine)
        app = create_app(self.config, engine)
        app.state.desktop = self
        self.server = uvicorn.Server(uvicorn.Config(app, host=self.config.host, port=self.config.port,
                                                    log_level="warning"))
        threading.Thread(target=self.server.run, name="myelin-server", daemon=True).start()
        for _ in range(100):
            if server_running(self.base):
                return
            time.sleep(0.1)
        raise RuntimeError(f"Myelin's server didn't start on port {self.config.port}.")

    # window
    def show(self) -> None:
        if self.window is not None:
            self.window.show()
            self.window.restore()

    def quick_add(self) -> None:
        self.show()
        if self.window is not None:
            self.window.evaluate_js("window.dispatchEvent(new Event('myelin:command'))")

    def start_focus(self) -> None:
        try:
            _post(self.base, "/api/command", {"text": "focus"})
        except Exception:
            log.exception("Couldn't start a focus session")
        self.show()

    def quit(self) -> None:
        self.quitting = True
        if self.server is not None:
            self.server.should_exit = True
        if self.window is not None:
            self.window.destroy()

    def _on_closing(self):
        if self.quitting:
            return True
        self.window.hide()  # keep running in the tray
        return False

    # tray
    def start_tray(self) -> None:
        try:
            import pystray
        except ImportError:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Open Myelin", lambda: self.show(), default=True),
            pystray.MenuItem(f"Quick add ({HOTKEY_LABEL})", lambda: self.quick_add()),
            pystray.MenuItem("Start focus on the next block", lambda: self.start_focus()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Myelin", lambda icon: (icon.stop(), self.quit())),
        )
        icon = pystray.Icon(APP_ID, tray_image(), "Myelin", menu)
        threading.Thread(target=icon.run, name="myelin-tray", daemon=True).start()

    def run(self) -> None:
        import webview

        remove_old_startup_shortcut()
        try:
            self.start_server()
        except RuntimeError as e:
            log.error("%s", e)
            _message_box("Myelin couldn't start", str(e))
            return
        self.window = webview.create_window(
            "Myelin",
            self.base + "/",
            width=1320,
            height=860,
            min_size=(900, 620),
            hidden=self.background,
            background_color="#0e1530",
            text_select=True,
        )
        self.window.events.closing += self._on_closing
        self.start_tray()
        watch_hotkey(self.quick_add)
        threading.Thread(target=Notifier(self.base, self.show).run_forever, name="myelin-notify",
                         daemon=True).start()
        webview.start(private_mode=False, storage_path=str(self.config.data_dir / "webview"))


def main(argv: Optional[list[str]] = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if "--server-only" in argv:  # no window, tray or hotkey: just the server (used by CI's smoke test)
        from .__main__ import main as serve

        serve()
        return
    config = load_config()
    if sys.stdout is None or sys.stderr is None:  # pythonw / packaged app: log to a file
        logfile = open(config.data_dir / "myelin.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or logfile
        sys.stderr = sys.stderr or logfile
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    if not _single_instance():
        # Already running: ask that copy to show its window, then step aside.
        try:
            _post(f"http://127.0.0.1:{config.port}", "/api/app/show")
        except Exception:
            pass
        return

    DesktopApp(config, background="--background" in argv).run()


if __name__ == "__main__":
    main()
