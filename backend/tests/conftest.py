from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from myelin.app import create_app
from myelin.config import Config
from myelin.db import make_engine


class FakeClock:
    """A controllable 'now' so tests can move through days."""

    def __init__(self, when: datetime):
        self.when = when

    def __call__(self, tz):
        return self.when.astimezone(tz) if tz else self.when


@pytest.fixture
def clock() -> FakeClock:
    # Monday 5 Oct 2026, 10:00 in Makkah
    return FakeClock(datetime(2026, 10, 5, 10, 0, tzinfo=ZoneInfo("Asia/Riyadh")))


@pytest.fixture
def client(tmp_path: Path, clock: FakeClock) -> TestClient:
    config = Config(data_dir=tmp_path, host="127.0.0.1", port=0, frontend_dist=tmp_path / "no-dist")
    engine = make_engine(config.db_url)
    app = create_app(config=config, engine=engine, clock=clock)
    with TestClient(app) as c:
        c.put("/api/settings", json={"timezone": "Asia/Riyadh"})
        yield c
