"""Database tables. SQLite via SQLModel."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class UserSettings(SQLModel, table=True):
    """One row (id=1) holding this person's setup."""

    id: int = Field(default=1, primary_key=True)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None  # IANA name, e.g. "America/Toronto"
    calc_method: str = "NORTH_AMERICA"  # ISNA
    asr_method: str = "SHAFI"  # standard; "HANAFI" also supported
    started_on: Optional[date] = None  # day 1 of the 66-day cycle


class PlanItem(SQLModel, table=True):
    """One block on one day's plan."""

    id: Optional[int] = Field(default=None, primary_key=True)
    day: date = Field(index=True)
    position: int = 0
    track: str  # key from defaults/routine.json
    kind: str  # "faith" | "interview" | "body"
    title: str
    detail: str = ""
    minutes: int = 0
    counts_for_streak: bool = False
    done_at: Optional[datetime] = None
