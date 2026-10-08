"""Fits the day's blocks into the time you actually have.

Pure functions, no database: easy to test, easy to explain. The approach is greedy:

1. Work out the day's open windows: the study window, minus work, commute, prayers, meetings and
   anything you said you're busy for, plus any free time you carved out of work hours.
2. Place blocks in priority order, each at the earliest gap it fits: Quran right after Fajr, gym
   next, then the interview blocks right after gym (the prime window), then bonus blocks.
3. If the interview hour won't fit, switch to a light day: the first interview block shrinks to a
   20-minute rescue and the rest become optional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

RESCUE_MINUTES = 20
MIN_GAP = timedelta(minutes=10)


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    label: str = ""

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class Block:
    id: int
    track: str
    kind: str  # "faith" | "interview" | "body"
    minutes: int
    done: bool = False
    skipped: bool = False
    bonus: bool = False


@dataclass
class Placement:
    status: str  # "done" | "scheduled" | "no_room" | "skipped"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    minutes: Optional[int] = None  # may be shortened to the rescue length
    optional: bool = False


@dataclass
class DayPlan:
    placements: dict[int, Placement] = field(default_factory=dict)
    light: bool = False
    auto_light: bool = False  # Myelin switched to a light day because the hour didn't fit
    free: list[Interval] = field(default_factory=list)


def subtract(windows: list[Interval], busy: list[Interval]) -> list[Interval]:
    """Windows minus busy intervals, keeping only gaps long enough to use."""
    result = sorted(windows, key=lambda w: w.start)
    for b in busy:
        nxt = []
        for w in result:
            if not w.overlaps(b):
                nxt.append(w)
                continue
            if w.start < b.start:
                nxt.append(Interval(w.start, b.start))
            if b.end < w.end:
                nxt.append(Interval(b.end, w.end))
        result = nxt
    return [w for w in result if w.end - w.start >= MIN_GAP]


def union(windows: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for w in sorted(windows, key=lambda w: w.start):
        if merged and w.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, w.end))
        else:
            merged.append(w)
    return merged


def _take(free: list[Interval], minutes: int, not_before: datetime) -> Optional[Interval]:
    """Earliest slot of `minutes` at or after `not_before`; removes it from `free`."""
    need = timedelta(minutes=minutes)
    for i, w in enumerate(free):
        start = max(w.start, not_before)
        if w.end - start >= need:
            slot = Interval(start, start + need)
            rest = []
            if w.start < start:
                rest.append(Interval(w.start, start))
            if slot.end < w.end:
                rest.append(Interval(slot.end, w.end))
            free[i : i + 1] = rest
            return slot
    return None


def plan_day(
    blocks: list[Block],
    open_windows: list[Interval],
    busy: list[Interval],
    now: datetime,
    *,
    faith_windows: Optional[list[Interval]] = None,
    light: bool = False,
    allow_auto_light: bool = True,
) -> DayPlan:
    """Place each block.

    `open_windows` are when study may happen; `faith_windows` are tried first for faith blocks
    (Quran right after Fajr, before you sleep again or leave for work); `busy` is everything blocked.
    """
    plan = DayPlan(light=light)
    free = subtract(union(open_windows), busy)
    faith_free = subtract(union(faith_windows or []), busy)

    todo: list[Block] = []
    for b in blocks:
        if b.done:
            plan.placements[b.id] = Placement("done")
        elif b.skipped:
            plan.placements[b.id] = Placement("skipped")
        else:
            todo.append(b)

    def attempt(light_mode: bool) -> tuple[dict[int, Placement], bool]:
        slots = [Interval(w.start, w.end) for w in free]
        faith_slots = [Interval(w.start, w.end) for w in faith_free]
        placed: dict[int, Placement] = {}
        interview_seen = False
        hour_fits = True

        order = sorted(todo, key=lambda b: (b.bonus, {"faith": 0, "body": 1, "interview": 2}.get(b.kind, 3)))
        gym_end: Optional[datetime] = None
        for b in order:
            minutes = b.minutes
            optional = b.bonus
            if light_mode and b.kind == "interview" and not b.bonus:
                if interview_seen:
                    optional = True  # light day: only the first block is needed
                else:
                    minutes = min(minutes, RESCUE_MINUTES)
                interview_seen = True

            earliest = now
            if b.kind == "interview" and gym_end is not None:
                earliest = max(now, gym_end)  # study right after gym, while primed

            slot = _take(faith_slots, minutes, now) if b.kind == "faith" else None
            slot = slot or _take(slots, minutes, earliest)
            if slot is None and b.kind == "interview" and gym_end is not None:
                slot = _take(slots, minutes, now)  # no room after gym: take any gap
            if slot is None:
                placed[b.id] = Placement("no_room", minutes=minutes, optional=optional)
                if b.kind == "interview" and not optional and not b.bonus:
                    hour_fits = False
                continue
            placed[b.id] = Placement("scheduled", slot.start, slot.end, minutes, optional)
            if b.kind == "body":
                gym_end = slot.end
        return placed, hour_fits

    placed, fits = attempt(light)
    if not fits and not light and allow_auto_light:
        placed, _ = attempt(True)
        plan.light = True
        plan.auto_light = True
    plan.placements.update(placed)
    plan.free = free
    return plan
