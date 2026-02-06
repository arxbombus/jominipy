"""Diagnostics core types."""

from dataclasses import dataclass
from typing import Literal

from jominipy.text import TextRange

Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Structured diagnostic emitted by lexers/parsers/linters/formatters."""

    code: str
    message: str
    range: TextRange
    severity: Severity = "error"
    hint: str | None = None
    category: str | None = None
