"""Where Myelin keeps its data, and how the server is reached.

Everything is local. The database lives in the user's app-data folder
(for example %LOCALAPPDATA%\\Myelin on Windows), never inside the repo.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "Myelin"


@dataclass(frozen=True)
class Config:
    data_dir: Path
    host: str
    port: int
    frontend_dist: Path

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'myelin.db'}"


def load_config() -> Config:
    data_dir = Path(os.environ.get("MYELIN_DATA_DIR") or user_data_dir(APP_NAME, appauthor=False))
    data_dir.mkdir(parents=True, exist_ok=True)

    if getattr(sys, "frozen", False):  # the packaged Myelin.exe carries the web interface inside it
        default_dist = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "frontend"
    else:
        default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    frontend_dist = Path(os.environ.get("MYELIN_FRONTEND_DIST") or default_dist)

    return Config(
        data_dir=data_dir,
        # Localhost only for now. Phone access on home Wi-Fi comes in Phase 2.
        host=os.environ.get("MYELIN_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYELIN_PORT", "8765")),
        frontend_dist=frontend_dist,
    )
