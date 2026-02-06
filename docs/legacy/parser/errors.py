from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Diagnostic:
    message: str
    line: int
    column: int
    source: Path | None = None
