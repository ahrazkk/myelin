from datetime import date

from myelin.planner import blocks_for


def titles(day: date) -> list[str]:
    return [b["track"] for b in blocks_for(day)]


def test_monday_has_quran_then_gym_then_python_and_sql():
    assert titles(date(2026, 10, 5)) == ["quran", "gym", "leetcode_python", "leetcode_sql"]


def test_tuesday_is_an_office_day_without_gym():
    assert titles(date(2026, 10, 6)) == ["quran", "leetcode_python", "system_design"]


def test_gym_days_are_mon_wed_fri_sat():
    week = [date(2026, 10, 5 + i) for i in range(7)]
    gym_days = [d.strftime("%a") for d in week if "gym" in titles(d)]
    assert gym_days == ["Mon", "Wed", "Fri", "Sat"]


def test_every_day_interleaves_two_interview_tracks():
    for i in range(7):
        interview = [b for b in blocks_for(date(2026, 10, 5 + i)) if b["kind"] == "interview"]
        assert len(interview) == 2
        assert interview[0]["track"] != interview[1]["track"]
