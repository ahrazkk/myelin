from __future__ import annotations

import re
import secrets
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..deps import get_session, load_settings
from ..models import UserSettings

router = APIRouter(prefix="/api")

CALC_METHODS = {"NORTH_AMERICA", "MUSLIM_WORLD_LEAGUE", "EGYPTIAN", "KARACHI", "UMM_AL_QURA",
                "DUBAI", "MOON_SIGHTING_COMMITTEE", "KUWAIT", "QATAR", "SINGAPORE", "UOIF"}
ASR_METHODS = {"SHAFI", "HANAFI"}
THEMES = {"auto", "light", "dark", "system"}
TEXT_SIZES = {"normal", "large", "larger"}
BACKGROUNDS = {"plain", "weather", "neural"}
CURSOR_EFFECTS = {"off", "glow", "synapses"}
ACCENTS = {"myelin", "emerald", "amber", "rose"}
TEMPERATURE_UNITS = {"c", "f"}
WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class SettingsUpdate(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: Optional[str] = None
    calc_method: Optional[str] = None
    asr_method: Optional[str] = None
    theme: Optional[str] = None
    text_size: Optional[str] = None
    reduced_motion: Optional[bool] = None
    background: Optional[str] = None
    cursor_effect: Optional[str] = None
    accent: Optional[str] = None
    clock_24h: Optional[bool] = None
    show_seconds: Optional[bool] = None
    show_hijri: Optional[bool] = None
    show_weather: Optional[bool] = None
    temperature_unit: Optional[str] = None
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    work_days: Optional[str] = None
    office_days: Optional[str] = None
    commute_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    prayer_buffer_minutes: Optional[int] = Field(default=None, ge=0, le=60)
    study_cutoff_after_isha: Optional[int] = Field(default=None, ge=0, le=300)
    calendar_urls: Optional[str] = None
    phone_access: Optional[bool] = None
    windows_lockscreen: Optional[bool] = None
    notifications: Optional[bool] = None


def settings_json(s: UserSettings) -> dict:
    return {
        "latitude": s.latitude,
        "longitude": s.longitude,
        "timezone": s.timezone,
        "calc_method": s.calc_method,
        "asr_method": s.asr_method,
        "started_on": s.started_on.isoformat() if s.started_on else None,
        "has_location": s.latitude is not None and s.longitude is not None,
        "theme": s.theme,
        "text_size": s.text_size,
        "reduced_motion": s.reduced_motion,
        "background": s.background,
        "cursor_effect": s.cursor_effect,
        "accent": s.accent,
        "clock_24h": s.clock_24h,
        "show_seconds": s.show_seconds,
        "show_hijri": s.show_hijri,
        "show_weather": s.show_weather,
        "temperature_unit": s.temperature_unit,
        "work_start": s.work_start,
        "work_end": s.work_end,
        "work_days": s.work_days,
        "office_days": s.office_days,
        "commute_minutes": s.commute_minutes,
        "prayer_buffer_minutes": s.prayer_buffer_minutes,
        "study_cutoff_after_isha": s.study_cutoff_after_isha,
        "calendar_urls": s.calendar_urls,
        "phone_access": s.phone_access,
        "phone_key": s.phone_key,
        "windows_lockscreen": s.windows_lockscreen,
        "notifications": s.notifications,
    }


def _check(data: dict) -> None:
    def bad(msg: str):
        raise HTTPException(422, msg)

    if data.get("timezone"):
        try:
            ZoneInfo(data["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            bad(f"Unknown time zone: {data['timezone']}")
    if data.get("calc_method") and data["calc_method"] not in CALC_METHODS:
        bad(f"Unknown calculation method: {data['calc_method']}")
    if data.get("asr_method") and data["asr_method"] not in ASR_METHODS:
        bad(f"Unknown Asr method: {data['asr_method']}")
    if data.get("theme") and data["theme"] not in THEMES:
        bad(f"Theme must be one of {', '.join(sorted(THEMES))}")
    if data.get("text_size") and data["text_size"] not in TEXT_SIZES:
        bad(f"Text size must be one of {', '.join(sorted(TEXT_SIZES))}")
    for key, allowed, name in (("background", BACKGROUNDS, "Background"), ("cursor_effect", CURSOR_EFFECTS, "Cursor effect"),
                               ("accent", ACCENTS, "Accent"), ("temperature_unit", TEMPERATURE_UNITS, "Temperature unit")):
        if data.get(key) and data[key] not in allowed:
            bad(f"{name} must be one of {', '.join(sorted(allowed))}")
    for key in ("work_start", "work_end"):
        if data.get(key) and not HHMM.match(data[key]):
            bad(f"{key.replace('_', ' ').capitalize()} must look like 09:00")
    for key in ("work_days", "office_days"):
        if data.get(key) is not None:
            days = [d for d in data[key].split(",") if d]
            if any(d not in WEEKDAYS for d in days):
                bad(f"{key.replace('_', ' ').capitalize()} must be days like mon,tue,wed")
    if data.get("calendar_urls"):
        for line in data["calendar_urls"].splitlines():
            line = line.strip()
            if line and not re.match(r"^(https?|webcal)://", line):
                bad("Calendar links must start with https:// or webcal://")


@router.get("/settings")
def read_settings(session: Session = Depends(get_session)) -> dict:
    return settings_json(load_settings(session))


@router.put("/settings")
def update_settings(update: SettingsUpdate, session: Session = Depends(get_session)) -> dict:
    settings = load_settings(session)
    data = update.model_dump(exclude_unset=True)
    _check(data)
    for key, value in data.items():
        setattr(settings, key, value)
    if settings.phone_access and not settings.phone_key:
        settings.phone_key = secrets.token_urlsafe(9)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings_json(settings)


@router.post("/settings/phone-key")
def rotate_phone_key(session: Session = Depends(get_session)) -> dict:
    """Make a new key, so old phone links stop working."""
    settings = load_settings(session)
    settings.phone_key = secrets.token_urlsafe(9)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings_json(settings)
