"""Pipeline run result carriers for tool entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jominipy.diagnostics import Diagnostic
from jominipy.pipeline.result import JominiParseResult

if TYPE_CHECKING:
    from jominipy.typecheck.rules import TypecheckFacts


@dataclass(frozen=True, slots=True)
class LintRunResult:
    """Result of running lint rules from a shared parse result."""

    parse: JominiParseResult
    diagnostics: list[Diagnostic]
    type_facts: TypecheckFacts | None = None


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


@dataclass(frozen=True, slots=True)
class TypecheckRunResult:
    """Result of running type-check rules from a shared parse result."""

    parse: JominiParseResult
    diagnostics: list[Diagnostic]
    facts: TypecheckFacts
