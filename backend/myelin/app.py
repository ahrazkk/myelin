"""The local FastAPI server: a JSON API under /api plus the built web UI."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine

from . import __version__
from .config import Config, load_config
from .db import make_engine
from .routes import focus, problems, sql, system
from .routes import settings as settings_routes
from .routes import today as today_routes


def default_clock(tz: Optional[ZoneInfo]) -> datetime:
    return datetime.now(tz) if tz else datetime.now().astimezone()


def create_app(
    config: Optional[Config] = None,
    engine: Optional[Engine] = None,
    clock: Optional[Callable[[Optional[ZoneInfo]], datetime]] = None,
) -> FastAPI:
    config = config or load_config()
    app = FastAPI(title="Myelin", version=__version__)
    app.state.config = config
    app.state.engine = engine or make_engine(config.db_url)
    app.state.clock = clock or default_clock

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    for router in (settings_routes.router, today_routes.router, focus.router, problems.router,
                   sql.router, system.router):
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
