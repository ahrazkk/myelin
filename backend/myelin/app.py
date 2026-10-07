"""The local FastAPI server: a JSON API under /api plus the built web UI."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlmodel import Session

from . import __version__
from .config import Config, load_config
from .db import make_engine
from .models import PlanItem, UserSettings
from .planner import ensure_plan
from .prayer import prayers_for
from .streak import streak_summary
from .views import progress_view, week_view

CALC_METHODS = {"NORTH_AMERICA", "MUSLIM_WORLD_LEAGUE", "EGYPTIAN", "KARACHI", "UMM_AL_QURA",
                "DUBAI", "MOON_SIGHTING_COMMITTEE", "KUWAIT", "QATAR", "SINGAPORE", "UOIF"}
ASR_METHODS = {"SHAFI", "HANAFI"}


class SettingsUpdate(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: Optional[str] = None
    calc_method: Optional[str] = None
    asr_method: Optional[str] = None


def _zone(settings: UserSettings) -> Optional[ZoneInfo]:
    if not settings.timezone:
        return None
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        return None


def _item_json(item: PlanItem) -> dict:
    return {
        "id": item.id,
        "track": item.track,
        "kind": item.kind,
        "title": item.title,
        "detail": item.detail,
        "minutes": item.minutes,
        "counts_for_streak": item.counts_for_streak,
        "done": item.done_at is not None,
        "done_at": item.done_at.isoformat() if item.done_at else None,
    }


def _settings_json(s: UserSettings) -> dict:
    return {
        "latitude": s.latitude,
        "longitude": s.longitude,
        "timezone": s.timezone,
        "calc_method": s.calc_method,
        "asr_method": s.asr_method,
        "started_on": s.started_on.isoformat() if s.started_on else None,
        "has_location": s.latitude is not None and s.longitude is not None,
    }


def create_app(
    config: Optional[Config] = None,
    engine: Optional[Engine] = None,
    clock: Optional[Callable[[Optional[ZoneInfo]], datetime]] = None,
) -> FastAPI:
    config = config or load_config()
    engine = engine or make_engine(config.db_url)

    def default_clock(tz: Optional[ZoneInfo]) -> datetime:
        return datetime.now(tz) if tz else datetime.now().astimezone()

    now_in = clock or default_clock

    app = FastAPI(title="Myelin", version=__version__)

    def get_session():
        with Session(engine) as session:
            yield session

    def get_settings(session: Session) -> UserSettings:
        settings = session.get(UserSettings, 1)
        if settings is None:  # pragma: no cover - created by make_engine
            settings = UserSettings(id=1)
            session.add(settings)
            session.commit()
        return settings

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    @app.get("/api/settings")
    def read_settings(session: Session = Depends(get_session)) -> dict:
        return _settings_json(get_settings(session))

    @app.put("/api/settings")
    def update_settings(update: SettingsUpdate, session: Session = Depends(get_session)) -> dict:
        settings = get_settings(session)
        data = update.model_dump(exclude_unset=True)
        if "timezone" in data and data["timezone"] is not None:
            try:
                ZoneInfo(data["timezone"])
            except (ZoneInfoNotFoundError, ValueError):
                raise HTTPException(422, f"Unknown time zone: {data['timezone']}")
        if data.get("calc_method") and data["calc_method"] not in CALC_METHODS:
            raise HTTPException(422, f"Unknown calculation method: {data['calc_method']}")
        if data.get("asr_method") and data["asr_method"] not in ASR_METHODS:
            raise HTTPException(422, f"Unknown Asr method: {data['asr_method']}")
        for key, value in data.items():
            setattr(settings, key, value)
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return _settings_json(settings)

    def context(session: Session) -> tuple[UserSettings, datetime]:
        """Settings and 'now' in the user's time zone. The first visit marks day 1 of the cycle."""
        settings = get_settings(session)
        now = now_in(_zone(settings))
        if settings.started_on is None:
            settings.started_on = now.date()
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return settings, now

    @app.get("/api/today")
    def today(session: Session = Depends(get_session)) -> dict:
        settings, now = context(session)
        day = now.date()
        items = ensure_plan(session, day)

        prayers = None
        if settings.latitude is not None and settings.longitude is not None:
            prayers = prayers_for(now, settings.latitude, settings.longitude, now.tzinfo,
                                  settings.calc_method, settings.asr_method)

        return {
            "date": day.isoformat(),
            "now": now.isoformat(),
            "timezone": settings.timezone,
            "plan": [_item_json(i) for i in items],
            "streak": streak_summary(session, settings.started_on, day),
            "prayers": prayers,
            "needs_setup": prayers is None,
        }

    @app.get("/api/week")
    def week(session: Session = Depends(get_session)) -> dict:
        settings, now = context(session)
        ensure_plan(session, now.date())
        return week_view(session, settings.started_on, now.date())

    @app.get("/api/progress")
    def progress(session: Session = Depends(get_session)) -> dict:
        settings, now = context(session)
        ensure_plan(session, now.date())
        return progress_view(session, settings.started_on, now.date())

    @app.post("/api/plan/{item_id}/toggle")
    def toggle(item_id: int, session: Session = Depends(get_session)) -> dict:
        item = session.get(PlanItem, item_id)
        if item is None:
            raise HTTPException(404, "No plan item with that id")
        settings = get_settings(session)
        item.done_at = None if item.done_at else now_in(_zone(settings))
        session.add(item)
        session.commit()
        session.refresh(item)
        return _item_json(item)

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
