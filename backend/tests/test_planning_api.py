"""The scheduler wired to the API. The test clock is Monday 5 Oct 2026, 10:00 in Makkah (Asia/Riyadh).

No location is set, so the day runs from a default Fajr (5:30) to a default Isha (20:30) + 90 minutes.
Monday is a work-from-home day: work 9 to 5, study after.
"""

from datetime import timedelta

from myelin.calendar_sync import CalendarCache


def plan_by_track(client):
    return {i["track"]: i for i in client.get("/api/today").json()["plan"]}


def test_blocks_get_times_after_work(client):
    plan = plan_by_track(client)
    assert plan["gym"]["status"] == "scheduled"
    assert plan["gym"]["start"].startswith("2026-10-05T17:")
    assert plan["leetcode_python"]["start"] == plan["gym"]["end"]  # prime window
    # Quran missed its morning window (it's 10 am), so it lands first after work.
    assert plan["quran"]["start"] == "2026-10-05T17:00:00+03:00"


def test_busy_command_reshuffles(client):
    r = client.post("/api/command", json={"text": "dentist 5-7"}).json()
    assert r["message"].startswith("Got it: dentist 5 pm to 7 pm")
    plan = plan_by_track(client)
    assert plan["quran"]["start"] == "2026-10-05T19:00:00+03:00"
    busy = client.get("/api/today").json()["day"]["busy"]
    assert any(b["label"] == "Dentist" and b["source"] == "you" for b in busy)


def test_free_time_at_work_gets_used(client):
    client.post("/api/command", json={"text": "free 12-1"})
    plan = plan_by_track(client)
    assert plan["quran"]["start"] == "2026-10-05T12:00:00+03:00"


def test_no_room_switches_to_a_light_day_and_rescue_keeps_the_streak(client):
    client.post("/api/command", json={"text": "busy 5-10"})  # evening gone
    day = client.get("/api/today").json()
    assert day["day"]["auto_light"] is True
    python = next(i for i in day["plan"] if i["track"] == "leetcode_python")
    client.post(f"/api/plan/{python['id']}/toggle")
    assert client.get("/api/today").json()["streak"]["today_complete"] is True


def test_leaving_it_late_is_not_a_light_day(client, clock):
    clock.when += timedelta(hours=12, minutes=10)  # 22:10, almost nothing left
    day = client.get("/api/today").json()
    assert day["day"]["auto_light"] is False and day["day"]["light"] is False


def test_light_day_and_energy(client):
    client.post("/api/command", json={"text": "light day"})
    day = client.get("/api/today").json()
    python = next(i for i in day["plan"] if i["track"] == "leetcode_python")
    sql = next(i for i in day["plan"] if i["track"] == "leetcode_sql")
    assert day["day"]["light"] and python["scheduled_minutes"] == 20 and sql["optional"]

    client.post("/api/command", json={"text": "normal day"})
    client.post("/api/command", json={"text": "energy high"})
    tracks = [i["track"] for i in client.get("/api/today").json()["plan"]]
    assert "stretch" in tracks


def test_skip_gym(client):
    r = client.post("/api/command", json={"text": "skip gym"}).json()
    assert r["message"] == "Skipped Gym today."
    assert plan_by_track(client)["gym"]["status"] == "skipped"
    client.post("/api/command", json={"text": "unskip gym"})
    assert plan_by_track(client)["gym"]["status"] == "scheduled"


def test_note_command_parks_a_thought(client):
    client.post("/api/command", json={"text": "note buy dates for iftar"})
    assert client.get("/api/notes").json()["open"][0]["text"] == "buy dates for iftar"


def test_focus_command_starts_the_next_block(client):
    r = client.post("/api/command", json={"text": "focus"}).json()
    assert r["message"] == "Focus started: Quran after Fajr, 15 minutes."
    assert client.get("/api/focus").json()["active"]["label"] == "Quran after Fajr"


def test_interview_mode_adds_prep_then_mock(client, clock):
    r = client.post("/api/command", json={"text": "interview Shopify oct 15"}).json()
    assert "in 10 days" in r["message"]
    titles = [i["title"] for i in client.get("/api/today").json()["plan"]]
    assert "Prep for Shopify" in titles
    assert client.get("/api/today").json()["interviews"][0]["days_left"] == 10

    clock.when += timedelta(days=8)  # 2 days out
    titles = [i["title"] for i in client.get("/api/today").json()["plan"]]
    assert "Mock interview for Shopify" in titles


def test_bad_command_explains(client):
    r = client.post("/api/command", json={"text": "make me a sandwich"})
    assert r.status_code == 422 and "Try" in r.json()["detail"]


def test_calendar_events_block_time(client):
    ics = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//t//EN
BEGIN:VEVENT
UID:a
DTSTART:20261005T140000Z
DTEND:20261005T160000Z
SUMMARY:Family dinner
END:VEVENT
END:VCALENDAR
"""
    client.app.state.calendars = CalendarCache(fetch=lambda url: ics)
    client.put("/api/settings", json={"calendar_urls": "https://calendar.google.com/calendar/ical/x/basic.ics"})
    day = client.get("/api/today").json()
    assert any(b["label"] == "Family dinner" and b["source"] == "calendar" for b in day["day"]["busy"])
    quran = next(i for i in day["plan"] if i["track"] == "quran")
    assert quran["start"] == "2026-10-05T19:00:00+03:00"  # 14:00-16:00 UTC is 17:00-19:00 in Makkah


def test_calendar_errors_are_reported_not_fatal(client):
    def boom(url):
        raise OSError("network down")

    client.app.state.calendars = CalendarCache(fetch=boom)
    client.put("/api/settings", json={"calendar_urls": "https://example.com/cal.ics"})
    day = client.get("/api/today").json()
    assert "network down" in day["day"]["calendar_errors"][0]
    assert day["plan"]
