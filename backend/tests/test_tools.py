from datetime import date, timedelta

import pytest

from myelin import sqlplay
from myelin.routes.problems import next_step, title_from_url


# ---------- Focus timer ----------

def test_focus_runs_and_marks_block_done(client, clock):
    item = client.get("/api/today").json()["plan"][2]  # LeetCode Python on Monday
    started = client.post("/api/focus/start", json={"plan_item_id": item["id"], "minutes": 30}).json()
    assert started["label"] == "LeetCode Python"
    assert client.get("/api/focus").json()["active"]["id"] == started["id"]

    clock.when += timedelta(minutes=31)
    stopped = client.post("/api/focus/stop", json={"mark_done": True}).json()
    assert stopped["completed"] is True and stopped["minutes"] == 30

    state = client.get("/api/focus").json()
    assert state["active"] is None and state["today_minutes"] == 30
    done = {i["id"]: i["done"] for i in client.get("/api/today").json()["plan"]}
    assert done[item["id"]] is True


def test_starting_a_new_focus_ends_the_old_one(client, clock):
    client.post("/api/focus/start", json={"label": "Reading", "minutes": 25})
    clock.when += timedelta(minutes=10)
    client.post("/api/focus/start", json={"label": "SQL", "minutes": 25})
    sessions = client.get("/api/focus").json()["sessions"]
    assert [s["label"] for s in sessions] == ["Reading", "SQL"]
    assert sessions[0]["minutes"] == 10 and sessions[0]["completed"] is False


def test_stop_without_a_session_is_409(client):
    assert client.post("/api/focus/stop", json={}).status_code == 409


# ---------- Brain dump ----------

def test_notes_park_clear_and_delete(client):
    n = client.post("/api/notes", json={"text": "  email recruiter back  "}).json()
    assert n["text"] == "email recruiter back"
    assert len(client.get("/api/notes").json()["open"]) == 1
    client.patch(f"/api/notes/{n['id']}", json={"done": True})
    notes = client.get("/api/notes").json()
    assert notes["open"] == [] and notes["cleared"][0]["id"] == n["id"]
    assert client.delete(f"/api/notes/{n['id']}").json()["ok"] is True
    assert client.get("/api/notes").json()["cleared"] == []


# ---------- LeetCode log ----------

def test_ladder_goes_3_7_21_60_then_mastered():
    d = date(2026, 10, 5)
    stage, due = next_step(0, "solved", d)
    gaps = [(due - d).days]
    for _ in range(3):
        stage, due = next_step(stage, "solved", d)
        gaps.append((due - d).days)
    assert gaps == [3, 7, 21, 60]
    assert next_step(stage, "solved", d) == (4, None)


def test_stuck_restarts_tomorrow_and_hint_steps_back():
    d = date(2026, 10, 5)
    assert next_step(3, "stuck", d) == (0, d + timedelta(days=1))
    assert next_step(3, "hint", d) == (2, d + timedelta(days=2))


def test_title_from_leetcode_url():
    assert title_from_url("https://leetcode.com/problems/two-sum/") == "Two Sum"
    assert title_from_url("https://neetcode.io/problems/valid-anagram") == "Valid Anagram"


def test_logged_problem_comes_back_when_due(client, clock):
    p = client.post("/api/problems", json={"url": "https://leetcode.com/problems/two-sum/",
                                           "pattern": "Arrays & hashing", "difficulty": "easy",
                                           "outcome": "solved", "minutes": 12}).json()
    assert p["title"] == "Two Sum" and p["due_on"] == "2026-10-08"
    assert client.get("/api/problems").json()["due"] == []

    clock.when += timedelta(days=3)
    due = client.get("/api/problems").json()["due"]
    assert [d["title"] for d in due] == ["Two Sum"]

    again = client.post(f"/api/problems/{p['id']}/attempts", json={"outcome": "solved", "minutes": 6}).json()
    assert again["due_on"] == "2026-10-15" and again["attempts"] == 2


def test_logging_the_same_link_twice_adds_an_attempt(client):
    body = {"url": "https://leetcode.com/problems/two-sum/", "outcome": "stuck"}
    first = client.post("/api/problems", json=body).json()
    second = client.post("/api/problems", json=body | {"outcome": "solved"}).json()
    assert first["id"] == second["id"] and second["attempts"] == 2 and second["was_new"] is False


def test_problem_needs_a_name_or_link(client):
    assert client.post("/api/problems", json={"outcome": "solved"}).status_code == 422


def test_suggests_weakest_pattern(client):
    for outcome in ("stuck", "hint", "stuck"):
        client.post("/api/problems", json={"title": f"Window {outcome}", "pattern": "Sliding window",
                                           "outcome": outcome})
    client.post("/api/problems", json={"title": "Pair", "pattern": "Two pointers", "outcome": "solved"})
    nxt = client.get("/api/problems").json()["stats"]["next"]["python"]
    assert nxt == {"pattern": "Sliding window", "why": "your lowest solve rate"}


# ---------- SQL playground ----------

@pytest.mark.parametrize("q", sqlplay.questions(), ids=lambda q: q["id"])
def test_every_reference_answer_runs_and_checks_correct(q):
    result = sqlplay.run(q["db"], q["solution"])
    assert result["rows"], "reference answer returned no rows"
    assert sqlplay.check(q["id"], q["solution"])["correct"] is True


def test_known_answers():
    assert sqlplay.run("company", sqlplay.question("company-second-salary")["solution"])["rows"] == [[171000]]
    names = {r[0] for r in sqlplay.run("activity", sqlplay.question("activity-streaks")["solution"])["rows"]}
    assert names == {"Ali", "Cam", "Eli"}
    retention = sqlplay.run("activity", sqlplay.question("activity-next-day-retention")["solution"])["rows"]
    assert retention == [[0.5]]


def test_check_explains_wrong_answers():
    wrong_order = "SELECT strftime('%Y-%m', ordered_on) AS m, COUNT(*) FROM orders GROUP BY m ORDER BY m DESC"
    assert "order" in sqlplay.check("shop-monthly-orders", wrong_order)["message"].lower()
    too_many = "SELECT name FROM customers"
    assert sqlplay.check("shop-never-ordered", too_many)["message"].startswith("Expected 2 row")


def test_playground_blocks_files_and_runaway_queries():
    with pytest.raises(sqlplay.SqlError, match="ATTACH"):
        sqlplay.run("shop", "ATTACH DATABASE 'x.db' AS x")
    with pytest.raises(sqlplay.SqlError, match="seconds"):
        sqlplay.run("shop", "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT COUNT(*) FROM n")


def test_writes_never_persist():
    sqlplay.run("shop", "DELETE FROM customers")
    assert sqlplay.run("shop", "SELECT COUNT(*) FROM customers")["rows"] == [[9]]


def test_sql_api_records_solves(client):
    qs = client.get("/api/sql/questions").json()
    assert len(qs) == len(sqlplay.questions()) and not any(q["solved"] for q in qs)
    assert "solution" not in qs[0]
    ok = client.post("/api/sql/check", json={
        "question_id": "company-second-salary",
        "query": "SELECT DISTINCT salary FROM employees ORDER BY salary DESC LIMIT 1 OFFSET 1"}).json()
    assert ok["correct"] is True
    solved = {q["id"] for q in client.get("/api/sql/questions").json() if q["solved"]}
    assert solved == {"company-second-salary"}
    assert client.post("/api/sql/run", json={"db": "shop", "query": "SELEC 1"}).status_code == 400


# ---------- Opening links ----------

def test_open_only_web_links(client):
    opened = []
    client.app.state.open_url = opened.append
    assert client.post("/api/open", json={"url": "https://leetcode.com/problems/two-sum/"}).json()["ok"]
    assert client.post("/api/open", json={"url": "file:///C:/Windows/system32"}).status_code == 422
    assert opened == ["https://leetcode.com/problems/two-sum/"]
