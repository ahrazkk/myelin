"""Where things live: the repo root, the design folder and the hand-written config."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# design/myelin_design/project.py -> design/ -> repo root
DESIGN_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Project:
    root: Path

    @classmethod
    def default(cls) -> Project:
        return cls(DESIGN_DIR.parent)

    @property
    def design_dir(self) -> Path:
        return self.root / "design"

    @property
    def config(self) -> dict[str, Any]:
        """design.toml, read fresh each time, so a long-running server never serves a stale copy."""
        return tomllib.loads(read_text(self.design_dir / "design.toml"))

    @property
    def source_css(self) -> Path:
        return self.root / self.config["source"]

    @property
    def frontend_src(self) -> Path:
        return self.root / "frontend" / "src"

    @property
    def tokens_json(self) -> Path:
        return self.design_dir / "tokens.json"

    @property
    def tokens_ts(self) -> Path | None:
        """The generated TypeScript module, if design.toml asks for one."""
        name = self.config.get("generated_ts")
        return self.root / name if name else None

    @property
    def tokens_schema(self) -> Path:
        return self.design_dir / "tokens.schema.json"

    def relative(self, path: Path) -> str:
        """A path as it should appear in reports: relative to the repo, with forward slashes."""
        return path.resolve().relative_to(self.root.resolve()).as_posix()


def read_text(path: Path) -> str:
    """Read a text file with its line endings normalised, so Windows and Linux agree."""
    # utf-8-sig drops the byte-order mark that some Windows editors put at the start of a file.
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
