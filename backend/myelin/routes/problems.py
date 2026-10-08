"""LeetCode log and the spaced re-solve queue.

Re-solving a problem after a gap is retrieval practice, spaced. Each clean solve pushes the next
re-solve further out: +3, +7, +21, then +60 days. A hint pulls it back a step; getting stuck
restarts the ladder tomorrow.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..deps import Ctx
from ..models import Attempt, Problem

router = APIRouter(prefix="/api")

LADDER = (3, 7, 21, 60)

# NeetCode roadmap order, so "what next" follows a sensible learning path.
PATTERNS = {
    "python": [
        "Arrays & hashing", "Two pointers", "Sliding window", "Stack", "Binary search", "Linked list",
        "Trees", "Tries", "Heap / priority queue", "Backtracking", "Graphs", "Advanced graphs",
        "1-D dynamic programming", "2-D dynamic programming", "Greedy", "Intervals", "Math & geometry",
        "Bit manipulation",
    ],
    "sql": [
        "Select & filter", "Joins", "Aggregation & GROUP BY", "Subqueries", "CTEs", "Window functions",
        "Self joins", "Dates", "Gaps & islands",
    ],
}

Outcome = Literal["solved", "hint", "stuck"]


def next_step(stage: int, outcome: str, day: date) -> tuple[int, Optional[date]]:
    """New (stage, due date) after an attempt. Due date None means mastered."""
    if outcome == "solved":
        if stage >= len(LADDER):
            return stage, None
        return stage + 1, day + timedelta(days=LADDER[stage])
    if outcome == "hint":
        return max(stage - 1, 0), day + timedelta(days=2)
    return 0, day + timedelta(days=1)


def title_from_url(url: str) -> Optional[str]:
    """'https://leetcode.com/problems/two-sum/' -> 'Two Sum'."""
    m = re.search(r"/problems/([a-z0-9-]+)", url)
    if not m:
        return None
    return " ".join(w.capitalize() for w in m.group(1).split("-"))


def problem_json(p: Problem, attempts: list[Attempt], today: date) -> dict:
    last = attempts[-1] if attempts else None
    return {
        "id": p.id,
        "title": p.title,
        "url": p.url,
        "track": p.track,
        "difficulty": p.difficulty,
        "pattern": p.pattern,
        "created_on": p.created_on.isoformat(),
        "stage": p.stage,
        "due_on": p.due_on.isoformat() if p.due_on else None,
        "is_due": p.due_on is not None and p.due_on <= today,
        "mastered": p.due_on is None,
        "attempts": len(attempts),
        "last_outcome": last.outcome if last else None,
        "last_minutes": last.minutes if last else None,
    }


def due_problems(session: Session, today: date) -> list[Problem]:
    return list(session.exec(
        select(Problem).where(Problem.due_on != None, Problem.due_on <= today).order_by(Problem.due_on)  # noqa: E711
    ))


def pattern_stats(problems: list[Problem], attempts: dict[int, list[Attempt]]) -> dict:
    per: dict[tuple[str, str], dict] = defaultdict(lambda: {"attempts": 0, "solved": 0, "minutes": 0, "problems": 0})
    for p in problems:
        if not p.pattern:
            continue
        s = per[(p.track, p.pattern)]
        s["problems"] += 1
        for a in attempts.get(p.id, []):
            s["attempts"] += 1
            s["solved"] += a.outcome == "solved"
            s["minutes"] += a.minutes

    rows = []
    for track, names in PATTERNS.items():
        for name in names:
            s = per.get((track, name))
            rows.append({
                "track": track,
                "pattern": name,
                "problems": s["problems"] if s else 0,
                "attempts": s["attempts"] if s else 0,
                "solve_rate": round(s["solved"] / s["attempts"], 2) if s and s["attempts"] else None,
                "avg_minutes": round(s["minutes"] / s["attempts"]) if s and s["attempts"] else None,
            })

    def suggest(track: str) -> Optional[dict]:
        mine = [r for r in rows if r["track"] == track]
        untried = [r for r in mine if r["attempts"] == 0]
        tried = [r for r in mine if r["attempts"] > 0]
        weakest = min(tried, key=lambda r: (r["solve_rate"], -(r["avg_minutes"] or 0)), default=None)
        if weakest and weakest["solve_rate"] is not None and weakest["solve_rate"] < 0.6:
            return {"pattern": weakest["pattern"], "why": "your lowest solve rate"}
        if untried:
            return {"pattern": untried[0]["pattern"], "why": "next on the roadmap"}
        if weakest:
            return {"pattern": weakest["pattern"], "why": "your lowest solve rate"}
        return None

    return {"patterns": rows, "next": {"python": suggest("python"), "sql": suggest("sql")}}


@router.get("/problems")
def list_problems(ctx: Ctx = Depends()) -> dict:
    problems = list(ctx.session.exec(select(Problem).order_by(Problem.created_on.desc(), Problem.id.desc())))  # type: ignore[attr-defined]
    by_problem: dict[int, list[Attempt]] = defaultdict(list)
    for a in ctx.session.exec(select(Attempt).order_by(Attempt.day, Attempt.id)):
        by_problem[a.problem_id].append(a)
    items = [problem_json(p, by_problem[p.id], ctx.today) for p in problems]
    return {
        "problems": items,
        "due": [i for i in items if i["is_due"]],
        "stats": pattern_stats(problems, by_problem),
        "pattern_names": PATTERNS,
        "ladder_days": list(LADDER),
    }


class ProblemIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    url: str = Field(default="", max_length=500)
    track: Literal["python", "sql"] = "python"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    pattern: str = Field(default="", max_length=60)
    outcome: Outcome = "solved"
    minutes: int = Field(default=0, ge=0, le=600)
    note: str = Field(default="", max_length=2000)


def _record(session: Session, p: Problem, outcome: str, minutes: int, note: str, day: date) -> None:
    session.add(Attempt(problem_id=p.id, day=day, outcome=outcome, minutes=minutes, note=note))
    p.stage, p.due_on = next_step(p.stage, outcome, day)
    session.add(p)


@router.post("/problems")
def log_problem(body: ProblemIn, ctx: Ctx = Depends()) -> dict:
    url = body.url.strip()
    title = (body.title or "").strip() or (title_from_url(url) if url else None)
    if not title:
        raise HTTPException(422, "Give the problem a name or paste its link")

    existing = None
    if url:
        existing = ctx.session.exec(select(Problem).where(Problem.url == url)).first()
    if existing is None:
        existing = ctx.session.exec(select(Problem).where(Problem.title == title)).first()

    p = existing or Problem(title=title, url=url, track=body.track, difficulty=body.difficulty,
                            pattern=body.pattern, created_on=ctx.today)
    if existing is None:
        ctx.session.add(p)
        ctx.session.flush()
    _record(ctx.session, p, body.outcome, body.minutes, body.note, ctx.today)
    ctx.session.commit()
    ctx.session.refresh(p)
    attempts = list(ctx.session.exec(select(Attempt).where(Attempt.problem_id == p.id).order_by(Attempt.id)))
    return problem_json(p, attempts, ctx.today) | {"was_new": existing is None}


class AttemptIn(BaseModel):
    outcome: Outcome
    minutes: int = Field(default=0, ge=0, le=600)
    note: str = Field(default="", max_length=2000)


@router.post("/problems/{problem_id}/attempts")
def add_attempt(problem_id: int, body: AttemptIn, ctx: Ctx = Depends()) -> dict:
    p = ctx.session.get(Problem, problem_id)
    if p is None:
        raise HTTPException(404, "No problem with that id")
    _record(ctx.session, p, body.outcome, body.minutes, body.note, ctx.today)
    ctx.session.commit()
    ctx.session.refresh(p)
    attempts = list(ctx.session.exec(select(Attempt).where(Attempt.problem_id == p.id).order_by(Attempt.id)))
    return problem_json(p, attempts, ctx.today)


@router.delete("/problems/{problem_id}")
def delete_problem(problem_id: int, ctx: Ctx = Depends()) -> dict:
    p = ctx.session.get(Problem, problem_id)
    if p is None:
        raise HTTPException(404, "No problem with that id")
    for a in ctx.session.exec(select(Attempt).where(Attempt.problem_id == problem_id)):
        ctx.session.delete(a)
    ctx.session.delete(p)
    ctx.session.commit()
    return {"ok": True}
