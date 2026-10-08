"""Quick commands: tell Myelin about your day in a few words.

    busy till 3          meeting 2-4         free 12-1 (a slow afternoon at work)
    light day            normal day          skip gym / unskip gym
    energy low           note call the bank  interview Shopify oct 20
    focus 25             clear
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

HELP = ('Try "busy till 3", "meeting 2-4", "free 12-1", "light day", "skip gym", '
        '"energy low", "note …", "interview Shopify oct 20" or "focus 25".')


class CommandError(ValueError):
    pass


@dataclass
class Command:
    kind: str  # busy | free | light | normal | skip | unskip | energy | clear | note | interview | focus
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    label: str = ""
    target: str = ""
    value: str = ""
    on: Optional[date] = None
    minutes: Optional[int] = None


_TIME = re.compile(r"^(?:(noon)|(midnight)|(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?)$")
_TIME_PART = r"(?:noon|midnight|\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?)"


def _parts(token: str) -> tuple[int, int, Optional[str]]:
    m = _TIME.match(token.strip().lower())
    if not m:
        raise CommandError(f'"{token}" doesn\'t look like a time. {HELP}')
    if m.group(1):
        return 12, 0, "pm"
    if m.group(2):
        return 0, 0, "am"
    hour, minute = int(m.group(3)), int(m.group(4) or 0)
    if hour > 23 or minute > 59:
        raise CommandError(f'"{token}" isn\'t a real time.')
    meridiem = m.group(5).replace(".", "") if m.group(5) else None
    return hour, minute, meridiem


def _at(day: datetime, hour: int, minute: int) -> datetime:
    return day.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)


def _resolve(hour: int, minute: int, meridiem: Optional[str], now: datetime, *, future: bool) -> datetime:
    if meridiem == "am":
        return _at(now, 0 if hour == 12 else hour, minute)
    if meridiem == "pm":
        return _at(now, hour if hour == 12 else hour + 12, minute)
    if hour >= 13 or hour == 0:
        return _at(now, hour, minute)
    if future:
        # "till 3": the next 3 o'clock from now.
        for h in (hour, hour + 12 if hour != 12 else None):
            if h is not None and _at(now, h, minute) > now:
                return _at(now, h, minute)
        return _at(now, hour + 12 if hour != 12 else hour, minute)
    # A range start like "2-4": daytime reading. 1 to 7 means afternoon, 8 to 12 morning or noon.
    return _at(now, hour + 12 if 1 <= hour <= 7 else hour, minute)


def parse_time(token: str, now: datetime, *, future: bool = True) -> datetime:
    return _resolve(*_parts(token), now, future=future)


def parse_range(a: str, b: str, now: datetime) -> tuple[datetime, datetime]:
    ha, ma, mer_a = _parts(a)
    hb, mb, mer_b = _parts(b)
    if mer_a is None and mer_b is not None and ha <= 12:
        mer_a = mer_b if not (mer_b == "pm" and ha > hb and hb != 12) else "am"  # "11-1pm" = 11am to 1pm
    start = _resolve(ha, ma, mer_a, now, future=False)
    end = _resolve(hb, mb, mer_b, now, future=False) if mer_b else _at(now, hb, mb)
    while end <= start:
        end += timedelta(hours=12)
    if end - start > timedelta(hours=16):
        raise CommandError("That range is longer than a day. Try something like 2-4.")
    return start, end


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_WEEKDAY_NAMES = {}
for _i, _names in enumerate([("mon", "monday"), ("tue", "tues", "tuesday"), ("wed", "wednesday"),
                             ("thu", "thur", "thurs", "thursday"), ("fri", "friday"),
                             ("sat", "saturday"), ("sun", "sunday")]):
    for _n in _names:
        _WEEKDAY_NAMES[_n] = _i


def parse_date(text: str, today: date) -> date:
    t = text.strip().lower().rstrip(".")
    t = re.sub(r"^(on|this|next)\s+", "", t)
    if t in ("today",):
        return today
    if t in ("tomorrow", "tmrw", "tmr"):
        return today + timedelta(days=1)
    if m := re.fullmatch(r"in (\d{1,3}) days?", t):
        return today + timedelta(days=int(m.group(1)))
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if t in _WEEKDAY_NAMES:
        ahead = (_WEEKDAY_NAMES[t] - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?", t) or re.fullmatch(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?", t)
    if m:
        month_word, day_num = (m.group(1), m.group(2)) if m.group(1).isalpha() else (m.group(2), m.group(1))
        month = _MONTHS.get(month_word[:3])
        if month:
            d = date(today.year, month, int(day_num))
            return d if d >= today else date(today.year + 1, month, int(day_num))
    raise CommandError(f'I couldn\'t read "{text}" as a date. Try "oct 20", "friday" or "in 5 days".')


_LABEL = r"(?P<label>[a-z][a-z'&/ ]{0,40}?)"


def parse(text: str, now: datetime) -> Command:
    t = " ".join(text.strip().lower().split())
    if not t:
        raise CommandError(HELP)

    if re.fullmatch(r"(light|busy|rough|short|lazy) day", t):
        return Command("light")
    if re.fullmatch(r"(normal|full|regular) day", t):
        return Command("normal")
    if re.fullmatch(r"(clear|reset|clear busy|clear today)", t):
        return Command("clear")
    if m := re.fullmatch(r"(skip|unskip|restore) (.+)", t):
        return Command("unskip" if m.group(1) != "skip" else "skip", target=m.group(2))
    if m := re.fullmatch(r"(?:energy|feeling|i feel|i'm|im) (low|tired|drained|ok|okay|fine|good|high|great|energized)", t):
        word = m.group(1)
        value = "low" if word in ("low", "tired", "drained") else "high" if word in ("high", "great", "energized") else "ok"
        return Command("energy", value=value)
    if m := re.fullmatch(r"(?:note|park|remember|todo)[: ]+(.+)", text.strip(), flags=re.IGNORECASE):
        return Command("note", value=m.group(1).strip())
    if m := re.fullmatch(r"(?:focus|start)(?: (\d{1,3}))?(?: ?(?:m|min|mins|minutes))?", t):
        return Command("focus", minutes=int(m.group(1)) if m.group(1) else None)
    if m := re.fullmatch(r"interview (?:with |at )?(.+)", t):
        words = m.group(1).split()
        # The date is the last one to three words: "oct 20", "next friday", "in 5 days".
        for n in (3, 2, 1):
            if len(words) > n:
                company, when = " ".join(words[:-n]), " ".join(words[-n:])
                try:
                    on = parse_date(when, now.date())
                except CommandError:
                    continue
                company = re.sub(r"\s+(on|this|next)$", "", company)
                return Command("interview", label=company.title(), on=on)
        raise CommandError('Add a date, like "interview Shopify oct 20" or "interview Shopify friday".')

    # "<label> till 3" or "busy until 4:30pm"
    if m := re.fullmatch(_LABEL + rf"\s+(?:till|until|til|to)\s+(?P<t>{_TIME_PART})", t):
        label = m.group("label").strip()
        end = parse_time(m.group("t"), now, future=True)
        kind = "free" if label.startswith("free") else "busy"
        return Command(kind, start=now, end=end, label=_label(label, kind))
    # "<label> 2-4", "busy from 2 to 4pm", "free 12-1"
    if m := re.fullmatch(_LABEL + rf"\s+(?:from\s+)?(?P<a>{_TIME_PART})\s*(?:-|–|to|until|till)\s*(?P<b>{_TIME_PART})", t):
        label = m.group("label").strip()
        start, end = parse_range(m.group("a"), m.group("b"), now)
        kind = "free" if label.startswith("free") else "busy"
        return Command(kind, start=start, end=end, label=_label(label, kind))

    raise CommandError(f"I didn't catch that. {HELP}")


def _label(raw: str, kind: str) -> str:
    raw = re.sub(r"^(busy|free)\s*(with|for)?\s*", "", raw).strip()
    if not raw:
        return "Free" if kind == "free" else "Busy"
    return raw[0].upper() + raw[1:]
