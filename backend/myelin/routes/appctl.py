"""Talking to the desktop app around the web interface: show the window, start with Windows."""

from __future__ import annotations

import sys

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import __version__

router = APIRouter(prefix="/api/app")


@router.get("")
def app_info(request: Request) -> dict:
    desktop = getattr(request.app.state, "desktop", None)
    autostart = None
    if sys.platform == "win32":
        from ..desktop import autostart_enabled

        autostart = autostart_enabled()
    return {
        "version": __version__,
        "desktop": desktop is not None,
        "windows": sys.platform == "win32",
        "autostart": autostart,
        "hotkey": "Ctrl+Alt+M" if desktop is not None else None,
    }


class AutostartIn(BaseModel):
    enabled: bool


@router.put("/autostart")
def autostart(body: AutostartIn) -> dict:
    if sys.platform != "win32":
        raise HTTPException(409, "Start with Windows is only available on Windows.")
    from ..desktop import autostart_enabled, set_autostart

    set_autostart(body.enabled)
    return {"autostart": autostart_enabled()}


@router.post("/show")
def show(request: Request) -> dict:
    """A second launch of Myelin asks the running one to show its window."""
    desktop = getattr(request.app.state, "desktop", None)
    if desktop is None:
        raise HTTPException(409, "The Myelin app isn't running; this is the server on its own.")
    desktop.show()
    return {"ok": True}
