"""Small helpers for the host computer."""

from __future__ import annotations

import webbrowser
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api")


class OpenIn(BaseModel):
    url: str


@router.post("/open")
def open_link(body: OpenIn, request: Request) -> dict:
    """Open a web link in the default browser.

    The wallpaper (inside Lively) and the app window can't open new browser windows themselves,
    so they ask Myelin to do it. Only http(s) links, and only from this computer.
    """
    if request.client and request.client.host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "Links can only be opened from this computer")
    parsed = urlparse(body.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(422, "Only http and https links can be opened")
    opener = getattr(request.app.state, "open_url", webbrowser.open)
    opener(body.url)
    return {"ok": True}
