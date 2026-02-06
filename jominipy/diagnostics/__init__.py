"""Diagnostics."""

from jominipy.diagnostics.codes import LEXER_UNTERMINATED_STRING, DiagnosticSpec
from jominipy.diagnostics.diagnostic import Diagnostic, Severity
from jominipy.diagnostics.report import collect_diagnostics, has_errors

__all__ = ["LEXER_UNTERMINATED_STRING", "Diagnostic", "DiagnosticSpec", "Severity", "collect_diagnostics", "has_errors"]
