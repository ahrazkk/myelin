"""Keeps the Windows lock screen picture current.

Uses the Windows Runtime LockScreen API through Windows PowerShell, so no extra packages are
needed. Windows caches lock-screen images by file name, so each picture gets a new name and the
old ones are cleaned up.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

INTERVAL_S = 15 * 60

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and !$_.IsGenericMethod })[0]
function Await($op, $type) {
  $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
function AwaitAction($op) { $t = $asTaskAction.Invoke($null, @($op)); $t.Wait(-1) | Out-Null }
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.System.UserProfile.LockScreen, Windows.System.UserProfile, ContentType = WindowsRuntime] | Out-Null
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($args[0])) ([Windows.Storage.StorageFile])
AwaitAction ([Windows.System.UserProfile.LockScreen]::SetImageFileAsync($file))
"""


def screen_size() -> tuple[int, int]:
    if sys.platform != "win32":
        return 1920, 1080
    try:
        import ctypes

        user32 = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return (w, h) if w and h else (1920, 1080)
    except Exception:
        return 1920, 1080


def set_lock_screen(path: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("The Windows lock screen can only be set on Windows.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
         _SCRIPT, str(path)],
        capture_output=True, text=True, timeout=60, creationflags=flags,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "PowerShell couldn't set the lock screen.")


@dataclass
class LockScreenUpdater:
    """Background loop: every 15 minutes, if enabled, redraw and set the Windows lock screen."""

    folder: Path
    is_enabled: Callable[[], bool]
    render_jpeg: Callable[[int, int], bytes]
    setter: Callable[[Path], None] = set_lock_screen
    last_set: Optional[datetime] = None
    last_error: Optional[str] = None
    _wake: threading.Event = field(default_factory=threading.Event)
    _thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="myelin-lockscreen", daemon=True)
            self._thread.start()

    def refresh_now(self) -> None:
        self._wake.set()

    def run_once(self) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            w, h = screen_size()
            path = self.folder / f"myelin-{int(time.time())}.jpg"
            path.write_bytes(self.render_jpeg(w, h))
            self.setter(path)
            for old in self.folder.glob("myelin-*.jpg"):
                if old != path:
                    old.unlink(missing_ok=True)
            self.last_set = datetime.now().astimezone()
            self.last_error = None
        except Exception as e:  # report, keep looping
            self.last_error = str(e) or type(e).__name__

    def _loop(self) -> None:
        while True:
            if self.is_enabled():
                self.run_once()
            self._wake.wait(INTERVAL_S)
            self._wake.clear()
