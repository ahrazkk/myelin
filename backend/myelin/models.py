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

    # Appearance
    theme: str = "auto"  # "auto" (night from Maghrib to sunrise) | "light" | "dark" | "system"
    text_size: str = "normal"  # "normal" | "large" | "larger"
    reduced_motion: bool = False

    # Your day, for the scheduler
    work_start: str = "09:00"
    work_end: str = "17:00"
    work_days: str = "mon,tue,wed,thu,fri"
    office_days: str = "tue,thu"
    commute_minutes: int = 45
    prayer_buffer_minutes: int = 15
    study_cutoff_after_isha: int = 90  # the planning day ends this long after Isha
    calendar_urls: str = ""  # one iCal link per line (Google or Outlook "secret address")

    # Reaching beyond this computer
    phone_access: bool = False  # serve the lock-screen image to your phone on home Wi-Fi
    phone_key: Optional[str] = None
    windows_lockscreen: bool = False  # keep the Windows lock screen picture up to date
    notifications: bool = True


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
