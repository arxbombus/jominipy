"""Semantic extraction over normalized rules IR."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Literal

from jominipy.rules.ir import (
    RuleExpression,
    RuleMetadata,
    RuleScopeReplacement,
    RuleStatement,
)
from jominipy.rules.schema_graph import load_hoi4_schema_graph

_SIMPLE_FIELD_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCALAR_PATTERN = re.compile(r"^(?P<head>[^\[\]]+)(?:\[(?P<arg>.*)\])?$")
_TYPE_REF_INLINE_PATTERN = re.compile(r"^.*<(?P<type_key>[A-Za-z_][A-Za-z0-9_]*)>.*$")

type RuleValueSpecKind = Literal[
    "primitive",
    "enum_ref",
    "scope_ref",
    "value_ref",
    "value_set_ref",
    "alias_match_left_ref",
    "single_alias_ref",
    "type_ref",
    "unknown_ref",
    "block",
    "tagged_block",
    "missing",
    "error",
]


@dataclass(frozen=True, slots=True)
class RuleValueSpec:
    kind: RuleValueSpecKind
    raw: str
    primitive: str | None = None
    argument: str | None = None


@dataclass(frozen=True, slots=True)
class RuleFieldConstraint:
    required: bool
    value_specs: tuple[RuleValueSpec, ...]
    comparison: bool = False
    error_if_only_match: str | None = None
    outgoing_reference_label: str | None = None
    incoming_reference_label: str | None = None


@dataclass(frozen=True, slots=True)
class RuleFieldScopeConstraint:
    required_scope: tuple[str, ...] | None = None
    push_scope: tuple[str, ...] | None = None
    replace_scope: tuple[RuleScopeReplacement, ...] | None = None


def build_required_fields_by_object(
    statements: tuple[RuleStatement, ...],
    *,
    include_implicit_required: bool = False,
) -> dict[str, tuple[str, ...]]:
    """Extract object->required-fields mapping from normalized rules statements."""
    result: dict[str, tuple[str, ...]] = {}
    for statement in statements:
        if statement.key is None or statement.value.kind != "block":
            continue
        required: list[str] = []
        seen: set[str] = set()
        for child in statement.value.block:
            if child.kind != "key_value" or child.key is None:
                continue
            if _SIMPLE_FIELD_KEY.match(child.key) is None:
                continue

            cardinality = child.metadata.cardinality
            is_required = False
            if cardinality is not None:
                if cardinality.minimum_unbounded:
                    is_required = True
                elif cardinality.minimum is not None and cardinality.minimum > 0:
                    is_required = True
            elif include_implicit_required:
                is_required = True

            if is_required and child.key not in seen:
                seen.add(child.key)
                required.append(child.key)

        if required:
            result[statement.key] = tuple(required)
    return result


def build_field_constraints_by_object(
    statements: tuple[RuleStatement, ...],
    *,
    include_implicit_required: bool = False,
) -> dict[str, dict[str, RuleFieldConstraint]]:
    result: dict[str, dict[str, RuleFieldConstraint]] = {}
    for statement in statements:
        if statement.key is None or statement.value.kind != "block":
            continue

        constraints: dict[str, RuleFieldConstraint] = {}
        for child in statement.value.block:
            if child.kind != "key_value" or child.key is None:
                continue
            if _SIMPLE_FIELD_KEY.match(child.key) is None:
                continue

            required = _is_required(child.metadata, include_implicit_required=include_implicit_required)
            specs = extract_value_specs(child.value)
            existing = constraints.get(child.key)
            if existing is None:
                constraints[child.key] = RuleFieldConstraint(
                    required=required,
                    value_specs=specs,
                    comparison=child.metadata.comparison,
                    error_if_only_match=child.metadata.error_if_only_match,
                    outgoing_reference_label=child.metadata.outgoing_reference_label,
                    incoming_reference_label=child.metadata.incoming_reference_label,
                )
                continue
            merged_specs = _merge_value_specs(existing.value_specs, specs)
            constraints[child.key] = RuleFieldConstraint(
                required=existing.required or required,
                value_specs=merged_specs,
                comparison=existing.comparison or child.metadata.comparison,
                error_if_only_match=existing.error_if_only_match or child.metadata.error_if_only_match,
                outgoing_reference_label=(
                    existing.outgoing_reference_label or child.metadata.outgoing_reference_label
                ),
                incoming_reference_label=(
                    existing.incoming_reference_label or child.metadata.incoming_reference_label
                ),
            )

        if constraints:
            result[statement.key] = constraints
    return result


def build_field_scope_constraints_by_object(
    statements: tuple[RuleStatement, ...],
) -> dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]]:
    """Extract object->field-path scope constraints from normalized rules statements."""
    result: dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]] = {}
    for statement in statements:
        if statement.key is None or statement.value.kind != "block":
            continue
        object_constraints: dict[tuple[str, ...], RuleFieldScopeConstraint] = {}
        _collect_scope_constraints(
            statement.value.block,
            path=(),
            output=object_constraints,
        )
        top_scope = _to_scope_constraint(statement.metadata)
        if top_scope is not None:
            object_constraints[()] = top_scope
        if object_constraints:
            result[statement.key] = object_constraints
    return result


def _is_required(metadata: RuleMetadata, *, include_implicit_required: bool) -> bool:
    cardinality = metadata.cardinality
    if cardinality is not None:
        if cardinality.minimum_unbounded:
            return True
        if cardinality.minimum is not None and cardinality.minimum > 0:
            return True
        return False
    return include_implicit_required


def _to_scope_constraint(metadata: RuleMetadata) -> RuleFieldScopeConstraint | None:
    if metadata.scope is None and metadata.push_scope is None and metadata.replace_scope is None:
        return None
    return RuleFieldScopeConstraint(
        required_scope=metadata.scope,
        push_scope=metadata.push_scope,
        replace_scope=metadata.replace_scope,
    )


def _collect_scope_constraints(
    statements: tuple[RuleStatement, ...],
    *,
    path: tuple[str, ...],
    output: dict[tuple[str, ...], RuleFieldScopeConstraint],
) -> None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key is None:
            continue
        child_path = (*path, statement.key)
        scope_constraint = _to_scope_constraint(statement.metadata)
        if scope_constraint is not None:
            output[child_path] = scope_constraint
        if statement.value.kind == "block":
            _collect_scope_constraints(statement.value.block, path=child_path, output=output)


def extract_value_specs(expression: RuleExpression) -> tuple[RuleValueSpec, ...]:
    if expression.kind == "missing":
        return (RuleValueSpec(kind="missing", raw=""),)
    if expression.kind == "error":
        return (RuleValueSpec(kind="error", raw=expression.text or ""),)
    if expression.kind == "block":
        return (RuleValueSpec(kind="block", raw="{...}"),)
    if expression.kind == "tagged_block":
        return (RuleValueSpec(kind="tagged_block", raw=expression.tag or "", argument=expression.tag),)
    if expression.kind != "scalar":
        return (RuleValueSpec(kind="unknown_ref", raw=expression.text or ""),)

    text = (expression.text or "").strip()
    if not text:
        return (RuleValueSpec(kind="unknown_ref", raw=text),)

    inline_type_match = _TYPE_REF_INLINE_PATTERN.match(text)
    if inline_type_match is not None:
        return (
            RuleValueSpec(
                kind="type_ref",
                raw=text,
                argument=inline_type_match.group("type_key").strip(),
            ),
        )

    match = _SCALAR_PATTERN.match(text)
    if match is None:
        return (RuleValueSpec(kind="unknown_ref", raw=text),)

    head = match.group("head").strip()
    argument = (match.group("arg") or "").strip() or None
    lower_head = head.lower()

    if lower_head in {
        "int",
        "float",
        "bool",
        "scalar",
        "localisation",
        "localisation_synced",
        "localisation_inline",
        "percentage_field",
        "date_field",
        "filepath",
        "icon",
        "variable_field",
        "int_variable_field",
        "value_field",
        "int_value_field",
        "scope_field",
    }:
        return (RuleValueSpec(kind="primitive", raw=text, primitive=lower_head, argument=argument),)
    if lower_head == "enum":
        return (RuleValueSpec(kind="enum_ref", raw=text, argument=argument),)
    if lower_head == "scope":
        return (RuleValueSpec(kind="scope_ref", raw=text, argument=argument),)
    if lower_head == "value":
        return (RuleValueSpec(kind="value_ref", raw=text, argument=argument),)
    if lower_head == "value_set":
        return (RuleValueSpec(kind="value_set_ref", raw=text, argument=argument),)
    if lower_head == "alias_match_left":
        return (RuleValueSpec(kind="alias_match_left_ref", raw=text, argument=argument),)
    if lower_head == "single_alias_right":
        return (RuleValueSpec(kind="single_alias_ref", raw=text, argument=argument),)

    return (RuleValueSpec(kind="unknown_ref", raw=text, argument=argument),)


def _merge_value_specs(
    left: tuple[RuleValueSpec, ...],
    right: tuple[RuleValueSpec, ...],
) -> tuple[RuleValueSpec, ...]:
    merged: list[RuleValueSpec] = list(left)
    seen = {(spec.kind, spec.raw, spec.primitive, spec.argument) for spec in left}
    for spec in right:
        key = (spec.kind, spec.raw, spec.primitive, spec.argument)
        if key in seen:
            continue
        seen.add(key)
        merged.append(spec)
    return tuple(merged)


@lru_cache(maxsize=1)
def load_hoi4_required_fields(*, include_implicit_required: bool = False) -> dict[str, tuple[str, ...]]:
    """Load required fields derived from the HOI4 cross-file CWTools schema."""
    schema = load_hoi4_schema_graph()
    if not schema.top_level_rule_statements:
        return {}

    return build_required_fields_by_object(
        schema.top_level_rule_statements,
        include_implicit_required=include_implicit_required,
    )


@lru_cache(maxsize=1)
def load_hoi4_field_constraints(
    *,
    include_implicit_required: bool = False,
) -> dict[str, dict[str, RuleFieldConstraint]]:
    """Load per-object field constraints from the HOI4 cross-file CWTools schema."""
    from jominipy.rules.adapter import load_hoi4_expanded_field_constraints

    return load_hoi4_expanded_field_constraints(
        include_implicit_required=include_implicit_required,
    )


@lru_cache(maxsize=1)
def load_hoi4_enum_values() -> dict[str, frozenset[str]]:
    """Load enum key -> allowed scalar values from HOI4 schema graph."""
    schema = load_hoi4_schema_graph()
    values_by_enum: dict[str, set[str]] = {}
    for enum_key, declarations in schema.enums_by_key.items():
        bucket = values_by_enum.setdefault(enum_key, set())
        for declaration in declarations:
            statement = declaration.statement
            if statement.value.kind != "block":
                continue
            for child in statement.value.block:
                if child.kind != "value":
                    continue
                if child.value.kind != "scalar":
                    continue
                raw = (child.value.text or "").strip()
                if raw:
                    bucket.add(raw)
    return {key: frozenset(values) for key, values in values_by_enum.items()}


@lru_cache(maxsize=1)
def load_hoi4_type_keys() -> frozenset[str]:
    """Load known type keys declared by HOI4 schema graph."""
    schema = load_hoi4_schema_graph()
    return frozenset(schema.types_by_key.keys())


@lru_cache(maxsize=1)
def load_hoi4_field_scope_constraints() -> dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]]:
    """Load per-object field-path scope constraints from HOI4 cross-file schema."""
    schema = load_hoi4_schema_graph()
    if not schema.top_level_rule_statements:
        return {}
    return build_field_scope_constraints_by_object(schema.top_level_rule_statements)


@lru_cache(maxsize=1)
def load_hoi4_known_scopes() -> frozenset[str]:
    """Load known scope aliases from HOI4 `scopes` declarations."""
    schema = load_hoi4_schema_graph()
    scope_names: set[str] = set()
    for section in schema.sections_by_key.get("scopes", ()):
        statement = section.statement
        if statement.value.kind != "block":
            continue
        for entry in statement.value.block:
            if entry.kind != "key_value" or entry.key is None:
                continue
            if entry.key:
                scope_names.add(entry.key.strip().lower())
            if entry.value.kind != "block":
                continue
            for child in entry.value.block:
                if child.kind != "key_value" or child.key != "aliases":
                    continue
                if child.value.kind != "block":
                    continue
                for alias_value in child.value.block:
                    if alias_value.kind != "value":
                        continue
                    if alias_value.value.kind != "scalar":
                        continue
                    alias_text = (alias_value.value.text or "").strip().strip('"').lower()
                    if alias_text:
                        scope_names.add(alias_text)
    return frozenset(scope_names)
