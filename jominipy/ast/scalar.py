"""Scalar interpretation helpers for AST consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

type DateLike = tuple[int, int, int]

_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d+|\d+\.\d*|\.\d+)$")
_DATE_RE = re.compile(r"^([+-]?\d+)\.(\d+)\.(\d+)$")


class ScalarKind(StrEnum):
    UNKNOWN = "unknown"
    BOOL = "bool"
    NUMBER = "number"
    DATE_LIKE = "date_like"


@dataclass(frozen=True, slots=True)
class ScalarInterpretation:
    kind: ScalarKind
    value: bool | int | float | DateLike | None
    bool_value: bool | None
    number_value: int | float | None
    date_value: DateLike | None

    @property
    def is_unknown(self) -> bool:
        return self.kind == ScalarKind.UNKNOWN


def parse_bool(text: str) -> bool | None:
    normalized = text.strip().lower()
    if normalized in {"yes", "true"}:
        return True
    if normalized in {"no", "false"}:
        return False
    return None


def parse_number(text: str) -> int | float | None:
    normalized = text.strip()
    if not normalized:
        return None

    if normalized.count(".") > 1:
        return None

    if _INTEGER_RE.fullmatch(normalized):
        return int(normalized)

    if _FLOAT_RE.fullmatch(normalized):
        return float(normalized)

    return None


def parse_date_like(text: str) -> DateLike | None:
    normalized = text.strip()
    match = _DATE_RE.fullmatch(normalized)
    if match is None:
        return None

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    return (year, month, day)


def interpret_scalar(
    text: str,
    *,
    was_quoted: bool = False,
    allow_quoted: bool = False,
) -> ScalarInterpretation:
    if was_quoted and not allow_quoted:
        return ScalarInterpretation(
            kind=ScalarKind.UNKNOWN,
            value=None,
            bool_value=None,
            number_value=None,
            date_value=None,
        )

    bool_value = parse_bool(text)
    if bool_value is not None:
        return ScalarInterpretation(
            kind=ScalarKind.BOOL,
            value=bool_value,
            bool_value=bool_value,
            number_value=None,
            date_value=None,
        )

    date_value = parse_date_like(text)
    if date_value is not None:
        return ScalarInterpretation(
            kind=ScalarKind.DATE_LIKE,
            value=date_value,
            bool_value=None,
            number_value=None,
            date_value=date_value,
        )

    number_value = parse_number(text)
    if number_value is not None:
        return ScalarInterpretation(
            kind=ScalarKind.NUMBER,
            value=number_value,
            bool_value=None,
            number_value=number_value,
            date_value=None,
        )

    return ScalarInterpretation(
        kind=ScalarKind.UNKNOWN,
        value=None,
        bool_value=None,
        number_value=None,
        date_value=None,
    )


__all__ = [
    "DateLike",
    "ScalarInterpretation",
    "ScalarKind",
    "interpret_scalar",
    "parse_bool",
    "parse_date_like",
    "parse_number",
]
