"""Lint runner over a shared Jomini parse result."""

from __future__ import annotations

from collections.abc import Sequence

from jominipy.diagnostics import Diagnostic
from jominipy.lint.rules import (
    LintRule,
    default_lint_rules,
    validate_lint_rules,
)
from jominipy.parser import ParseMode, ParserOptions, parse_result
from jominipy.pipeline.result import JominiParseResult
from jominipy.pipeline.results import LintRunResult, TypecheckRunResult
from jominipy.typecheck import run_typecheck as _run_typecheck


def run_lint(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    typecheck: TypecheckRunResult | None = None,
    rules: Sequence[LintRule] | None = None,
) -> LintRunResult:
    """Run lint diagnostics from a single parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    resolved_typecheck = _resolve_typecheck(typecheck=typecheck, parse=resolved_parse)
    analysis_facts = resolved_parse.analysis_facts()
    resolved_rules = tuple(rules) if rules is not None else default_lint_rules()
    validate_lint_rules(resolved_rules)

    diagnostics = list(resolved_parse.diagnostics)
    for rule in resolved_rules:
        diagnostics.extend(
            rule.run(
                analysis_facts,
                resolved_typecheck.facts,
                resolved_parse.source_text,
            )
        )

    return LintRunResult(
        parse=resolved_parse,
        diagnostics=_sort_diagnostics(diagnostics),
        type_facts=resolved_typecheck.facts,
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


def _resolve_typecheck(
    *,
    typecheck: TypecheckRunResult | None,
    parse: JominiParseResult,
) -> TypecheckRunResult:
    if typecheck is not None:
        if typecheck.parse is not parse:
            raise ValueError("Provided typecheck result must reuse the same parse result")
        return typecheck
    return _run_typecheck(parse.source_text, parse=parse)


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(
        diagnostics,
        key=lambda diagnostic: (
            diagnostic.range.start.value,
            diagnostic.range.end.value,
            diagnostic.code,
            diagnostic.message,
        ),
    )
