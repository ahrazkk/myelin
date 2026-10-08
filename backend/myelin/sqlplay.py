"""A safe, offline SQL playground.

Every query runs against a fresh in-memory copy of a small sample database, so nothing you run can
change your data or touch the disk. Queries are cut off after a couple of seconds.
"""

from __future__ import annotations

import json
import sqlite3
import time
from functools import lru_cache
from importlib import resources

DATABASES = {
    "company": "Company: departments, employees, projects and assignments",
    "shop": "Shop: customers, products, orders and order items",
    "activity": "Activity: users and their daily logins",
}
TIME_LIMIT_S = 2.0
MAX_ROWS = 500


class SqlError(Exception):
    pass


@lru_cache(maxsize=None)
def seed(db: str) -> str:
    if db not in DATABASES:
        raise SqlError(f"Unknown database: {db}")
    return resources.files("myelin").joinpath(f"sql_samples/{db}.sql").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def questions() -> list[dict]:
    return json.loads(resources.files("myelin").joinpath("sql_samples/questions.json").read_text(encoding="utf-8"))


def question(qid: str) -> dict:
    for q in questions():
        if q["id"] == qid:
            return q
    raise SqlError(f"Unknown question: {qid}")


def _deny_risky(action, *_):
    # Nothing may attach files, detach, or change settings. Everything else is a scratch copy.
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _connect(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(seed(db))
    conn.set_authorizer(_deny_risky)
    return conn


def run(db: str, query: str) -> dict:
    query = query.strip().rstrip(";").strip()
    if not query:
        raise SqlError("Write a query first.")
    conn = _connect(db)
    started = time.perf_counter()
    conn.set_progress_handler(lambda: 1 if time.perf_counter() - started > TIME_LIMIT_S else 0, 2000)
    try:
        cur = conn.execute(query)
        rows = cur.fetchmany(MAX_ROWS + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
    except sqlite3.Warning:
        raise SqlError("Run one statement at a time.")
    except sqlite3.Error as e:
        if "interrupted" in str(e):
            raise SqlError(f"That query ran longer than {TIME_LIMIT_S:.0f} seconds and was stopped.")
        if "not authorized" in str(e):
            raise SqlError("ATTACH, DETACH and PRAGMA aren't available in the playground.")
        raise SqlError(str(e))
    finally:
        conn.close()
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:MAX_ROWS]],
        "truncated": len(rows) > MAX_ROWS,
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }


def schema(db: str) -> list[dict]:
    conn = sqlite3.connect(":memory:")
    conn.executescript(seed(db))
    tables = []
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"):
        cols = [{"name": c[1], "type": c[2]} for c in conn.execute(f"PRAGMA table_info('{name}')")]
        count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        tables.append({"name": name, "columns": cols, "rows": count})
    conn.close()
    return tables


def _normal(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2)
    if isinstance(value, str):
        return value.strip()
    return value


def _rows(result: dict) -> list[tuple]:
    return [tuple(_normal(v) for v in row) for row in result["rows"]]


def check(qid: str, query: str) -> dict:
    """Compare the user's result with the reference answer. Column names don't matter."""
    q = question(qid)
    mine = run(q["db"], query)
    expected = run(q["db"], q["solution"])
    got, want = _rows(mine), _rows(expected)

    if len(mine["columns"]) != len(expected["columns"]):
        return {"correct": False, "result": mine,
                "message": f"Expected {len(expected['columns'])} column(s), got {len(mine['columns'])}."}
    if not q["ordered"]:
        got, want = sorted(got, key=repr), sorted(want, key=repr)
    if got == want:
        return {"correct": True, "result": mine, "message": "Correct."}
    if len(got) != len(want):
        return {"correct": False, "result": mine,
                "message": f"Expected {len(want)} row(s), got {len(got)}."}
    if q["ordered"] and sorted(got, key=repr) == sorted(want, key=repr):
        return {"correct": False, "result": mine, "message": "Right rows, wrong order. Check your ORDER BY."}
    return {"correct": False, "result": mine, "message": "Same number of rows, but some values differ."}
