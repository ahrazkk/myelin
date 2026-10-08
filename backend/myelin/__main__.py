"""Run Myelin: `python -m myelin` (or `pythonw -m myelin` for no console window)."""

from __future__ import annotations

import dataclasses
import sys

import uvicorn
from sqlmodel import Session

from .app import create_app
from .config import load_config
from .db import make_engine
from .deps import load_settings


def main() -> None:
    config = load_config()

    # pythonw (no console) leaves stdout/stderr as None, which breaks logging. Send them to a file.
    if sys.stdout is None or sys.stderr is None:
        log = open(config.data_dir / "myelin.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    engine = make_engine(config.db_url)
    with Session(engine) as s:
        if load_settings(s).phone_access and config.host in ("127.0.0.1", "localhost"):
            # Phone access: listen on the home network too (only the lock-screen picture is served there).
            config = dataclasses.replace(config, host="0.0.0.0")
    uvicorn.run(create_app(config, engine), host=config.host, port=config.port, log_level="warning")


if __name__ == "__main__":
    main()
