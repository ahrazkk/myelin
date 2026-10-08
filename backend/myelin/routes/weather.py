"""Current weather for the background and the temperature line."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..deps import Ctx
from ..weather import WeatherService, WeatherUnavailable

router = APIRouter(prefix="/api")


def service(request: Request) -> WeatherService:
    if not hasattr(request.app.state, "weather"):
        request.app.state.weather = WeatherService()
    return request.app.state.weather


@router.get("/weather")
def weather(ctx: Ctx = Depends()) -> dict:
    s = ctx.settings
    if s.background != "weather" and not s.show_weather:
        return {"available": False, "reason": "off"}
    if s.latitude is None or s.longitude is None:
        return {"available": False, "reason": "no_location"}
    try:
        data = service(ctx.request).current(s.latitude, s.longitude, s.temperature_unit)
    except WeatherUnavailable:
        return {"available": False, "reason": "offline"}
    return {"available": True, **data}
