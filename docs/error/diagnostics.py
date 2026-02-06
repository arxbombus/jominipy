from dataclasses import dataclass
from pathlib import Path

from jominipy.types import Position


@dataclass
class Diagnostic:
    message: str
    position: Position
    source: Path | None = None
