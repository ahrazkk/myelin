"""Read-only calendar sync through iCal links.

Google Calendar and Outlook both give every calendar a private iCal address. Pasting it into
Myelin is enough; no sign-in, no tokens. Events become busy time for the scheduler.
"""

from __future__ import annotations

import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

REFRESH_S = 15 * 60
TIMEOUT_S = 6


@dataclass
class Event:
    start: datetime
    end: datetime
    title: str


@dataclass
class _Entry:
    fetched: float = 0.0
    text: Optional[str] = None
    error: Optional[str] = None


def fetch_url(url: str) -> str:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    req = urllib.request.Request(url, headers={"User-Agent": "Myelin/0.2"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - user-provided iCal link
        return resp.read().decode("utf-8", errors="replace")


@dataclass
class CalendarCache:
    fetch: Callable[[str], str] = fetch_url
    _entries: dict[str, _Entry] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _get(self, url: str) -> _Entry:
        with self._lock:
            entry = self._entries.setdefault(url, _Entry())
        if time.monotonic() - entry.fetched < REFRESH_S and entry.fetched:
            return entry
        try:
            entry.text = self.fetch(url)
            entry.error = None
        except Exception as e:  # keep the last good copy if the network hiccups
            entry.error = f"{type(e).__name__}: {e}"
        entry.fetched = time.monotonic()
        return entry

    def events_on(self, urls: list[str], day: date, tz: ZoneInfo) -> tuple[list[Event], list[str]]:
        events: list[Event] = []
        errors: list[str] = []
        start = datetime(day.year, day.month, day.day, tzinfo=tz)
        end = start + timedelta(days=1)
        for url in urls:
            entry = self._get(url)
            if entry.error:
                errors.append(entry.error)
            if not entry.text:
                continue
            try:
                events.extend(parse_events(entry.text, start, end, tz))
            except Exception as e:
                errors.append(f"Couldn't read that calendar: {e}")
        return sorted(events, key=lambda e: e.start), errors


def parse_events(text: str, start: datetime, end: datetime, tz: ZoneInfo) -> list[Event]:
    cal = icalendar.Calendar.from_ical(text)
    out = []
    for ev in recurring_ical_events.of(cal).between(start, end):
        if str(ev.get("TRANSP", "")).upper() == "TRANSPARENT":
            continue  # marked "free" in the calendar
        s, e = ev.get("DTSTART"), ev.get("DTEND")
        if s is None:
            continue
        s = s.dt
        if not isinstance(s, datetime):
            continue  # all-day events don't block time
        e = e.dt if e is not None else s + timedelta(hours=1)
        s = s.astimezone(tz) if s.tzinfo else s.replace(tzinfo=tz)
        e = e.astimezone(tz) if e.tzinfo else e.replace(tzinfo=tz)
        out.append(Event(s, e, str(ev.get("SUMMARY", "Busy")) or "Busy"))
    return out
