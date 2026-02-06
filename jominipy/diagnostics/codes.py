"""Diagnostic codes and messages."""

from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class DiagnosticSpec:
    code: str
    message: str
    hint: str | None = None
    severity: Severity = "error"
    category: str | None = None


LEXER_UNTERMINATED_STRING: Final[DiagnosticSpec] = DiagnosticSpec(
    code="LEXER_UNTERMINATED_STRING",
    message="Unterminated string literal.",
    hint="Close the string with a double quote or enable multiline strings.",
    severity="error",
    category="lexer",
)
