"""Type-check runner over a shared Jomini parse result."""

from __future__ import annotations

from collections.abc import Sequence

from jominipy.diagnostics import Diagnostic
from jominipy.parser import ParseMode, ParserOptions, parse_result
from jominipy.pipeline.result import JominiParseResult
from jominipy.pipeline.results import TypecheckRunResult
from jominipy.typecheck.rules import (
    TypecheckRule,
    build_typecheck_facts,
    default_typecheck_rules,
    validate_typecheck_rules,
)
from jominipy.typecheck.services import TypecheckServices


def run_typecheck(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    rules: Sequence[TypecheckRule] | None = None,
    services: TypecheckServices | None = None,
) -> TypecheckRunResult:
    """Run type checking from a single parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    analysis_facts = resolved_parse.analysis_facts()
    type_facts = build_typecheck_facts(analysis_facts)

    resolved_services = services if services is not None else TypecheckServices()
    resolved_rules = (
        tuple(rules)
        if rules is not None
        else default_typecheck_rules(services=resolved_services)
    )
    validate_typecheck_rules(resolved_rules)

    diagnostics = list(resolved_parse.diagnostics)
    for rule in resolved_rules:
        diagnostics.extend(rule.run(analysis_facts, type_facts, resolved_parse.source_text))

    return TypecheckRunResult(
        parse=resolved_parse,
        diagnostics=_sort_diagnostics(diagnostics),
        facts=type_facts,
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
