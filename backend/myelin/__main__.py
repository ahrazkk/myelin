"""Run Myelin: `python -m myelin` (or `pythonw -m myelin` for no console window)."""

from __future__ import annotations

import sys

import uvicorn

from .app import create_app
from .config import load_config


def main() -> None:
    config = load_config()

    # pythonw (no console) leaves stdout/stderr as None, which breaks logging. Send them to a file.
    if sys.stdout is None or sys.stderr is None:
        log = open(config.data_dir / "myelin.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    uvicorn.run(create_app(config), host=config.host, port=config.port, log_level="warning")


if __name__ == "__main__":
    main()
