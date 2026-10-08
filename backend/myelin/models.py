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


class FocusSession(SQLModel, table=True):
    """A timed focus block, optionally tied to a plan item."""

    id: Optional[int] = Field(default=None, primary_key=True)
    plan_item_id: Optional[int] = None
    label: str
    started_at: datetime
    planned_minutes: int
    ended_at: Optional[datetime] = None
    completed: bool = False  # ran all the way to the planned end


class Note(SQLModel, table=True):
    """Brain dump: a thought parked so it doesn't break focus."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime
    text: str
    done_at: Optional[datetime] = None


class Problem(SQLModel, table=True):
    """A LeetCode/NeetCode problem in the re-solve queue."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    url: str = ""
    track: str = "python"  # "python" | "sql"
    difficulty: str = "medium"  # "easy" | "medium" | "hard"
    pattern: str = ""
    created_on: date
    stage: int = 0  # successful spaced re-solves so far
    due_on: Optional[date] = Field(default=None, index=True)  # None once mastered


class Attempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: int = Field(index=True)
    day: date
    outcome: str  # "solved" | "hint" | "stuck"
    minutes: int = 0
    note: str = ""


class SqlSolve(SQLModel, table=True):
    question_id: str = Field(primary_key=True)
    solved_at: datetime
    tries: int = 1


class BusyBlock(SQLModel, table=True):
    """Time you told Myelin about: busy (e.g. a meeting) or free (e.g. a slow afternoon at work)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    day: date = Field(index=True)
    start: datetime
    end: datetime
    label: str = "Busy"
    kind: str = "busy"  # "busy" | "free"


class DayState(SQLModel, table=True):
    day: date = Field(primary_key=True)
    light: bool = False  # you said it's a light day: the 20-minute rescue keeps the streak
    auto_light: bool = False  # Myelin found no room for the full hour, so the rescue counts
    energy: Optional[str] = None  # "low" | "ok" | "high"


class Interview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company: str
    role: str = ""
    on: date
    notes: str = ""


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
    skipped: bool = False
    bonus: bool = False  # extra credit: never needed for the streak
