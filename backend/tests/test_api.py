from datetime import timedelta


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_today_without_location_asks_for_setup(client):
    body = client.get("/api/today").json()
    assert body["date"] == "2026-10-05"
    assert body["needs_setup"] is True
    assert body["prayers"] is None
    assert [i["track"] for i in body["plan"]] == ["quran", "gym", "leetcode_python", "leetcode_sql"]


def test_today_with_location_includes_prayers(client):
    client.put("/api/settings", json={"latitude": 21.4225, "longitude": 39.8262})
    body = client.get("/api/today").json()
    assert body["needs_setup"] is False
    assert [t["name"] for t in body["prayers"]["times"]] == ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
    assert body["prayers"]["next"]["name"] == "dhuhr"  # 10:00 in Makkah


def test_rejects_unknown_timezone(client):
    assert client.put("/api/settings", json={"timezone": "Mars/Olympus"}).status_code == 422


def test_streak_counts_completed_interview_days(client, clock):
    def finish_today():
        for item in client.get("/api/today").json()["plan"]:
            if item["counts_for_streak"] and not item["done"]:
                client.post(f"/api/plan/{item['id']}/toggle")

    first = client.get("/api/today").json()["streak"]
    assert first["current"] == 0 and first["cycle_day"] == 1

    finish_today()
    assert client.get("/api/today").json()["streak"]["current"] == 1

    clock.when += timedelta(days=1)
    nxt = client.get("/api/today").json()["streak"]
    assert nxt["current"] == 1  # today is still in progress, yesterday counts
    assert nxt["cycle"][0]["status"] == "done" and nxt["cycle"][1]["status"] == "today"

    finish_today()
    assert client.get("/api/today").json()["streak"]["current"] == 2


def test_quran_and_gym_do_not_gate_the_streak(client):
    plan = client.get("/api/today").json()["plan"]
    assert {i["track"]: i["counts_for_streak"] for i in plan} == {
        "quran": False, "gym": False, "leetcode_python": True, "leetcode_sql": True}


def test_toggle_unknown_item_is_404(client):
    assert client.post("/api/plan/999/toggle").status_code == 404
