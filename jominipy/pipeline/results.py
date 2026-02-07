"""Pipeline run result carriers for tool entrypoints."""

from dataclasses import dataclass

from jominipy.diagnostics import Diagnostic
from jominipy.pipeline.result import JominiParseResult


@dataclass(frozen=True, slots=True)
class LintRunResult:
    """Result of running lint rules from a shared parse result."""

    parse: JominiParseResult
    diagnostics: list[Diagnostic]


@dataclass(frozen=True, slots=True)
class FormatRunResult:
    """Result of formatting from a shared parse result."""

    parse: JominiParseResult
    formatted_text: str
    diagnostics: list[Diagnostic]
    changed: bool


@dataclass(frozen=True, slots=True)
class CheckRunResult:
    """Result of unified parser/lint checks from a shared parse result."""

    parse: JominiParseResult
    diagnostics: list[Diagnostic]
    has_errors: bool

