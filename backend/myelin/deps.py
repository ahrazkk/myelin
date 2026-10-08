"""Shared request dependencies: database session, user settings, and 'now' in the user's time zone."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Request
from sqlmodel import Session

from .models import UserSettings


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


def zone(settings: UserSettings) -> Optional[ZoneInfo]:
    if not settings.timezone:
        return None
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        return None


def load_settings(session: Session) -> UserSettings:
    settings = session.get(UserSettings, 1)
    if settings is None:  # pragma: no cover - created by make_engine
        settings = UserSettings(id=1)
        session.add(settings)
        session.commit()
    return settings


def now_for(request: Request, settings: UserSettings) -> datetime:
    return request.app.state.clock(zone(settings))


class Ctx:
    """Everything most endpoints need, in one dependency."""

    def __init__(self, request: Request, session: Session = Depends(get_session)):
        self._setup(request, session)

    @classmethod
    def for_app(cls, app, session: Session) -> "Ctx":
        """A context outside any web request, for background work like the lock screen."""
        ctx = cls.__new__(cls)
        ctx._setup(SimpleNamespace(app=app, client=None), session)
        return ctx

    def _setup(self, request, session: Session) -> None:
        self.request = request
        self.session = session
        self.settings = load_settings(session)
        self.now = request.app.state.clock(zone(self.settings))
        if self.settings.started_on is None:
            # The first visit marks day 1 of the 66-day cycle.
            self.settings.started_on = self.now.date()
            session.add(self.settings)
            session.commit()
            session.refresh(self.settings)

    @property
    def today(self):
        return self.now.date()
