from __future__ import annotations

from functools import lru_cache
import re

from jominipy.rules.adapters.common import (
    build_constraints_from_rule_block,
    merge_specs,
)
from jominipy.rules.adapters.models import SubtypeMatcher
from jominipy.rules.ir import RuleMetadata, RuleStatement
from jominipy.rules.schema_graph import RuleSchemaGraph, load_hoi4_schema_graph
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    extract_value_specs,
)

_SUBTYPE_PATTERN = re.compile(r"^subtype\[(?P<name>[^\]]+)\]$")


@lru_cache(maxsize=1)
def load_hoi4_subtype_matchers_by_object() -> dict[str, tuple[SubtypeMatcher, ...]]:
    """Load subtype matchers keyed by object/type name."""
    schema = load_hoi4_schema_graph()
    return build_subtype_matchers_by_object(schema)


@lru_cache(maxsize=1)
def load_hoi4_subtype_field_constraints_by_object() -> dict[str, dict[str, dict[str, RuleFieldConstraint]]]:
    """Load subtype-specific field constraints keyed by object->subtype->field."""
    schema = load_hoi4_schema_graph()
    return build_subtype_field_constraints_by_object(schema)


def build_subtype_matchers_by_object(schema: RuleSchemaGraph) -> dict[str, tuple[SubtypeMatcher, ...]]:
    """Build per-object subtype matchers from `type[...]` declarations."""
    matchers: dict[str, list[SubtypeMatcher]] = {}
    for object_key, declarations in schema.types_by_key.items():
        bucket = matchers.setdefault(object_key, [])
        for declaration in declarations:
            statement = declaration.statement
            if statement.value.kind != "block":
                continue
            for child in statement.value.block:
                subtype_name = _subtype_name(child.key)
                if subtype_name is None or child.value.kind != "block":
                    continue
                expected = _collect_subtype_expected_fields(child.value.block)
                include_filters, exclude_filters, starts_with = _parse_subtype_matcher_options(child.metadata)
                bucket.append(
                    SubtypeMatcher(
                        subtype_name=subtype_name,
                        expected_field_values=expected,
                        type_key_filters=include_filters,
                        excluded_type_key_filters=exclude_filters,
                        starts_with=starts_with,
                        push_scope=tuple(scope.lower() for scope in (child.metadata.push_scope or ())),
                    )
                )
    return {key: tuple(items) for key, items in matchers.items() if items}


def build_subtype_field_constraints_by_object(
    schema: RuleSchemaGraph,
) -> dict[str, dict[str, dict[str, RuleFieldConstraint]]]:
    """Build subtype-conditional field constraints from top-level object rules."""
    single_alias_constraints = _collect_single_alias_constraints(schema)
    output: dict[str, dict[str, dict[str, RuleFieldConstraint]]] = {}
    for statement in schema.top_level_rule_statements:
        object_key = statement.key
        if object_key is None or statement.value.kind != "block":
            continue
        subtype_map: dict[str, dict[str, RuleFieldConstraint]] = {}
        for child in statement.value.block:
            subtype_name = _subtype_name(child.key)
            if subtype_name is None or child.value.kind != "block":
                continue
            subtype_fields = build_constraints_from_rule_block(
                child.value.block,
                single_alias_constraints=single_alias_constraints,
            )
            if subtype_fields:
                subtype_map[subtype_name] = subtype_fields
        if subtype_map:
            output[object_key] = subtype_map
    return output


def _collect_single_alias_constraints(
    schema: RuleSchemaGraph,
) -> dict[str, RuleFieldConstraint]:
    aliases: dict[str, RuleFieldConstraint] = {}
    for alias_name, declarations in schema.single_aliases_by_key.items():
        merged: tuple[RuleValueSpec, ...] = ()
        for declaration in declarations:
            statement = declaration.statement
            if statement.kind != "key_value":
                continue
            specs = extract_value_specs(statement.value)
            merged = merge_specs(merged, specs)
        if merged:
            aliases[alias_name] = RuleFieldConstraint(required=False, value_specs=merged)
    return aliases


def _subtype_name(key: str | None) -> str | None:
    if key is None:
        return None
    match = _SUBTYPE_PATTERN.match(key)
    if match is None:
        return None
    name = match.group("name").strip()
    return name or None


def _collect_subtype_expected_fields(
    statements: tuple[RuleStatement, ...],
) -> tuple[tuple[str, str], ...]:
    expected: list[tuple[str, str]] = []
    for statement in statements:
        if statement.kind != "key_value" or statement.key is None:
            continue
        if statement.value.kind != "scalar":
            continue
        raw = (statement.value.text or "").strip().strip('"')
        if not raw:
            continue
        expected.append((statement.key, raw))
    return tuple(expected)


def _parse_subtype_matcher_options(
    metadata: RuleMetadata,
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    include_filters: list[str] = []
    exclude_filters: list[str] = []
    starts_with: str | None = None
    for option in metadata.options:
        key = option.key.strip().lower()
        value = (option.value or "").strip()
        if not value:
            continue
        if key == "type_key_filter":
            include, exclude = _parse_type_key_filter_value(value)
            include_filters.extend(include)
            exclude_filters.extend(exclude)
            continue
        if key == "starts_with":
            starts_with = value.strip().strip('"').strip("'") or None
    return (tuple(include_filters), tuple(exclude_filters), starts_with)


def _parse_type_key_filter_value(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    raw = value.strip()
    negate = False
    for marker in ("<>", "!="):
        if raw.startswith(marker):
            negate = True
            raw = raw[len(marker) :].strip()
            break
    values = _parse_value_list(raw)
    if negate:
        return ((), values)
    return (values, ())


def _parse_value_list(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        inner = stripped[1:-1].strip()
        if not inner:
            return ()
        return tuple(part for part in inner.split() if part)
    return (stripped,) if stripped else ()
