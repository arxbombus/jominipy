from __future__ import annotations

from jominipy.rules.ir import RuleStatement
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    extract_value_specs,
)


def find_scalar_child(statements: tuple[RuleStatement, ...], key: str) -> str | None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key != key:
            continue
        if statement.value.kind != "scalar":
            continue
        return (statement.value.text or "").strip().strip('"')
    return None


def find_scalar_children(statements: tuple[RuleStatement, ...], key: str) -> tuple[str, ...]:
    values: list[str] = []
    for statement in statements:
        if statement.kind != "key_value" or statement.key != key:
            continue
        if statement.value.kind != "scalar":
            continue
        value = (statement.value.text or "").strip().strip('"')
        if value:
            values.append(value)
    return tuple(values)


def find_block_child(statements: tuple[RuleStatement, ...], key: str) -> RuleStatement | None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key != key:
            continue
        if statement.value.kind != "block":
            continue
        return statement
    return None


def parse_bracket_key(raw_key: str, *, expected_family: str) -> str | None:
    prefix = f"{expected_family}["
    if not raw_key.startswith(prefix) or not raw_key.endswith("]"):
        return None
    inner = raw_key[len(prefix) : -1].strip()
    return inner or None


def extract_scope_list(statement: RuleStatement) -> tuple[str, ...]:
    if statement.value.kind == "scalar":
        raw = (statement.value.text or "").strip().strip('"')
        return (raw,) if raw else ()
    if statement.value.kind != "block":
        return ()
    scopes: list[str] = []
    for child in statement.value.block:
        if child.kind == "value" and child.value.kind == "scalar":
            raw = (child.value.text or "").strip().strip('"')
            if raw:
                scopes.append(raw)
    return tuple(scopes)


def is_required(statement: RuleStatement) -> bool:
    cardinality = statement.metadata.cardinality
    if cardinality is None:
        return False
    if cardinality.minimum_unbounded:
        return True
    return bool(cardinality.minimum is not None and cardinality.minimum > 0)


def expand_single_alias_specs(
    specs: tuple[RuleValueSpec, ...],
    *,
    single_alias_constraints: dict[str, RuleFieldConstraint],
) -> tuple[RuleValueSpec, ...]:
    expanded: tuple[RuleValueSpec, ...] = ()
    for spec in specs:
        if spec.kind != "single_alias_ref":
            expanded = merge_specs(expanded, (spec,))
            continue
        alias_name = (spec.argument or "").strip()
        alias_constraint = single_alias_constraints.get(alias_name)
        if alias_constraint is None:
            expanded = merge_specs(expanded, (spec,))
            continue
        expanded = merge_specs(expanded, alias_constraint.value_specs)
    return expanded


def merge_specs(
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


def build_constraints_from_rule_block(
    statements: tuple[RuleStatement, ...],
    *,
    single_alias_constraints: dict[str, RuleFieldConstraint],
) -> dict[str, RuleFieldConstraint]:
    by_field: dict[str, RuleFieldConstraint] = {}
    for child in statements:
        if child.kind != "key_value" or child.key is None:
            continue
        required = is_required(child)
        specs = expand_single_alias_specs(
            extract_value_specs(child.value),
            single_alias_constraints=single_alias_constraints,
        )
        existing = by_field.get(child.key)
        if existing is None:
            by_field[child.key] = RuleFieldConstraint(
                required=required,
                value_specs=specs,
                comparison=child.metadata.comparison,
                error_if_only_match=child.metadata.error_if_only_match,
                outgoing_reference_label=child.metadata.outgoing_reference_label,
                incoming_reference_label=child.metadata.incoming_reference_label,
            )
            continue
        by_field[child.key] = RuleFieldConstraint(
            required=existing.required or required,
            value_specs=merge_specs(existing.value_specs, specs),
            comparison=existing.comparison or child.metadata.comparison,
            error_if_only_match=existing.error_if_only_match or child.metadata.error_if_only_match,
            outgoing_reference_label=existing.outgoing_reference_label or child.metadata.outgoing_reference_label,
            incoming_reference_label=existing.incoming_reference_label or child.metadata.incoming_reference_label,
        )
    return by_field
