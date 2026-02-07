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
    allow_semicolon_terminator: bool = False
    allow_parameter_syntax: bool = False
    allow_unmarked_list_form: bool = False
    allow_alternating_value_key_value: bool = True
    allow_bare_scalar_after_key_value: bool = False

    @staticmethod
    def for_mode(mode: ParseMode) -> "ParserOptions":
        if mode == ParseMode.PERMISSIVE:
            return ParserOptions(
                mode=mode,
                allow_legacy_extra_rbrace=True,
                allow_legacy_missing_rbrace=True,
                allow_semicolon_terminator=True,
                allow_parameter_syntax=False,
                allow_unmarked_list_form=False,
                allow_alternating_value_key_value=True,
                allow_bare_scalar_after_key_value=True,
            )

        return ParserOptions(
            mode=mode,
            allow_legacy_extra_rbrace=False,
            allow_legacy_missing_rbrace=False,
            allow_semicolon_terminator=False,
            allow_parameter_syntax=False,
            allow_unmarked_list_form=False,
            allow_alternating_value_key_value=True,
            allow_bare_scalar_after_key_value=False,
        )
