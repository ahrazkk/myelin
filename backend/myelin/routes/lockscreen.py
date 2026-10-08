"""Lock-screen pictures for Windows and your phone."""

from __future__ import annotations

import socket
import sys

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .. import lockscreen
from ..deps import Ctx
from .today import today as today_data

router = APIRouter()

PHONE_SIZE = (1179, 2556)  # iPhone 15 / 16; the image scales to other phones


def lan_ip() -> str | None:
    """This computer's address on the home network (no packets are sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))  # TEST-NET address: never routed, only picks an interface
            return s.getsockname()[0]
    except OSError:
        return None


def picture(ctx: Ctx, width: int, height: int, layout: str):
    return lockscreen.render(lockscreen.snapshot(today_data(ctx)), width, height, layout)


@router.get("/lockscreen/phone.png")
def phone_png(ctx: Ctx = Depends(), key: str = "", w: int = PHONE_SIZE[0], h: int = PHONE_SIZE[1]) -> Response:
    local = ctx.request.client is None or ctx.request.client.host in ("127.0.0.1", "::1", "testclient")
    if not local and (not ctx.settings.phone_access or key != ctx.settings.phone_key):
        raise HTTPException(403, "Turn on phone access in Myelin's settings and use the link it shows.")
    w, h = max(320, min(w, 3000)), max(480, min(h, 6000))
    return Response(lockscreen.png(picture(ctx, w, h, "phone")), media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@router.get("/lockscreen/desktop.png")
def desktop_png(ctx: Ctx = Depends(), w: int = 1920, h: int = 1080) -> Response:
    w, h = max(640, min(w, 7680)), max(360, min(h, 4320))
    return Response(lockscreen.png(picture(ctx, w, h, "desktop")), media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@router.get("/api/lockscreen")
def status(request: Request, ctx: Ctx = Depends()) -> dict:
    updater = getattr(request.app.state, "lock_updater", None)
    ip = lan_ip()
    port = request.app.state.config.port
    s = ctx.settings
    phone_url = (f"http://{ip}:{port}/lockscreen/phone.png?key={s.phone_key}"
                 if ip and s.phone_access and s.phone_key else None)
    return {
        "windows": {
            "available": sys.platform == "win32",
            "enabled": s.windows_lockscreen,
            "last_set": updater.last_set.isoformat() if updater and updater.last_set else None,
            "error": updater.last_error if updater else None,
        },
        "phone": {
            "enabled": s.phone_access,
            "url": phone_url,
            "listening_on_network": request.app.state.config.host not in ("127.0.0.1", "localhost"),
        },
    }


@router.post("/api/lockscreen/windows/refresh")
def refresh_windows(request: Request) -> dict:
    updater = getattr(request.app.state, "lock_updater", None)
    if updater is None:
        raise HTTPException(409, "The Windows lock screen updater only runs on Windows.")
    updater.refresh_now()
    return {"ok": True}
