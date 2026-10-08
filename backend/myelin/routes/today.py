from __future__ import annotations

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from .. import commands
from ..daybuild import build_day, day_state, ensure_extra_blocks
from ..deps import Ctx
from ..models import BusyBlock, Interview, Note, PlanItem
from ..planner import ensure_plan
from ..prayer import prayers_for
from ..scheduler import Placement
from ..streak import streak_summary
from ..views import progress_view, week_view
from .problems import due_problems

router = APIRouter(prefix="/api")


def item_json(item: PlanItem, placement: Optional[Placement] = None) -> dict:
    data = {
        "id": item.id,
        "track": item.track,
        "kind": item.kind,
        "title": item.title,
        "detail": item.detail,
        "minutes": item.minutes,
        "counts_for_streak": item.counts_for_streak,
        "done": item.done_at is not None,
        "done_at": item.done_at.isoformat() if item.done_at else None,
        "skipped": item.skipped,
        "bonus": item.bonus,
    }
    if placement is not None:
        data |= {
            "status": placement.status,
            "start": placement.start.isoformat() if placement.start else None,
            "end": placement.end.isoformat() if placement.end else None,
            "scheduled_minutes": placement.minutes,
            "optional": placement.optional,
        }
    return data


def prayers_or_none(ctx: Ctx):
    s = ctx.settings
    if s.latitude is None or s.longitude is None:
        return None
    return prayers_for(ctx.now, s.latitude, s.longitude, ctx.now.tzinfo, s.calc_method, s.asr_method)


def todays_items(ctx: Ctx) -> list[PlanItem]:
    ensure_plan(ctx.session, ctx.today)
    ensure_extra_blocks(ctx.session, ctx.today, day_state(ctx.session, ctx.today))
    return list(ctx.session.exec(select(PlanItem).where(PlanItem.day == ctx.today).order_by(PlanItem.position)))


@router.get("/today")
def today(ctx: Ctx = Depends()) -> dict:
    items = todays_items(ctx)
    built = build_day(ctx.session, ctx.settings, ctx.now, items, ctx.request.app.state.calendars)
    prayers = prayers_or_none(ctx)
    interviews = ctx.session.exec(
        select(Interview).where(Interview.on >= ctx.today).order_by(Interview.on)
    )
    return {
        "date": ctx.today.isoformat(),
        "now": ctx.now.isoformat(),
        "timezone": ctx.settings.timezone,
        "plan": [item_json(i, built.placements.get(i.id)) for i in items],
        "day": {
            "light": built.light,
            "auto_light": built.auto_light,
            "energy": built.energy,
            "busy": built.busy,
            "calendar_errors": built.calendar_errors,
            "ends_at": built.window[1].isoformat() if built.window else None,
        },
        "streak": streak_summary(ctx.session, ctx.settings.started_on, ctx.today),
        "prayers": prayers,
        "needs_setup": prayers is None,
        "interviews": [interview_json(iv, ctx) for iv in interviews],
        "resolves_due": [{"id": p.id, "title": p.title} for p in due_problems(ctx.session, ctx.today)],
    }


@router.get("/week")
def week(ctx: Ctx = Depends()) -> dict:
    ensure_plan(ctx.session, ctx.today)
    return week_view(ctx.session, ctx.settings.started_on, ctx.today)


@router.get("/progress")
def progress(ctx: Ctx = Depends()) -> dict:
    ensure_plan(ctx.session, ctx.today)
    return progress_view(ctx.session, ctx.settings.started_on, ctx.today)


@router.post("/plan/{item_id}/toggle")
def toggle(item_id: int, ctx: Ctx = Depends()) -> dict:
    item = ctx.session.get(PlanItem, item_id)
    if item is None:
        raise HTTPException(404, "No plan item with that id")
    item.done_at = None if item.done_at else ctx.now
    if item.done_at:
        item.skipped = False
    ctx.session.add(item)
    ctx.session.commit()
    ctx.session.refresh(item)
    return item_json(item)


@router.post("/plan/{item_id}/skip")
def skip(item_id: int, ctx: Ctx = Depends()) -> dict:
    item = ctx.session.get(PlanItem, item_id)
    if item is None:
        raise HTTPException(404, "No plan item with that id")
    item.skipped = not item.skipped
    ctx.session.add(item)
    ctx.session.commit()
    ctx.session.refresh(item)
    return item_json(item)


class DayPatch(BaseModel):
    light: Optional[bool] = None
    energy: Optional[Literal["low", "ok", "high"]] = None


@router.post("/day")
def update_day(body: DayPatch, ctx: Ctx = Depends()) -> dict:
    state = day_state(ctx.session, ctx.today)
    if body.light is not None:
        state.light = body.light
    if body.energy is not None:
        state.energy = body.energy
    ctx.session.add(state)
    ctx.session.commit()
    return {"light": state.light, "energy": state.energy}


@router.delete("/busy/{block_id}")
def remove_busy(block_id: int, ctx: Ctx = Depends()) -> dict:
    b = ctx.session.get(BusyBlock, block_id)
    if b is None:
        raise HTTPException(404, "No busy block with that id")
    ctx.session.delete(b)
    ctx.session.commit()
    return {"ok": True}


# ---------- Interviews ----------

def interview_json(iv: Interview, ctx: Ctx) -> dict:
    return {"id": iv.id, "company": iv.company, "role": iv.role, "on": iv.on.isoformat(),
            "days_left": (iv.on - ctx.today).days, "notes": iv.notes}


class InterviewIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=120)
    on: str  # YYYY-MM-DD
    notes: str = Field(default="", max_length=2000)


@router.get("/interviews")
def list_interviews(ctx: Ctx = Depends()) -> list[dict]:
    return [interview_json(iv, ctx) for iv in ctx.session.exec(select(Interview).order_by(Interview.on))]


@router.post("/interviews")
def add_interview(body: InterviewIn, ctx: Ctx = Depends()) -> dict:
    try:
        on = commands.parse_date(body.on, ctx.today)
    except commands.CommandError as e:
        raise HTTPException(422, str(e))
    iv = Interview(company=body.company.strip(), role=body.role.strip(), on=on, notes=body.notes)
    ctx.session.add(iv)
    ctx.session.commit()
    ctx.session.refresh(iv)
    return interview_json(iv, ctx)


@router.delete("/interviews/{iv_id}")
def delete_interview(iv_id: int, ctx: Ctx = Depends()) -> dict:
    iv = ctx.session.get(Interview, iv_id)
    if iv is None:
        raise HTTPException(404, "No interview with that id")
    for item in ctx.session.exec(select(PlanItem).where(PlanItem.track == f"interview:{iv_id}",
                                                         PlanItem.done_at == None)):  # noqa: E711
        ctx.session.delete(item)
    ctx.session.delete(iv)
    ctx.session.commit()
    return {"ok": True}


# ---------- Quick commands ----------

class CommandIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


def _fmt(dt) -> str:
    """3 pm, 4:30 pm (portable: Windows strftime has no %-I)."""
    hour = dt.hour % 12 or 12
    suffix = "am" if dt.hour < 12 else "pm"
    return f"{hour} {suffix}" if dt.minute == 0 else f"{hour}:{dt.minute:02d} {suffix}"


def _match_items(items: list[PlanItem], target: str) -> list[PlanItem]:
    t = target.strip().lower()
    aliases = {"leetcode": "leetcode", "python": "leetcode_python", "sql": "leetcode_sql",
               "design": "system_design", "system design": "system_design", "quran": "quran", "gym": "gym",
               "resume": "resume", "reading": "new_skill", "skill": "new_skill", "new skill": "new_skill"}
    key = aliases.get(t)
    return [i for i in items if (key and key in i.track) or t in i.title.lower()]


@router.post("/command")
def run_command(body: CommandIn, ctx: Ctx = Depends()) -> dict:
    try:
        cmd = commands.parse(body.text, ctx.now)
    except commands.CommandError as e:
        raise HTTPException(422, str(e))

    s = ctx.session
    state = day_state(s, ctx.today)
    message = ""

    if cmd.kind in ("busy", "free"):
        if cmd.end <= ctx.now and cmd.kind == "busy" and cmd.start == ctx.now:
            raise HTTPException(422, "That time has already passed today.")
        s.add(BusyBlock(day=ctx.today, start=cmd.start, end=cmd.end, label=cmd.label, kind=cmd.kind))
        span = f"until {_fmt(cmd.end)}" if cmd.start == ctx.now else f"{_fmt(cmd.start)} to {_fmt(cmd.end)}"
        message = (f"Got it: free {span}. I'll use that time." if cmd.kind == "free"
                   else f"Got it: {cmd.label.lower() if cmd.label != 'Busy' else 'busy'} {span}. Your day is reshuffled.")
    elif cmd.kind == "light":
        state.light = True
        message = "Light day. The first interview block is now a 20-minute rescue, and that keeps your streak."
    elif cmd.kind == "normal":
        state.light = False
        message = "Back to a normal day: the full interview hour."
    elif cmd.kind == "energy":
        state.energy = cmd.value
        message = {"low": "Low energy noted. Today is a light day: 20 minutes keeps the streak.",
                   "ok": "Energy noted. Normal day.",
                   "high": "High energy. I added a stretch block if you want it."}[cmd.value]
    elif cmd.kind in ("skip", "unskip"):
        items = [i for i in todays_items(ctx) if i.done_at is None]
        matches = _match_items(items, cmd.target)
        if not matches:
            raise HTTPException(422, f'Nothing on today\'s plan matches "{cmd.target}".')
        for i in matches:
            i.skipped = cmd.kind == "skip"
            s.add(i)
        names = ", ".join(i.title for i in matches)
        message = f"Skipped {names} today." if cmd.kind == "skip" else f"{names} is back on the plan."
    elif cmd.kind == "clear":
        for b in s.exec(select(BusyBlock).where(BusyBlock.day == ctx.today)):
            s.delete(b)
        state.light = False
        message = "Cleared everything you told me about today."
    elif cmd.kind == "note":
        s.add(Note(text=cmd.value, created_at=ctx.now))
        message = "Parked in your brain dump."
    elif cmd.kind == "interview":
        iv = Interview(company=cmd.label, on=cmd.on)
        s.add(iv)
        days = (cmd.on - ctx.today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
        message = f"Interview with {cmd.label} {when}. Prep blocks start showing up two weeks out."
    elif cmd.kind == "focus":
        from .focus import FocusStart, focus_start  # local import: avoids a cycle

        items = todays_items(ctx)
        built = build_day(s, ctx.settings, ctx.now, items, ctx.request.app.state.calendars)
        upcoming = [i for i in items if i.done_at is None and not i.skipped
                    and built.placements.get(i.id) and built.placements[i.id].status == "scheduled"]
        upcoming.sort(key=lambda i: built.placements[i.id].start)
        target = upcoming[0] if upcoming else None
        minutes = cmd.minutes or (built.placements[target.id].minutes if target else 25)
        focus_start(FocusStart(plan_item_id=target.id if target else None, minutes=minutes), ctx)
        message = f"Focus started: {target.title if target else 'Focus'}, {minutes} minutes."

    s.add(state)
    s.commit()
    return {"ok": True, "kind": cmd.kind, "message": message}
