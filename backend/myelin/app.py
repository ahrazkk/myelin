"""The local FastAPI server: a JSON API under /api plus the built web UI."""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlmodel import Session

from . import __version__
from .calendar_sync import CalendarCache
from .config import Config, load_config
from .db import make_engine
from . import lockscreen
from .deps import Ctx, load_settings
from .routes import appctl, focus, lockscreen as lockscreen_routes, problems, sql, system
from .routes import settings as settings_routes
from .routes import today as today_routes


def default_clock(tz: Optional[ZoneInfo]) -> datetime:
    return datetime.now(tz) if tz else datetime.now().astimezone()


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
# The only thing another device on your network may fetch, and only with the key.
NETWORK_PATHS = {"/lockscreen/phone.png"}


def create_app(
    config: Optional[Config] = None,
    engine: Optional[Engine] = None,
    clock: Optional[Callable[[Optional[ZoneInfo]], datetime]] = None,
    background: bool = True,
) -> FastAPI:
    config = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if background and sys.platform == "win32":
            from .routes.today import today as today_data
            from .winlock import LockScreenUpdater

            def enabled() -> bool:
                with Session(app.state.engine) as s:
                    return load_settings(s).windows_lockscreen

            def render_jpeg(w: int, h: int) -> bytes:
                with Session(app.state.engine) as s:
                    snap = lockscreen.snapshot(today_data(Ctx.for_app(app, s)))
                return lockscreen.jpeg(lockscreen.render(snap, w, h, "desktop"))

            app.state.lock_updater = LockScreenUpdater(config.data_dir / "lockscreen", enabled, render_jpeg)
            app.state.lock_updater.start()
        yield

    app = FastAPI(title="Myelin", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def only_this_computer(request: Request, call_next):
        # With phone access on, Myelin listens on your home network. Everything except the
        # lock-screen picture stays private to this computer.
        client = request.client.host if request.client else "testclient"
        if client not in LOCAL_HOSTS and request.url.path not in NETWORK_PATHS:
            return JSONResponse({"detail": "Myelin only answers this computer."}, status_code=403)
        return await call_next(request)

    app.state.config = config
    app.state.engine = engine or make_engine(config.db_url)
    app.state.clock = clock or default_clock
    app.state.calendars = CalendarCache()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    for router in (settings_routes.router, today_routes.router, focus.router, problems.router,
                   sql.router, system.router, lockscreen_routes.router, appctl.router):
        app.include_router(router)

    _mount_frontend(app, config)
    return app


def _mount_frontend(app: FastAPI, config: Config) -> None:
    dist = config.frontend_dist
    index = dist / "index.html"

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(
            "<h1>Myelin is running</h1><p>The web interface has not been built yet. "
            "Run <code>scripts\\setup.ps1</code>, then restart Myelin.</p>",
            status_code=200,
        )
