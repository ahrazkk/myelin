"""The desktop app's pieces that can be tested without a screen."""

from datetime import datetime, timedelta

from PIL import Image

from myelin import desktop


def test_tray_icon_draws():
    img = desktop.tray_image(64)
    assert isinstance(img, Image.Image) and img.size == (64, 64)
    assert img.getpixel((32, 32))[3] == 255  # the node in the middle is opaque


def test_app_info_without_the_desktop_app(client):
    info = client.get("/api/app").json()
    assert info["desktop"] is False and info["hotkey"] is None
    assert client.post("/api/app/show").status_code == 409


def test_app_info_with_the_desktop_app(client):
    shown = []

    class FakeDesktop:
        def show(self):
            shown.append(True)

    client.app.state.desktop = FakeDesktop()
    assert client.get("/api/app").json()["hotkey"] == "Ctrl+Alt+M"
    assert client.post("/api/app/show").json()["ok"] is True
    assert shown == [True]


class RecordingNotifier(desktop.Notifier):
    def __init__(self, client):
        super().__init__("http://test", on_click=lambda: None)
        self.client = client
        self.shown: list[tuple[str, str]] = []

    def show(self, title, body):
        self.shown.append((title, body))


def test_notifier_reminds_once_before_a_prayer(client, monkeypatch, clock):
    client.put("/api/settings", json={"latitude": 21.42, "longitude": 39.83})
    monkeypatch.setattr(desktop, "_get", lambda base, path, timeout=3: client.get(path).json())
    n = RecordingNotifier(client)

    dhuhr = next(t for t in client.get("/api/today").json()["prayers"]["times"] if t["name"] == "dhuhr")
    at = datetime.fromisoformat(dhuhr["at"])
    n.check(now=at - timedelta(minutes=8))
    n.check(now=at - timedelta(minutes=7))
    prayer_toasts = [t for t in n.shown if t[0].startswith("Dhuhr")]
    assert len(prayer_toasts) == 1 and "8 minutes" in prayer_toasts[0][0]


def test_notifier_respects_the_setting(client, monkeypatch):
    client.put("/api/settings", json={"latitude": 21.42, "longitude": 39.83, "notifications": False})
    monkeypatch.setattr(desktop, "_get", lambda base, path, timeout=3: client.get(path).json())
    n = RecordingNotifier(client)
    n.check()
    assert n.shown == []


def test_notifier_says_when_focus_ends(client, monkeypatch, clock):
    monkeypatch.setattr(desktop, "_get", lambda base, path, timeout=3: client.get(path).json())
    client.post("/api/focus/start", json={"label": "Two Sum", "minutes": 25})
    clock.when += timedelta(minutes=26)
    n = RecordingNotifier(client)
    n.check()
    assert ("Time's up: Two Sum", "Mark it done or keep going for 10 more minutes.") in n.shown


def test_launch_command_points_at_the_desktop_module():
    assert "myelin.desktop --background" in desktop.launch_command() or desktop.launch_command().endswith(
        "--background")


def test_recognises_myelin_processes_only():
    assert desktop.is_myelin_process("Myelin.exe", r"C:\Users\a\AppData\Local\Programs\Myelin\Myelin.exe")
    assert desktop.is_myelin_process("pythonw.exe", r"C:\code\myelin\backend\.venv\Scripts\pythonw.exe -m myelin")
    assert desktop.is_myelin_process("python.exe", "python -m myelin.desktop --background")
    assert not desktop.is_myelin_process("python.exe", "python -m http.server 8765")
    assert not desktop.is_myelin_process("chrome.exe", "chrome --myelin")


def _app(tmp_path):
    from myelin.config import Config

    return desktop.DesktopApp(Config(data_dir=tmp_path, host="127.0.0.1", port=8765,
                                     frontend_dist=tmp_path), background=True)


def test_shares_a_server_of_the_same_version(tmp_path, monkeypatch):
    from myelin import __version__

    monkeypatch.setattr(desktop, "server_version", lambda base: __version__)
    monkeypatch.setattr(desktop, "stop_old_myelin", lambda port: (_ for _ in ()).throw(AssertionError("stopped")))
    _app(tmp_path).start_server()  # returns without starting or stopping anything


def test_replaces_an_older_server(tmp_path, monkeypatch):
    stopped = []
    monkeypatch.setattr(desktop, "server_version", lambda base: "0.1.0")
    monkeypatch.setattr(desktop, "stop_old_myelin", lambda port: stopped.append(port) or False)
    app = _app(tmp_path)
    try:
        app.start_server()
    except RuntimeError as e:
        assert "0.1.0" in str(e)  # couldn't stop it in this test, so it explains what to do
    assert stopped == [8765]
