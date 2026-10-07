"""Prayer times, calculated offline with the Adhan algorithm (adhanpy)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from adhanpy.calculation.CalculationMethod import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.Madhab import Madhab
from adhanpy.PrayerTimes import PrayerTimes

# Sunrise is shown for reference but is not a prayer.
NAMES = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")


@dataclass(frozen=True)
class PrayerDay:
    day: date
    times: dict[str, datetime]


def prayer_day(
    day: date,
    latitude: float,
    longitude: float,
    tz: ZoneInfo,
    calc_method: str = "NORTH_AMERICA",
    asr_method: str = "SHAFI",
) -> PrayerDay:
    params = CalculationParameters(method=CalculationMethod[calc_method])
    params.madhab = Madhab[asr_method]
    pt = PrayerTimes(
        (latitude, longitude),
        datetime(day.year, day.month, day.day),
        calculation_parameters=params,
        time_zone=tz,
    )
    return PrayerDay(day=day, times={name: getattr(pt, name) for name in NAMES})


def next_prayer(now: datetime, today: PrayerDay, tomorrow: PrayerDay) -> tuple[str, datetime]:
    """The next of the five prayers after `now`, rolling over to tomorrow's Fajr after Isha."""
    for name in PRAYERS:
        if today.times[name] > now:
            return name, today.times[name]
    return "fajr", tomorrow.times["fajr"]


def prayers_for(now: datetime, latitude: float, longitude: float, tz: ZoneInfo,
                calc_method: str, asr_method: str) -> dict:
    today = prayer_day(now.date(), latitude, longitude, tz, calc_method, asr_method)
    tomorrow = prayer_day(now.date() + timedelta(days=1), latitude, longitude, tz, calc_method, asr_method)
    name, at = next_prayer(now, today, tomorrow)
    return {
        "method": calc_method,
        "asr_method": asr_method,
        "times": [{"name": n, "at": today.times[n].isoformat()} for n in NAMES],
        "next": {"name": name, "at": at.isoformat()},
        "tomorrow_fajr": tomorrow.times["fajr"].isoformat(),
    }
