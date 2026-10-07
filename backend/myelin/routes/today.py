from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Ctx, zone
from ..models import PlanItem
from ..planner import ensure_plan
from ..prayer import prayers_for
from ..streak import streak_summary
from ..views import progress_view, week_view

router = APIRouter(prefix="/api")


def item_json(item: PlanItem) -> dict:
    return {
        "id": item.id,
        "track": item.track,
        "kind": item.kind,
        "title": item.title,
        "detail": item.detail,
        "minutes": item.minutes,
        "counts_for_streak": item.counts_for_streak,
        "done": item.done_at is not None,
        "done_at": item.done_at.isoformat() if item.done_at else None,
    }


def prayers_or_none(ctx: Ctx):
    s = ctx.settings
    if s.latitude is None or s.longitude is None:
        return None
    return prayers_for(ctx.now, s.latitude, s.longitude, ctx.now.tzinfo, s.calc_method, s.asr_method)


@router.get("/today")
def today(ctx: Ctx = Depends()) -> dict:
    items = ensure_plan(ctx.session, ctx.today)
    prayers = prayers_or_none(ctx)
    return {
        "date": ctx.today.isoformat(),
        "now": ctx.now.isoformat(),
        "timezone": ctx.settings.timezone,
        "plan": [item_json(i) for i in items],
        "streak": streak_summary(ctx.session, ctx.settings.started_on, ctx.today),
        "prayers": prayers,
        "needs_setup": prayers is None,
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
    item.done_at = None if item.done_at else ctx.request.app.state.clock(zone(ctx.settings))
    ctx.session.add(item)
    ctx.session.commit()
    ctx.session.refresh(item)
    return item_json(item)
