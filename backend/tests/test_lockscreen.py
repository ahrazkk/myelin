import io
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from myelin.winlock import LockScreenUpdater


def image(resp) -> Image.Image:
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    return Image.open(io.BytesIO(resp.content))


def test_phone_picture_is_iphone_sized(client):
    client.put("/api/settings", json={"latitude": 21.42, "longitude": 39.83})
    img = image(client.get("/lockscreen/phone.png"))
    assert img.size == (1179, 2556)
    # The top of the picture stays empty for the iPhone clock.
    top = img.crop((0, 0, 1179, 1000)).convert("L")
    assert top.getextrema()[0] == top.getextrema()[1]


def test_desktop_picture_matches_requested_size(client):
    img = image(client.get("/lockscreen/desktop.png?w=2560&h=1440"))
    assert img.size == (2560, 1440)


def test_picture_shows_night_colours_after_maghrib(client, clock):
    client.put("/api/settings", json={"latitude": 21.42, "longitude": 39.83})
    day = image(client.get("/lockscreen/phone.png")).getpixel((5, 5))
    clock.when += timedelta(hours=10)  # 20:00 in Makkah, after Maghrib
    night = image(client.get("/lockscreen/phone.png")).getpixel((5, 5))
    assert sum(night) < sum(day)


def test_only_the_phone_picture_is_reachable_from_the_network(client):
    lan = TestClient(client.app, client=("192.168.1.20", 50000))
    assert lan.get("/api/today").status_code == 403
    assert lan.get("/").status_code == 403
    assert lan.get("/lockscreen/phone.png").status_code == 403  # phone access is off

    key = client.put("/api/settings", json={"phone_access": True}).json()["phone_key"]
    assert key
    assert lan.get("/lockscreen/phone.png?key=wrong").status_code == 403
    assert lan.get(f"/lockscreen/phone.png?key={key}").status_code == 200

    new_key = client.post("/api/settings/phone-key").json()["phone_key"]
    assert new_key != key
    assert lan.get(f"/lockscreen/phone.png?key={key}").status_code == 403


def test_status_reports_phone_url_only_when_enabled(client):
    assert client.get("/api/lockscreen").json()["phone"]["url"] is None
    client.put("/api/settings", json={"phone_access": True})
    url = client.get("/api/lockscreen").json()["phone"]["url"]
    assert url is None or ("/lockscreen/phone.png?key=" in url)


def test_windows_updater_writes_a_new_file_each_time_and_cleans_up(tmp_path: Path):
    set_paths = []
    updater = LockScreenUpdater(tmp_path, lambda: True, lambda w, h: b"jpeg", setter=set_paths.append)
    updater.run_once()
    first = set_paths[-1]
    (tmp_path / "myelin-1.jpg").write_bytes(b"old")
    updater.run_once()
    assert updater.last_error is None and updater.last_set is not None
    assert sorted(p.name for p in tmp_path.glob("myelin-*.jpg")) == [set_paths[-1].name]
    assert first.exists() is (first == set_paths[-1])


def test_windows_updater_reports_errors(tmp_path: Path):
    def fail(path):
        raise RuntimeError("Access denied")

    updater = LockScreenUpdater(tmp_path, lambda: True, lambda w, h: b"jpeg", setter=fail)
    updater.run_once()
    assert updater.last_error == "Access denied"


def test_open_blocks_are_never_reported_as_done(client):
    """Late in the day, unscheduled blocks are still open, not finished."""
    from myelin import lockscreen
    from myelin.routes.today import today as today_data  # noqa: F401  (route module loads)

    today = client.get("/api/today").json()
    for item in today["plan"]:
        item["status"] = "no_room"  # nothing left on the schedule
    snap = lockscreen.snapshot(today)
    assert snap.next_title is None
    open_blocks = sum(1 for i in today["plan"] if not i.get("bonus") and not i["done"])
    assert lockscreen.plan_line(snap) == f"{open_blocks} blocks still open today."

    for item in today["plan"]:
        item["done"] = True
    assert lockscreen.plan_line(lockscreen.snapshot(today)) == "Everything on today's plan is done."
