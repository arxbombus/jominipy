"""Parser modes and configuration options."""

from dataclasses import dataclass
from enum import StrEnum


class ParseMode(StrEnum):
    """Top-level parser behavior profile."""

    STRICT = "strict"
    PERMISSIVE = "permissive"


@dataclass(frozen=True, slots=True)
class ParserOptions:
    """Feature flags controlling grammar compatibility and recovery behavior."""

    mode: ParseMode = ParseMode.STRICT
    allow_legacy_extra_rbrace: bool = False
    allow_legacy_missing_rbrace: bool = False
    allow_semicolon_terminator: bool = True

    @staticmethod
    def for_mode(mode: ParseMode) -> "ParserOptions":
        if mode == ParseMode.PERMISSIVE:
            return ParserOptions(
                mode=mode,
                allow_legacy_extra_rbrace=True,
                allow_legacy_missing_rbrace=True,
                allow_semicolon_terminator=True,
            )

        return ParserOptions(
            mode=mode,
            allow_legacy_extra_rbrace=False,
            allow_legacy_missing_rbrace=False,
            allow_semicolon_terminator=True,
        )
