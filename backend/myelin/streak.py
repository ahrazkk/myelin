"""The master streak and the 66-day myelination cycle.

A day is complete when every block that counts toward the streak is done.
Phase 0 keeps the rules simple; freezes and the never-miss-twice rule arrive in Phase 1.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, select

from .models import PlanItem

CYCLE_DAYS = 66  # median days to automaticity (Lally et al., 2010)


def completed_days(session: Session, start: date, end: date) -> set[date]:
    rows = session.exec(
        select(PlanItem).where(PlanItem.day >= start, PlanItem.day <= end, PlanItem.counts_for_streak == True)  # noqa: E712
    )
    by_day: dict[date, list[PlanItem]] = defaultdict(list)
    for item in rows:
        by_day[item.day].append(item)
    return {d for d, items in by_day.items() if items and all(i.done_at for i in items)}


def streak_summary(session: Session, started_on: date, today: date) -> dict:
    done = completed_days(session, started_on, today)

    # Today still counts as "in progress", so the streak runs back from yesterday until today is done.
    cursor = today if today in done else today - timedelta(days=1)
    current = 0
    while cursor >= started_on and cursor in done:
        current += 1
        cursor -= timedelta(days=1)

    elapsed = (today - started_on).days
    cycle_start = started_on + timedelta(days=(elapsed // CYCLE_DAYS) * CYCLE_DAYS)
    cycle = []
    for i in range(CYCLE_DAYS):
        d = cycle_start + timedelta(days=i)
        if d in done:
            status = "done"
        elif d == today:
            status = "today"
        elif d < today:
            status = "missed"
        else:
            status = "future"
        cycle.append({"date": d.isoformat(), "status": status})

    return {
        "current": current,
        "today_complete": today in done,
        "cycle_number": elapsed // CYCLE_DAYS + 1,
        "cycle_day": elapsed % CYCLE_DAYS + 1,
        "cycle_length": CYCLE_DAYS,
        "cycle": cycle,
    }
