"""Draws a lock-screen picture of your day: the streak axon, what's next, and the next prayer.

Phones and Windows don't let ordinary apps put live widgets on the lock screen, but both will show
a picture. Myelin redraws it on a schedule, so the picture stays current.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from importlib import resources

from PIL import Image, ImageDraw, ImageFont

SCALE = 2  # draw big, then shrink: smooth edges on the capsules

PALETTES = {
    "day": {"bg": "#edeff5", "ink": "#1b2142", "muted": "#5d6485", "hair": "#c2c8da",
            "myelin": "#2d6bad", "cresyl": "#7b3f9e"},
    "night": {"bg": "#0e1530", "ink": "#e4e8f6", "muted": "#949bbb", "hair": "#2b3462",
              "myelin": "#57c4e5", "cresyl": "#d07be8"},
}

PRAYER_NAMES = {"fajr": "Fajr", "sunrise": "Sunrise", "dhuhr": "Dhuhr", "asr": "Asr", "maghrib": "Maghrib",
                "isha": "Isha"}


@lru_cache(maxsize=64)
def font(face: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    path = resources.files("myelin").joinpath(f"assets/fonts/{face}.ttf")
    with resources.as_file(path) as p:
        f = ImageFont.truetype(str(p), size)
    try:
        f.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass
    return f


def clock(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt.minute:02d} {'a.m.' if dt.hour < 12 else 'p.m.'}"


def clock_range(a: datetime, b: datetime) -> str:
    same = (a.hour < 12) == (b.hour < 12)
    first = f"{a.hour % 12 or 12}:{a.minute:02d}" if same else clock(a)
    return f"{first}–{clock(b)}"


@dataclass
class Snapshot:
    """What the picture needs, pulled from the Today data."""

    now: datetime
    night: bool
    cycle_day: int
    cycle: list[str]  # statuses: done | missed | today | future
    current: int
    today_complete: bool
    light: bool
    next_title: str | None
    next_when: str | None
    later: list[tuple[str, str]]
    next_prayer: tuple[str, str] | None
    done_count: int
    total_count: int


def snapshot(today: dict) -> Snapshot:
    now = datetime.fromisoformat(today["now"])
    prayers = today.get("prayers")
    night = False
    next_prayer = None
    if prayers:
        times = {t["name"]: datetime.fromisoformat(t["at"]) for t in prayers["times"]}
        night = now >= times["maghrib"] or now < times["sunrise"]
        nxt = prayers["next"]
        next_prayer = (PRAYER_NAMES[nxt["name"]], clock(datetime.fromisoformat(nxt["at"]).astimezone(now.tzinfo)))
    else:
        night = now.hour >= 19 or now.hour < 6

    scheduled = [i for i in today["plan"] if not i["done"] and i.get("status") == "scheduled" and i.get("start")]
    scheduled.sort(key=lambda i: i["start"])

    def when(i: dict) -> str:
        a = datetime.fromisoformat(i["start"]).astimezone(now.tzinfo)
        b = datetime.fromisoformat(i["end"]).astimezone(now.tzinfo)
        return clock_range(a, b)

    streak = today["streak"]
    real = [i for i in today["plan"] if not i.get("bonus")]
    return Snapshot(
        now=now,
        night=night,
        cycle_day=streak["cycle_day"],
        cycle=[d["status"] for d in streak["cycle"]],
        current=streak["current"],
        today_complete=streak["today_complete"],
        light=today.get("day", {}).get("light", False),
        next_title=scheduled[0]["title"] if scheduled else None,
        next_when=when(scheduled[0]) if scheduled else None,
        later=[(i["title"], when(i)) for i in scheduled[1:4]],
        next_prayer=next_prayer,
        done_count=sum(1 for i in real if i["done"]),
        total_count=len(real),
    )


def _axon(draw: ImageDraw.ImageDraw, x0: int, y: int, width: int, cycle: list[str], cycle_day: int, pal: dict,
          sheath_h: int) -> None:
    n = len(cycle)
    step = width / n
    gap = max(2, step * 0.12)
    today_i = cycle_day - 1
    draw.line([(x0, y), (x0 + step * (today_i + 1), y)], fill=pal["muted"], width=max(2, sheath_h // 9))
    draw.line([(x0 + step * (today_i + 1), y), (x0 + width, y)], fill=pal["hair"], width=max(2, sheath_h // 9))
    r = min(sheath_h / 2, (step - 2 * gap) / 2)
    for i, status in enumerate(cycle):
        a = x0 + i * step + gap
        b = x0 + (i + 1) * step - gap
        box = [a, y - sheath_h / 2, b, y + sheath_h / 2]
        if status == "done":
            draw.rounded_rectangle(box, radius=r, fill=pal["myelin"])
        elif i == today_i:
            draw.rounded_rectangle(box, radius=r, outline=pal["cresyl"], width=max(3, sheath_h // 7))


def _streak_text(s: Snapshot) -> str:
    if s.today_complete:
        return f"{s.current}-day streak. Today is wrapped."
    if s.current == 0:
        return "Day one of a new streak."
    return f"{s.current}-day streak"


def render(s: Snapshot, width: int, height: int, layout: str) -> Image.Image:
    """layout: 'phone' (content in the lower half, clear of the iPhone clock) or 'desktop'.

    Everything is drawn at SCALE x size in "design units" (k = pixels per design px), then shrunk.
    """
    pal = PALETTES["night" if s.night else "day"]
    W, H = width * SCALE, height * SCALE
    img = Image.new("RGB", (W, H), pal["bg"])
    d = ImageDraw.Draw(img)

    def text(xy, value, size, weight=450, color="ink", face="AtkinsonHyperlegibleNext", anchor="la"):
        d.text(xy, value, font=font(face, max(8, int(size)), weight), fill=pal[color], anchor=anchor)

    if layout == "phone":
        k = W / 1179  # designed for a 1179 x 2556 iPhone screen
        margin = int(100 * k)
        inner = W - 2 * margin
        y = int(H * 0.47)  # below the system clock and widgets

        text((margin, y), f"Day {s.cycle_day} of 66", 34 * k, 650, "cresyl")
        y += int(75 * k)
        _axon(d, margin, y, inner, s.cycle, s.cycle_day, pal, int(30 * k))
        y += int(60 * k)
        text((margin, y), _streak_text(s), 52 * k, 600)
        y += int(130 * k)

        if s.next_title:
            text((margin, y), "Next", 34 * k, 500, "muted")
            y += int(52 * k)
            text((margin, y), _fit(d, s.next_title, inner, 66 * k, 650), 66 * k, 650)
            y += int(88 * k)
            text((margin, y), s.next_when or "", 42 * k, 600, "myelin", face="Manrope")
            y += int(96 * k)
            for title, when in s.later:
                text((margin, y), _fit(d, title, inner * 0.6, 38 * k, 450), 38 * k, 450, "muted")
                text((margin + inner, y), when, 38 * k, 500, "muted", face="Manrope", anchor="ra")
                y += int(62 * k)
        else:
            done = "Everything on today's plan is done." if s.done_count else "Nothing scheduled right now."
            text((margin, y), done, 46 * k, 550)

        if s.next_prayer:
            name, at = s.next_prayer
            text((margin, int(H * 0.84)), name, 44 * k, 650, "cresyl")
            text((margin + int(190 * k), int(H * 0.84)), at, 44 * k, 600, "cresyl", face="Manrope")
    else:
        k = H / 1080  # designed for a 1920 x 1080 screen
        margin = int(130 * k)
        inner = int(W * 0.55)
        y = int(H * 0.58)  # below the Windows clock

        text((margin, y), f"Day {s.cycle_day} of 66", 26 * k, 650, "cresyl")
        y += int(56 * k)
        _axon(d, margin, y, inner, s.cycle, s.cycle_day, pal, int(22 * k))
        y += int(46 * k)
        text((margin, y), _streak_text(s), 36 * k, 600)
        y += int(84 * k)
        if s.next_title:
            text((margin, y), _fit(d, f"Next: {s.next_title}", inner, 40 * k, 650), 40 * k, 650)
            text((margin, y + int(58 * k)), s.next_when or "", 30 * k, 600, "myelin", face="Manrope")
        if s.next_prayer:
            name, at = s.next_prayer
            text((W - margin, int(H * 0.58)), name, 32 * k, 650, "cresyl", anchor="ra")
            text((W - margin, int(H * 0.58) + int(48 * k)), at, 30 * k, 550, "muted", face="Manrope", anchor="ra")

    return img.resize((width, height), Image.LANCZOS)


def _fit(d: ImageDraw.ImageDraw, value: str, max_w: float, size: float, weight: int) -> str:
    f = font("AtkinsonHyperlegibleNext", max(8, int(size)), weight)
    if d.textlength(value, font=f) <= max_w:
        return value
    while value and d.textlength(value + "…", font=f) > max_w:
        value = value[:-1]
    return value.rstrip() + "…"


def png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
