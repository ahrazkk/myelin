from myelin.weather import WeatherService, WeatherUnavailable, build_url, describe, parse

SAMPLE = {
    "current": {"time": "2026-10-07T23:30", "temperature_2m": 14.6, "apparent_temperature": 14.1,
                "weather_code": 2, "is_day": 0, "cloud_cover": 50, "precipitation": 0.0, "wind_speed_10m": 8.2},
    "daily": {"time": ["2026-10-07"], "temperature_2m_max": [22.2], "temperature_2m_min": [13.1]},
}


def test_codes_map_to_scenes():
    assert describe(0)[0] == "clear"
    assert describe(3)[:2] == ("cloudy", "Overcast")
    assert describe(65)[0] == "rain" and describe(65)[2] > describe(61)[2]
    assert describe(75)[0] == "snow"
    assert describe(95)[0] == "storm"
    assert describe(1234)[0] == "cloudy"  # unknown codes still draw something sensible


def test_parse_rounds_and_labels():
    w = parse(SAMPLE, "c")
    assert (w["scene"], w["label"], w["temp"], w["high"], w["low"]) == ("partly", "Partly cloudy", 15, 22, 13)
    assert w["is_day"] is False


def test_url_rounds_location_and_honours_fahrenheit():
    url = build_url(43.65321, -79.38318, "f")
    assert "latitude=43.65" in url and "longitude=-79.38" in url and "temperature_unit=fahrenheit" in url
    assert "temperature_unit" not in build_url(43.65, -79.38, "c")


def test_service_caches_and_falls_back_to_a_stale_reading():
    calls = []
    t = [0.0]

    def fetch(url):
        calls.append(url)
        if len(calls) > 1:
            raise OSError("offline")
        return SAMPLE

    svc = WeatherService(fetch=fetch, clock=lambda: t[0])
    assert svc.current(43.65, -79.38)["temp"] == 15
    assert svc.current(43.65, -79.38)["temp"] == 15 and len(calls) == 1  # cached
    t[0] = 16 * 60
    stale = svc.current(43.65, -79.38)
    assert stale["stale"] is True and stale["temp"] == 15


def test_service_without_any_reading_reports_unavailable():
    svc = WeatherService(fetch=lambda url: (_ for _ in ()).throw(OSError("offline")))
    try:
        svc.current(1, 2)
    except WeatherUnavailable:
        pass
    else:
        raise AssertionError("expected WeatherUnavailable")


def test_endpoint(client):
    assert client.get("/api/weather").json() == {"available": False, "reason": "no_location"}

    client.app.state.weather = WeatherService(fetch=lambda url: SAMPLE)
    client.put("/api/settings", json={"latitude": 43.65, "longitude": -79.38})
    w = client.get("/api/weather").json()
    assert w["available"] is True and w["scene"] == "partly" and w["temp"] == 15

    client.put("/api/settings", json={"background": "plain", "show_weather": False})
    assert client.get("/api/weather").json() == {"available": False, "reason": "off"}


def test_appearance_settings_validate(client):
    ok = client.put("/api/settings", json={"background": "neural", "cursor_effect": "synapses", "accent": "rose",
                                           "clock_24h": True, "show_seconds": True, "temperature_unit": "f"})
    assert ok.status_code == 200
    body = ok.json()
    assert (body["background"], body["cursor_effect"], body["accent"], body["clock_24h"]) == ("neural", "synapses", "rose", True)
    assert client.put("/api/settings", json={"background": "lava"}).status_code == 422
    assert client.put("/api/settings", json={"accent": "neon"}).status_code == 422
