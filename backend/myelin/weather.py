"""Current weather from Open-Meteo (free, no account or key).

Only used when the weather background or the temperature line is on. The request carries your
location rounded to about 1 km, and nothing else. Results are cached for 15 minutes.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Optional

API = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 15 * 60

# WMO weather codes -> (scene, label, intensity 0..1). Scenes are what the background knows how to draw.
CODES: dict[int, tuple[str, str, float]] = {
    0: ("clear", "Clear", 0.0),
    1: ("clear", "Mostly clear", 0.0),
    2: ("partly", "Partly cloudy", 0.4),
    3: ("cloudy", "Overcast", 0.9),
    45: ("fog", "Fog", 0.6),
    48: ("fog", "Freezing fog", 0.7),
    51: ("drizzle", "Light drizzle", 0.2),
    53: ("drizzle", "Drizzle", 0.35),
    55: ("drizzle", "Heavy drizzle", 0.5),
    56: ("drizzle", "Freezing drizzle", 0.3),
    57: ("drizzle", "Freezing drizzle", 0.5),
    61: ("rain", "Light rain", 0.35),
    63: ("rain", "Rain", 0.6),
    65: ("rain", "Heavy rain", 0.95),
    66: ("rain", "Freezing rain", 0.5),
    67: ("rain", "Freezing rain", 0.8),
    71: ("snow", "Light snow", 0.35),
    73: ("snow", "Snow", 0.6),
    75: ("snow", "Heavy snow", 0.95),
    77: ("snow", "Snow grains", 0.4),
    80: ("rain", "Rain showers", 0.5),
    81: ("rain", "Heavy showers", 0.8),
    82: ("rain", "Violent showers", 1.0),
    85: ("snow", "Snow showers", 0.5),
    86: ("snow", "Heavy snow showers", 0.9),
    95: ("storm", "Thunderstorm", 0.8),
    96: ("storm", "Thunderstorm with hail", 0.9),
    99: ("storm", "Thunderstorm with hail", 1.0),
}


def describe(code: int) -> tuple[str, str, float]:
    return CODES.get(int(code), ("cloudy", "Cloudy", 0.5))


def build_url(latitude: float, longitude: float, unit: str) -> str:
    params = {
        "latitude": f"{latitude:.2f}",
        "longitude": f"{longitude:.2f}",
        "current": "temperature_2m,apparent_temperature,weather_code,is_day,cloud_cover,precipitation,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
        "forecast_days": "1",
        "timezone": "auto",
    }
    if unit == "f":
        params["temperature_unit"] = "fahrenheit"
    return f"{API}?{urllib.parse.urlencode(params)}"


def parse(raw: dict, unit: str) -> dict:
    cur = raw["current"]
    daily = raw.get("daily") or {}
    scene, label, intensity = describe(cur["weather_code"])

    def first(key: str):
        values = daily.get(key) or []
        return values[0] if values else None

    def rounded(v):
        return None if v is None else round(float(v))

    return {
        "scene": scene,
        "label": label,
        "intensity": intensity,
        "code": int(cur["weather_code"]),
        "temp": rounded(cur.get("temperature_2m")),
        "feels_like": rounded(cur.get("apparent_temperature")),
        "high": rounded(first("temperature_2m_max")),
        "low": rounded(first("temperature_2m_min")),
        "is_day": bool(cur.get("is_day", 1)),
        "cloud_cover": cur.get("cloud_cover"),
        "wind_kmh": cur.get("wind_speed_10m"),
        "precipitation_mm": cur.get("precipitation"),
        "unit": unit,
        "observed_at": cur.get("time"),
    }


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Myelin (github.com/ahrazkk/myelin)"})
    with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 - fixed https endpoint
        return json.loads(r.read().decode("utf-8"))


class WeatherUnavailable(Exception):
    pass


class WeatherService:
    def __init__(self, fetch: Optional[Callable[[str], dict]] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.fetch = fetch or _http_get_json
        self.clock = clock
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def current(self, latitude: float, longitude: float, unit: str = "c") -> dict:
        key = (round(latitude, 2), round(longitude, 2), unit)
        cached = self._cache.get(key)
        if cached and self.clock() - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            data = parse(self.fetch(build_url(latitude, longitude, unit)), unit)
        except Exception as e:  # offline, timeout, unexpected reply
            if cached:  # an older reading beats none
                return {**cached[1], "stale": True}
            raise WeatherUnavailable(str(e)) from e
        self._cache[key] = (self.clock(), data)
        return data
