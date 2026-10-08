"""Focus timer and brain dump."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from ..deps import Ctx
from ..models import FocusSession, Note, PlanItem

router = APIRouter(prefix="/api")


def session_json(f: FocusSession) -> dict:
    ends_at = f.started_at + timedelta(minutes=f.planned_minutes)
    return {
        "id": f.id,
        "label": f.label,
        "plan_item_id": f.plan_item_id,
        "started_at": f.started_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "planned_minutes": f.planned_minutes,
        "ended_at": f.ended_at.isoformat() if f.ended_at else None,
        "completed": f.completed,
    }


def _minutes(f: FocusSession, now: datetime) -> int:
    end = f.ended_at or now
    return max(0, round((end - f.started_at).total_seconds() / 60))


def _day_bounds(ctx: Ctx) -> tuple[datetime, datetime]:
    start = ctx.now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def active_session(ctx: Ctx) -> Optional[FocusSession]:
    return ctx.session.exec(select(FocusSession).where(FocusSession.ended_at == None)).first()  # noqa: E711


@router.get("/focus")
def focus_state(ctx: Ctx = Depends()) -> dict:
    start, end = _day_bounds(ctx)
    today = list(ctx.session.exec(
        select(FocusSession).where(FocusSession.started_at >= start, FocusSession.started_at < end)
        .order_by(FocusSession.started_at)
    ))
    active = active_session(ctx)
    return {
        "active": session_json(active) if active else None,
        "today_minutes": sum(_minutes(f, ctx.now) for f in today),
        "sessions": [session_json(f) | {"minutes": _minutes(f, ctx.now)} for f in today],
    }


class FocusStart(BaseModel):
    plan_item_id: Optional[int] = None
    label: Optional[str] = Field(default=None, max_length=200)
    minutes: int = Field(default=25, ge=1, le=240)


@router.post("/focus/start")
def focus_start(body: FocusStart, ctx: Ctx = Depends()) -> dict:
    current = active_session(ctx)
    if current:  # starting something new ends whatever was running
        current.ended_at = ctx.now
        ctx.session.add(current)
    label = body.label
    if body.plan_item_id is not None:
        item = ctx.session.get(PlanItem, body.plan_item_id)
        if item is None:
            raise HTTPException(404, "No plan item with that id")
        label = label or item.title
    f = FocusSession(plan_item_id=body.plan_item_id, label=label or "Focus", started_at=ctx.now,
                     planned_minutes=body.minutes)
    ctx.session.add(f)
    ctx.session.commit()
    ctx.session.refresh(f)
    return session_json(f)


class FocusStop(BaseModel):
    mark_done: bool = False


@router.post("/focus/stop")
def focus_stop(body: FocusStop, ctx: Ctx = Depends()) -> dict:
    f = active_session(ctx)
    if f is None:
        raise HTTPException(409, "No focus session is running")
    planned_end = f.started_at + timedelta(minutes=f.planned_minutes)
    f.ended_at = min(ctx.now, planned_end) if ctx.now >= planned_end else ctx.now
    f.completed = ctx.now >= planned_end
    if body.mark_done and f.plan_item_id is not None:
        item = ctx.session.get(PlanItem, f.plan_item_id)
        if item is not None and item.done_at is None:
            item.done_at = ctx.now
            ctx.session.add(item)
    ctx.session.add(f)
    ctx.session.commit()
    ctx.session.refresh(f)
    return session_json(f) | {"minutes": _minutes(f, ctx.now)}


# ---------- Brain dump ----------

def note_json(n: Note) -> dict:
    return {"id": n.id, "text": n.text, "created_at": n.created_at.isoformat(),
            "done": n.done_at is not None, "done_at": n.done_at.isoformat() if n.done_at else None}


@router.get("/notes")
def list_notes(ctx: Ctx = Depends()) -> dict:
    start, _ = _day_bounds(ctx)
    notes = ctx.session.exec(select(Note).order_by(Note.created_at.desc()))  # type: ignore[attr-defined]
    open_notes, cleared = [], []
    for n in notes:
        if n.done_at is None:
            open_notes.append(note_json(n))
        elif n.done_at >= start - timedelta(days=6):
            cleared.append(note_json(n))
    return {"open": open_notes, "cleared": cleared}


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/notes")
def add_note(body: NoteIn, ctx: Ctx = Depends()) -> dict:
    n = Note(text=body.text.strip(), created_at=ctx.now)
    ctx.session.add(n)
    ctx.session.commit()
    ctx.session.refresh(n)
    return note_json(n)


class NotePatch(BaseModel):
    done: Optional[bool] = None
    text: Optional[str] = Field(default=None, min_length=1, max_length=2000)


@router.patch("/notes/{note_id}")
def edit_note(note_id: int, body: NotePatch, ctx: Ctx = Depends()) -> dict:
    n = ctx.session.get(Note, note_id)
    if n is None:
        raise HTTPException(404, "No note with that id")
    if body.done is not None:
        n.done_at = ctx.now if body.done else None
    if body.text is not None:
        n.text = body.text.strip()
    ctx.session.add(n)
    ctx.session.commit()
    ctx.session.refresh(n)
    return note_json(n)


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, ctx: Ctx = Depends()) -> dict:
    n = ctx.session.get(Note, note_id)
    if n is None:
        raise HTTPException(404, "No note with that id")
    ctx.session.delete(n)
    ctx.session.commit()
    return {"ok": True}
