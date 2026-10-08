"""Turns settings, prayer times, work hours, calendars and quick commands into today's timed plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from .calendar_sync import CalendarCache
from .models import BusyBlock, DayState, Interview, PlanItem, UserSettings
from .planner import WEEKDAYS
from .prayer import PRAYERS, prayer_day
from .scheduler import Block, Interval, Placement, plan_day, subtract

DEFAULT_FAJR = (5, 30)
DEFAULT_ISHA = (20, 30)
PREP_WINDOW_DAYS = 14
MOCK_WINDOW_DAYS = 3


@dataclass
class BuiltDay:
    placements: dict[int, Placement]
    light: bool
    auto_light: bool
    energy: Optional[str]
    busy: list[dict] = field(default_factory=list)
    calendar_errors: list[str] = field(default_factory=list)
    window: Optional[tuple[datetime, datetime]] = None


def _hhmm(day_start: datetime, value: str) -> datetime:
    h, m = (int(x) for x in value.split(":"))
    return day_start.replace(hour=h, minute=m)


def day_state(session: Session, day: date) -> DayState:
    state = session.get(DayState, day)
    if state is None:
        state = DayState(day=day)
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def ensure_extra_blocks(session: Session, day: date, state: DayState) -> None:
    """Interview prep when an interview is close, and a stretch block on high-energy days."""
    existing = {i.track for i in session.exec(select(PlanItem).where(PlanItem.day == day))}
    position = len(existing) + 10
    upcoming = session.exec(
        select(Interview).where(Interview.on >= day, Interview.on <= day + timedelta(days=PREP_WINDOW_DAYS))
    )
    for iv in upcoming:
        track = f"interview:{iv.id}"
        if track in existing:
            continue
        days_left = (iv.on - day).days
        if days_left <= MOCK_WINDOW_DAYS:
            title, detail, minutes = (f"Mock interview for {iv.company}",
                                      "Out loud: 1 coding problem, 1 system design, 2 STAR stories", 45)
        else:
            title, detail, minutes = (f"Prep for {iv.company}",
                                      "Research the company, then rehearse one STAR story", 20)
        session.add(PlanItem(day=day, position=position, track=track, kind="interview", title=title,
                             detail=detail, minutes=minutes, bonus=True))
        position += 1
    if state.energy == "high" and "stretch" not in existing:
        session.add(PlanItem(day=day, position=position, track="stretch", kind="interview", title="Stretch block",
                             detail="One harder problem in your weakest pattern", minutes=45, bonus=True))
    session.commit()


def build_day(
    session: Session,
    settings: UserSettings,
    now: datetime,
    items: list[PlanItem],
    calendars: Optional[CalendarCache] = None,
) -> BuiltDay:
    tz = now.tzinfo
    day = now.date()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = midnight + timedelta(hours=23, minutes=59)
    state = day_state(session, day)
    buffer = timedelta(minutes=settings.prayer_buffer_minutes)

    busy: list[Interval] = []
    shown: list[dict] = []

    def block(start: datetime, end: datetime, label: str, source: str, block_id: Optional[int] = None):
        busy.append(Interval(start, end, label))
        shown.append({"id": block_id, "start": start.isoformat(), "end": end.isoformat(),
                      "label": label, "source": source})

    # Prayer times frame the day.
    if settings.latitude is not None and settings.longitude is not None:
        times = prayer_day(day, settings.latitude, settings.longitude, tz, settings.calc_method,
                           settings.asr_method).times
        fajr, isha = times["fajr"], times["isha"]
        for name in PRAYERS:
            busy.append(Interval(times[name], times[name] + buffer, name.capitalize()))
    else:
        fajr = midnight.replace(hour=DEFAULT_FAJR[0], minute=DEFAULT_FAJR[1])
        isha = midnight.replace(hour=DEFAULT_ISHA[0], minute=DEFAULT_ISHA[1])
    day_end = min(isha + timedelta(minutes=settings.study_cutoff_after_isha), end_of_day)

    weekday = WEEKDAYS[day.weekday()]
    is_workday = weekday in settings.work_days.split(",")
    is_office = weekday in settings.office_days.split(",")
    work_start, work_end = _hhmm(midnight, settings.work_start), _hhmm(midnight, settings.work_end)
    commute = timedelta(minutes=settings.commute_minutes if is_office else 0)

    # The database hands times back in UTC; plan in local time (copies, so nothing is written back).
    manual = [
        BusyBlock(id=b.id, day=b.day, start=b.start.astimezone(tz), end=b.end.astimezone(tz), label=b.label,
                  kind=b.kind)
        for b in session.exec(select(BusyBlock).where(BusyBlock.day == day).order_by(BusyBlock.start))
    ]
    free_blocks = [Interval(b.start, b.end, b.label) for b in manual if b.kind == "free"]

    # When study can happen: after work on workdays, from your usual start time otherwise,
    # plus any free time you carved out ("free 12-1").
    if is_workday:
        open_windows = [Interval(work_end + commute, day_end)]
        for piece in subtract([Interval(work_start, work_end, "Work")], free_blocks):
            block(piece.start, piece.end, "Work", "work")
        if commute:
            block(work_start - commute, work_start, "Commute", "work")
            block(work_end, work_end + commute, "Commute", "work")
    else:
        open_windows = [Interval(work_start, day_end)]
    open_windows += free_blocks

    for b in manual:
        if b.kind == "busy":
            block(b.start, b.end, b.label, "you", b.id)
    for b in manual:
        if b.kind == "free":
            shown.append({"id": b.id, "start": b.start.isoformat(), "end": b.end.isoformat(),
                          "label": b.label, "source": "you", "free": True})

    calendar_errors: list[str] = []
    urls = [u.strip() for u in settings.calendar_urls.splitlines() if u.strip()]
    if urls and calendars is not None:
        events, calendar_errors = calendars.events_on(urls, day, tz)
        for ev in events:
            block(ev.start, ev.end, ev.title, "calendar")

    # Quran right after Fajr, before going back to sleep or leaving for work.
    faith_windows = [Interval(fajr + buffer, fajr + buffer + timedelta(hours=2))]

    blocks = [Block(i.id, i.track, i.kind, i.minutes, done=i.done_at is not None, skipped=i.skipped,
                    bonus=i.bonus) for i in items]
    light = state.light or state.energy == "low"
    # Did today ever have room for the full hour? Judge from the start of the day, so leaving it
    # late doesn't quietly turn into a light day; only real busyness (work, meetings) does.
    capacity = plan_day(blocks, open_windows, busy, midnight, faith_windows=faith_windows, light=light)
    auto_light = capacity.auto_light
    plan = plan_day(blocks, open_windows, busy, now, faith_windows=faith_windows, light=light or auto_light,
                    allow_auto_light=False)
    plan.auto_light = auto_light

    if state.auto_light != auto_light:
        state.auto_light = auto_light
        session.add(state)
        session.commit()

    shown.sort(key=lambda b: b["start"])
    return BuiltDay(
        placements=plan.placements,
        light=plan.light,
        auto_light=plan.auto_light,
        energy=state.energy,
        busy=shown,
        calendar_errors=calendar_errors,
        window=(fajr, day_end),
    )
