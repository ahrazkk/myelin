from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from .. import sqlplay
from ..deps import Ctx
from ..models import SqlSolve

router = APIRouter(prefix="/api/sql")


@router.get("/databases")
def databases() -> list[dict]:
    return [{"id": db, "description": desc, "tables": sqlplay.schema(db)} for db, desc in sqlplay.DATABASES.items()]


@router.get("/questions")
def questions(ctx: Ctx = Depends()) -> list[dict]:
    solved = {s.question_id: s for s in ctx.session.exec(select(SqlSolve))}
    return [
        {k: q[k] for k in ("id", "db", "title", "difficulty", "pattern", "prompt", "ordered")}
        | {"solved": q["id"] in solved}
        for q in sqlplay.questions()
    ]


class RunIn(BaseModel):
    db: str
    query: str = Field(max_length=20000)


@router.post("/run")
def run(body: RunIn) -> dict:
    try:
        return sqlplay.run(body.db, body.query)
    except sqlplay.SqlError as e:
        raise HTTPException(400, str(e))


class CheckIn(BaseModel):
    question_id: str
    query: str = Field(max_length=20000)


@router.post("/check")
def check(body: CheckIn, ctx: Ctx = Depends()) -> dict:
    try:
        result = sqlplay.check(body.question_id, body.query)
    except sqlplay.SqlError as e:
        raise HTTPException(400, str(e))
    if result["correct"]:
        solve = ctx.session.get(SqlSolve, body.question_id)
        if solve is None:
            ctx.session.add(SqlSolve(question_id=body.question_id, solved_at=ctx.now))
        else:
            solve.tries += 1
            ctx.session.add(solve)
        ctx.session.commit()
    return result


@router.get("/questions/{qid}/solution")
def solution(qid: str) -> dict:
    try:
        return {"solution": sqlplay.question(qid)["solution"]}
    except sqlplay.SqlError as e:
        raise HTTPException(404, str(e))
