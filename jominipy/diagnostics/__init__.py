"""Diagnostics."""

from jominipy.diagnostics.codes import (
    LEXER_UNTERMINATED_STRING,
    PARSER_EXPECTED_TOKEN,
    PARSER_EXPECTED_VALUE,
    PARSER_LEGACY_EXTRA_RBRACE,
    PARSER_LEGACY_MISSING_RBRACE,
    PARSER_UNEXPECTED_TOKEN,
    PARSER_UNSUPPORTED_PARAMETER_SYNTAX,
    PARSER_UNSUPPORTED_UNMARKED_LIST,
    DiagnosticSpec,
)
from jominipy.diagnostics.diagnostic import Diagnostic, Severity
from jominipy.diagnostics.report import collect_diagnostics, has_errors

__all__ = [
    "LEXER_UNTERMINATED_STRING",
    "PARSER_EXPECTED_TOKEN",
    "PARSER_EXPECTED_VALUE",
    "PARSER_LEGACY_EXTRA_RBRACE",
    "PARSER_LEGACY_MISSING_RBRACE",
    "PARSER_UNEXPECTED_TOKEN",
    "PARSER_UNSUPPORTED_PARAMETER_SYNTAX",
    "PARSER_UNSUPPORTED_UNMARKED_LIST",
    "Diagnostic",
    "DiagnosticSpec",
    "Severity",
    "collect_diagnostics",
    "has_errors",
]
