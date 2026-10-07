import sqlite3

from sqlmodel import Session

from myelin.db import make_engine
from myelin.models import UserSettings


def test_old_database_gains_new_settings_columns(tmp_path):
    """A database made by v0.1 (fewer columns) opens fine and gets the new columns with defaults."""
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE usersettings (id INTEGER PRIMARY KEY, latitude FLOAT, longitude FLOAT, timezone VARCHAR, "
        "calc_method VARCHAR NOT NULL, asr_method VARCHAR NOT NULL, started_on DATE)"
    )
    con.execute("INSERT INTO usersettings VALUES (1, 43.6, -79.4, 'America/Toronto', 'NORTH_AMERICA', 'SHAFI', NULL)")
    con.commit()
    con.close()

    engine = make_engine(f"sqlite:///{db}")
    with Session(engine) as s:
        settings = s.get(UserSettings, 1)
        assert settings.latitude == 43.6
        assert settings.theme == "auto"
        assert settings.work_start == "09:00"
        assert settings.reduced_motion is False
