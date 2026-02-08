"""Semantic extraction over normalized rules IR."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Literal

from jominipy.rules.ir import RuleExpression, RuleMetadata, RuleStatement
from jominipy.rules.load import load_rules_paths

_SIMPLE_FIELD_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCALAR_PATTERN = re.compile(r"^(?P<head>[^\[\]]+)(?:\[(?P<arg>.*)\])?$")

type RuleValueSpecKind = Literal[
    "primitive",
    "enum_ref",
    "scope_ref",
    "value_ref",
    "value_set_ref",
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
            specs = _extract_value_specs(child.value)
            existing = constraints.get(child.key)
            if existing is None:
                constraints[child.key] = RuleFieldConstraint(required=required, value_specs=specs)
                continue
            merged_specs = _merge_value_specs(existing.value_specs, specs)
            constraints[child.key] = RuleFieldConstraint(
                required=existing.required or required,
                value_specs=merged_specs,
            )

        if constraints:
            result[statement.key] = constraints
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


def _extract_value_specs(expression: RuleExpression) -> tuple[RuleValueSpec, ...]:
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

    if text.startswith("<") and text.endswith(">") and len(text) > 2:
        return (RuleValueSpec(kind="type_ref", raw=text, argument=text[1:-1].strip()),)

    match = _SCALAR_PATTERN.match(text)
    if match is None:
        return (RuleValueSpec(kind="unknown_ref", raw=text),)

    head = match.group("head").strip()
    argument = (match.group("arg") or "").strip() or None
    lower_head = head.lower()

    if lower_head in {"int", "float", "bool", "scalar", "localisation", "localisation_synced", "localisation_inline"}:
        return (RuleValueSpec(kind="primitive", raw=text, primitive=lower_head, argument=argument),)
    if lower_head == "enum":
        return (RuleValueSpec(kind="enum_ref", raw=text, argument=argument),)
    if lower_head == "scope":
        return (RuleValueSpec(kind="scope_ref", raw=text, argument=argument),)
    if lower_head == "value":
        return (RuleValueSpec(kind="value_ref", raw=text, argument=argument),)
    if lower_head == "value_set":
        return (RuleValueSpec(kind="value_set_ref", raw=text, argument=argument),)

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
    """Load required fields derived from the HOI4 technologies CWTools schema."""
    root = Path(__file__).resolve().parents[2]
    technologies = root / "references/hoi4-rules/Config/common/technologies.cwt"
    if not technologies.exists():
        return {}

    loaded = load_rules_paths((technologies,))
    file_ir = loaded.ruleset.files[0]
    return build_required_fields_by_object(
        file_ir.statements,
        include_implicit_required=include_implicit_required,
    )


@lru_cache(maxsize=1)
def load_hoi4_field_constraints(
    *,
    include_implicit_required: bool = False,
) -> dict[str, dict[str, RuleFieldConstraint]]:
    """Load per-object field constraints from HOI4 technologies schema."""
    root = Path(__file__).resolve().parents[2]
    technologies = root / "references/hoi4-rules/Config/common/technologies.cwt"
    if not technologies.exists():
        return {}

    loaded = load_rules_paths((technologies,))
    file_ir = loaded.ruleset.files[0]
    return build_field_constraints_by_object(
        file_ir.statements,
        include_implicit_required=include_implicit_required,
    )
