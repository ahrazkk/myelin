"""Read-only summaries behind the Week and Progress tabs."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlmodel import Session, select

from .models import PlanItem
from .planner import WEEKDAYS, blocks_for, load_routine
from .streak import CYCLE_DAYS, completed_days

HEATMAP_WEEKS = 26  # about six months, oldest on the left


def _day_status(d: date, today: date, started_on: date, done: set[date]) -> str:
    if d < started_on:
        return "before"
    if d in done:
        return "done"
    if d == today:
        return "today"
    if d < today:
        return "missed"
    return "future"


def week_view(session: Session, started_on: date, today: date) -> dict:
    """Mon to Sun of the current week: what was planned, what got done, what's coming."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    done = completed_days(session, monday, sunday)

    stored: dict[date, list[PlanItem]] = {}
    for item in session.exec(
        select(PlanItem).where(PlanItem.day >= monday, PlanItem.day <= sunday).order_by(PlanItem.day, PlanItem.position)
    ):
        stored.setdefault(item.day, []).append(item)

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        if d in stored:
            blocks = [{"title": it.title, "detail": it.detail, "kind": it.kind, "minutes": it.minutes,
                       "done": it.done_at is not None} for it in stored[d]]
        else:
            # Not planned yet (future) or never opened (past): show what the routine asks for.
            blocks = [{"title": b["title"], "detail": b.get("detail", ""), "kind": b["kind"],
                       "minutes": b.get("minutes", 0), "done": False} for b in blocks_for(d)]
        days.append({
            "date": d.isoformat(),
            "weekday": WEEKDAYS[d.weekday()],
            "status": _day_status(d, today, started_on, done),
            "blocks": blocks,
        })
    return {"week_of": monday.isoformat(), "today": today.isoformat(), "days": days}


def _runs(done: set[date], start: date, end: date) -> tuple[int, int]:
    """(best run, current run) of consecutive completed days. Today in progress doesn't break the current run."""
    best = run = 0
    d = start
    while d <= end:
        run = run + 1 if d in done else 0
        best = max(best, run)
        d += timedelta(days=1)
    cursor = end if end in done else end - timedelta(days=1)
    current = 0
    while cursor >= start and cursor in done:
        current += 1
        cursor -= timedelta(days=1)
    return best, current


def progress_view(session: Session, started_on: date, today: date) -> dict:
    done = completed_days(session, started_on, today)
    best, current = _runs(done, started_on, today)

    # Heatmap: whole weeks (Mon to Sun), ending with this week.
    this_monday = today - timedelta(days=today.weekday())
    first_monday = max(this_monday - timedelta(weeks=HEATMAP_WEEKS - 1),
                       started_on - timedelta(days=started_on.weekday()))
    weeks = []
    monday = first_monday
    while monday <= this_monday:
        weeks.append([
            {"date": (monday + timedelta(days=i)).isoformat(),
             "status": _day_status(monday + timedelta(days=i), today, started_on, done)}
            for i in range(7)
        ])
        monday += timedelta(weeks=1)

    # Repetitions per habit: every completed block is one more rep toward automaticity.
    all_reps = Counter()
    week_reps = Counter()
    for item in session.exec(select(PlanItem).where(PlanItem.done_at != None)):  # noqa: E711
        all_reps[item.track] += 1
        if item.day >= this_monday:
            week_reps[item.track] += 1

    routine = load_routine()
    planned_per_week = Counter(b["track"] for i in range(7) for b in blocks_for(this_monday + timedelta(days=i)))
    habits = [
        {"track": key, "name": meta["name"], "kind": meta["kind"], "reps": all_reps[key],
         "this_week": week_reps[key], "per_week": planned_per_week[key], "target": CYCLE_DAYS}
        for key, meta in routine["tracks"].items()
        if planned_per_week[key] or all_reps[key]
    ]

    return {
        "started_on": started_on.isoformat(),
        "today": today.isoformat(),
        "current": current,
        "best": best,
        "days_done": len(done),
        "days_since_start": (today - started_on).days + 1,
        "weeks": weeks,
        "habits": habits,
    }
