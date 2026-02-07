from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any


class TokenKind(Enum):
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LT = auto()
    GT = auto()
    EQUAL = auto()
    DOUBLE_EQUAL = auto()
    DOT_DOT = auto()
    COMMENT = auto()
    EOF = auto()


@dataclass
class Token:
    kind: TokenKind
    value: Any
    line: int
    column: int
    raw: str | None = None
    source: Path | None = None
