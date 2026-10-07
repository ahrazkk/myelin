from datetime import timedelta


def finish_today(client):
    for item in client.get("/api/today").json()["plan"]:
        if not item["done"]:
            client.post(f"/api/plan/{item['id']}/toggle")


def test_week_runs_monday_to_sunday_with_today_marked(client, clock):
    clock.when += timedelta(days=2)  # Wednesday 7 Oct
    body = client.get("/api/week").json()
    assert body["week_of"] == "2026-10-05"
    assert [d["weekday"] for d in body["days"]] == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    statuses = [d["status"] for d in body["days"]]
    # The cycle starts the first time Myelin is opened, which is Wednesday here.
    assert statuses == ["before", "before", "today", "future", "future", "future", "future"]


def test_week_shows_planned_blocks_for_future_days(client):
    days = {d["weekday"]: d for d in client.get("/api/week").json()["days"]}
    assert [b["title"] for b in days["sat"]["blocks"]][:2] == ["Quran after Fajr", "Gym"]
    assert "Gym" not in [b["title"] for b in days["thu"]["blocks"]]


def test_week_marks_finished_days_done(client):
    finish_today(client)
    monday = client.get("/api/week").json()["days"][0]
    assert monday["status"] == "done"
    assert all(b["done"] for b in monday["blocks"])


def test_progress_tracks_best_streak_and_reps(client, clock):
    for _ in range(3):
        finish_today(client)
        clock.when += timedelta(days=1)
    clock.when += timedelta(days=1)  # skip a day
    finish_today(client)

    body = client.get("/api/progress").json()
    assert body["best"] == 3
    assert body["current"] == 1
    assert body["days_done"] == 4
    reps = {h["track"]: h["reps"] for h in body["habits"]}
    assert reps["quran"] == 4  # Quran was finished every completed day
    assert reps["gym"] >= 2


def test_progress_heatmap_is_whole_weeks(client):
    weeks = client.get("/api/progress").json()["weeks"]
    assert all(len(w) == 7 for w in weeks)
    assert weeks[-1][0]["date"] == "2026-10-05"
