from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from myelin import commands
from myelin.calendar_sync import parse_events
from myelin.scheduler import Block, Interval, plan_day, subtract

TZ = ZoneInfo("America/Toronto")


def at(h, m=0, d=5):
    return datetime(2026, 10, d, h, m, tzinfo=TZ)


def standard_blocks():
    return [
        Block(1, "quran", "faith", 15),
        Block(2, "gym", "body", 60),
        Block(3, "leetcode_python", "interview", 30),
        Block(4, "leetcode_sql", "interview", 30),
    ]


# ---------- scheduler ----------

def test_subtract_cuts_busy_time_out():
    free = subtract([Interval(at(17), at(22))], [Interval(at(18), at(18, 30)), Interval(at(21, 55), at(23))])
    assert [(w.start, w.end) for w in free] == [(at(17), at(18)), (at(18, 30), at(21, 55))]


def test_quran_after_fajr_gym_then_study_in_the_prime_window():
    plan = plan_day(standard_blocks(), [Interval(at(17), at(22))], [], now=at(5),
                    faith_windows=[Interval(at(6, 20), at(8, 20))])
    p = plan.placements
    assert (p[1].start, p[1].end) == (at(6, 20), at(6, 35))  # Quran right after Fajr
    assert (p[2].start, p[2].end) == (at(17), at(18))  # gym after work
    assert p[3].start == at(18) and p[4].start == at(18, 30)  # study straight after gym
    assert not plan.light


def test_busy_time_pushes_blocks_later():
    plan = plan_day(standard_blocks(), [Interval(at(17), at(22))], [Interval(at(17), at(19), "Dentist")],
                    now=at(12), faith_windows=[Interval(at(6, 20), at(8, 20))])
    assert plan.placements[1].start == at(19)  # Quran missed its morning window: first thing after the dentist
    assert plan.placements[2].start == at(19, 15)  # then gym
    assert plan.placements[3].start == at(20, 15)  # then study, straight after gym


def test_no_room_for_the_hour_becomes_a_light_day():
    plan = plan_day(standard_blocks()[2:], [Interval(at(21), at(21, 35))], [], now=at(12))
    assert plan.light and plan.auto_light
    first, second = plan.placements[3], plan.placements[4]
    assert first.status == "scheduled" and first.minutes == 20
    assert second.optional


def test_done_and_skipped_blocks_take_no_time():
    blocks = standard_blocks()
    blocks[1].skipped = True
    blocks[2].done = True
    plan = plan_day(blocks, [Interval(at(17), at(22))], [], now=at(16))
    assert plan.placements[2].status == "skipped" and plan.placements[3].status == "done"
    assert plan.placements[4].start == at(17, 15)  # after Quran, which fell back to the evening


def test_past_time_is_never_scheduled():
    plan = plan_day(standard_blocks()[2:], [Interval(at(17), at(22))], [], now=at(19, 10))
    assert plan.placements[3].start == at(19, 10)


# ---------- quick commands ----------

NOW = at(13, 5)  # Monday 1:05 pm


@pytest.mark.parametrize("text, end", [
    ("busy till 3", at(15)),
    ("busy until 4:30pm", at(16, 30)),
    ("busy till 11", at(23)),  # 11 am has passed, so 11 pm
    ("busy to 15:15", at(15, 15)),
])
def test_busy_till(text, end):
    cmd = commands.parse(text, NOW)
    assert cmd.kind == "busy" and cmd.start == NOW and cmd.end == end


@pytest.mark.parametrize("text, start, end, label", [
    ("meeting 2-4", at(14), at(16), "Meeting"),
    ("busy from 2 to 3:30pm", at(14), at(15, 30), "Busy"),
    ("dentist 11-1pm", at(11), at(13), "Dentist"),
    ("call 10am-10:30", at(10), at(10, 30), "Call"),
])
def test_busy_ranges(text, start, end, label):
    cmd = commands.parse(text, NOW)
    assert (cmd.kind, cmd.start, cmd.end, cmd.label) == ("busy", start, end, label)


def test_free_time_at_work():
    cmd = commands.parse("free 12-1", NOW)
    assert (cmd.kind, cmd.start, cmd.end) == ("free", at(12), at(13))


@pytest.mark.parametrize("text, kind, extra", [
    ("light day", "light", {}),
    ("Normal day", "normal", {}),
    ("skip gym", "skip", {"target": "gym"}),
    ("unskip gym", "unskip", {"target": "gym"}),
    ("energy low", "energy", {"value": "low"}),
    ("i'm tired", "energy", {"value": "low"}),
    ("feeling great", "energy", {"value": "high"}),
    ("note Email the recruiter", "note", {"value": "Email the recruiter"}),
    ("focus 25", "focus", {"minutes": 25}),
    ("focus", "focus", {"minutes": None}),
    ("clear", "clear", {}),
])
def test_other_commands(text, kind, extra):
    cmd = commands.parse(text, NOW)
    assert cmd.kind == kind
    for k, v in extra.items():
        assert getattr(cmd, k) == v


@pytest.mark.parametrize("text, company, on", [
    ("interview Shopify oct 20", "Shopify", date(2026, 10, 20)),
    ("interview with Acme Corp friday", "Acme Corp", date(2026, 10, 9)),
    ("interview google next monday", "Google", date(2026, 10, 12)),
    ("interview stripe in 5 days", "Stripe", date(2026, 10, 10)),
    ("interview RBC 2026-11-03", "Rbc", date(2026, 11, 3)),
    ("interview Amazon jan 8", "Amazon", date(2027, 1, 8)),
])
def test_interview_dates(text, company, on):
    cmd = commands.parse(text, NOW)
    assert (cmd.kind, cmd.label, cmd.on) == ("interview", company, on)


@pytest.mark.parametrize("text", ["", "dance", "busy till banana", "interview Shopify"])
def test_unclear_commands_explain_themselves(text):
    with pytest.raises(commands.CommandError):
        commands.parse(text, NOW)


# ---------- calendars ----------

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:1
DTSTART:20261005T190000Z
DTEND:20261005T200000Z
SUMMARY:Team sync
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20261005
DTEND;VALUE=DATE:20261006
SUMMARY:Thanksgiving week
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART:20261005T220000Z
DTEND:20261005T230000Z
SUMMARY:Optional talk
TRANSP:TRANSPARENT
END:VEVENT
BEGIN:VEVENT
UID:4
DTSTART;TZID=America/Toronto:20260928T180000
DTEND;TZID=America/Toronto:20260928T190000
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:Weekly 1:1
END:VEVENT
END:VCALENDAR
"""


def test_calendar_events_become_busy_time():
    events = parse_events(ICS, at(0), at(0) + timedelta(days=1), TZ)
    assert [(e.title, e.start, e.end) for e in events] == [
        ("Team sync", at(15), at(16)),  # 19:00 UTC is 3 pm in Toronto
        ("Weekly 1:1", at(18), at(19)),  # recurring every Monday
    ]
