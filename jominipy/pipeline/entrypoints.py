"""Unified entrypoints that orchestrate parse/lint/format with one parse lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jominipy.diagnostics import Diagnostic, has_errors
from jominipy.format import run_format as _run_format
from jominipy.lint import run_lint as _run_lint
from jominipy.parser import ParseMode, ParserOptions, parse_result
from jominipy.pipeline.result import JominiParseResult
from jominipy.pipeline.results import (
    CheckRunResult,
    FormatRunResult,
    LintRunResult,
    TypecheckRunResult,
)

if TYPE_CHECKING:
    from jominipy.lint.rules import LintRule
    from jominipy.typecheck.rules import TypecheckRule
    from jominipy.typecheck.services import TypecheckServices
from jominipy.typecheck import run_typecheck as _run_typecheck


def run_lint(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    typecheck: TypecheckRunResult | None = None,
    rules: tuple[LintRule, ...] | None = None,
) -> LintRunResult:
    """Run linting over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    typecheck_result = (
        typecheck if typecheck is not None else _run_typecheck(resolved_parse.source_text, parse=resolved_parse)
    )
    if typecheck_result.parse is not resolved_parse:
        raise ValueError("Provided typecheck result must reuse the same parse result")
    return _run_lint(
        resolved_parse.source_text,
        parse=resolved_parse,
        typecheck=typecheck_result,
        rules=rules,
    )


def run_typecheck(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    rules: tuple[TypecheckRule, ...] | None = None,
    services: TypecheckServices | None = None,
    project_root: str | None = None,
) -> TypecheckRunResult:
    """Run type checking over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    return _run_typecheck(
        resolved_parse.source_text,
        parse=resolved_parse,
        rules=rules,
        services=services,
        project_root=project_root,
    )


def run_format(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> FormatRunResult:
    """Run formatting over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    return _run_format(resolved_parse.source_text, parse=resolved_parse)


def run_check(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    services: TypecheckServices | None = None,
    project_root: str | None = None,
) -> CheckRunResult:
    """Run parse + typecheck + lint checks over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    typecheck_result = _run_typecheck(
        resolved_parse.source_text,
        parse=resolved_parse,
        services=services,
        project_root=project_root,
    )
    lint_result = _run_lint(
        resolved_parse.source_text,
        parse=resolved_parse,
        typecheck=typecheck_result,
    )
    diagnostics = _dedupe_diagnostics([*typecheck_result.diagnostics, *lint_result.diagnostics])
    return CheckRunResult(
        parse=resolved_parse,
        diagnostics=diagnostics,
        has_errors=has_errors(diagnostics),
    )


def _resolve_parse(
    text: str,
    *,
    options: ParserOptions | None,
    mode: ParseMode | None,
    parse: JominiParseResult | None,
) -> JominiParseResult:
    if parse is not None:
        if options is not None or mode is not None:
            raise ValueError("Pass either parse or options/mode, not both")
        return parse
    return parse_result(text, options=options, mode=mode)


def _dedupe_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    deduped: list[Diagnostic] = []
    seen: set[tuple[int, int, str, str, str | None, str | None]] = set()
    for diagnostic in diagnostics:
        key = (
            diagnostic.range.start.value,
            diagnostic.range.end.value,
            diagnostic.code,
            diagnostic.message,
            diagnostic.category,
            diagnostic.hint,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(diagnostic)
    return deduped
