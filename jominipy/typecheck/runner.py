"""Type-check runner over a shared Jomini parse result."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import is_dataclass, replace

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
from jominipy.typecheck.services import (
    TypecheckServices,
    build_typecheck_services_from_project_root,
)


def run_typecheck(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    rules: Sequence[TypecheckRule] | None = None,
    services: TypecheckServices | None = None,
    project_root: str | None = None,
) -> TypecheckRunResult:
    """Run type checking from a single parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    analysis_facts = resolved_parse.analysis_facts()
    type_facts = build_typecheck_facts(analysis_facts)

    if services is not None:
        resolved_services = services
    elif project_root is not None:
        resolved_services = build_typecheck_services_from_project_root(project_root=project_root)
    else:
        resolved_services = TypecheckServices()
    resolved_rules = (
        tuple(rules)
        if rules is not None
        else default_typecheck_rules(services=resolved_services)
    )
    if rules is not None and (services is not None or project_root is not None):
        resolved_rules = _bind_services_to_rules(resolved_rules, services=resolved_services)
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


def _bind_services_to_rules(
    rules: tuple[TypecheckRule, ...],
    *,
    services: TypecheckServices,
) -> tuple[TypecheckRule, ...]:
    bound: list[TypecheckRule] = []
    for rule in rules:
        if not is_dataclass(rule):
            bound.append(rule)
            continue
        replacements: dict[str, object] = {}
        if hasattr(rule, "asset_registry"):
            replacements["asset_registry"] = services.asset_registry
        if hasattr(rule, "policy"):
            replacements["policy"] = services.policy
        if hasattr(rule, "type_memberships_by_key") and not getattr(rule, "type_memberships_by_key"):
            replacements["type_memberships_by_key"] = services.type_memberships_by_key
        if hasattr(rule, "value_memberships_by_key") and not getattr(rule, "value_memberships_by_key"):
            replacements["value_memberships_by_key"] = services.value_memberships_by_key
        if hasattr(rule, "known_scopes") and not getattr(rule, "known_scopes"):
            replacements["known_scopes"] = services.known_scopes
        if replacements:
            bound.append(replace(rule, **replacements))
        else:
            bound.append(rule)
    return tuple(bound)
