"""Builds each day's plan from the routine: anchors first, then gym, then the two rotation tracks."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from importlib import resources

from sqlmodel import Session, select

from .models import PlanItem

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@lru_cache(maxsize=1)
def load_routine() -> dict:
    text = resources.files("myelin").joinpath("defaults/routine.json").read_text(encoding="utf-8")
    return json.loads(text)


def blocks_for(day: date, routine: dict | None = None) -> list[dict]:
    """The blocks a given day should have, in order. Pure function: no database."""
    routine = routine or load_routine()
    tracks = routine["tracks"]
    weekday = WEEKDAYS[day.weekday()]

    blocks: list[dict] = []
    for block in routine.get("daily", []):
        blocks.append({**block, "kind": tracks[block["track"]]["kind"]})

    gym = routine.get("gym")
    if gym and weekday in gym["days"]:
        # Gym before study: a bout of exercise primes learning for the next block.
        blocks.append({"track": "gym", "title": gym["title"], "detail": gym["detail"],
                       "minutes": gym["minutes"], "kind": "body"})

    for block in routine["rotation"].get(weekday, []):
        blocks.append({**block, "kind": tracks[block["track"]]["kind"]})

    return blocks


def ensure_plan(session: Session, day: date) -> list[PlanItem]:
    """Return the plan for `day`, creating it from the routine the first time it is asked for."""
    items = list(session.exec(select(PlanItem).where(PlanItem.day == day).order_by(PlanItem.position)))
    if items:
        return items

    for position, block in enumerate(blocks_for(day)):
        session.add(PlanItem(
            day=day,
            position=position,
            track=block["track"],
            kind=block["kind"],
            title=block["title"],
            detail=block.get("detail", ""),
            minutes=block.get("minutes", 0),
            # The master streak tracks the daily interview hour.
            counts_for_streak=block["kind"] == "interview",
        ))
    session.commit()
    return list(session.exec(select(PlanItem).where(PlanItem.day == day).order_by(PlanItem.position)))
