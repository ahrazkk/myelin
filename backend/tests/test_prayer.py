from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from myelin.prayer import next_prayer, prayer_day

MAKKAH = (21.4225, 39.8262)
TZ = ZoneInfo("Asia/Riyadh")


def test_times_are_in_order():
    day = prayer_day(date(2026, 10, 7), *MAKKAH, TZ)
    order = [day.times[n] for n in ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")]
    assert order == sorted(order)


def test_hanafi_asr_is_later_than_standard():
    shafi = prayer_day(date(2026, 10, 7), *MAKKAH, TZ, asr_method="SHAFI")
    hanafi = prayer_day(date(2026, 10, 7), *MAKKAH, TZ, asr_method="HANAFI")
    assert hanafi.times["asr"] > shafi.times["asr"]


def test_next_prayer_rolls_over_to_tomorrows_fajr_after_isha():
    today = prayer_day(date(2026, 10, 7), *MAKKAH, TZ)
    tomorrow = prayer_day(date(2026, 10, 8), *MAKKAH, TZ)
    late = datetime(2026, 10, 7, 23, 30, tzinfo=TZ)
    assert next_prayer(late, today, tomorrow) == ("fajr", tomorrow.times["fajr"])


def test_next_prayer_skips_sunrise():
    today = prayer_day(date(2026, 10, 7), *MAKKAH, TZ)
    tomorrow = prayer_day(date(2026, 10, 8), *MAKKAH, TZ)
    just_after_fajr = today.times["fajr"] + timedelta(minutes=1)
    assert next_prayer(just_after_fajr, today, tomorrow)[0] == "dhuhr"
