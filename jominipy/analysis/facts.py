"""Shared parse-derived facts for lint and type-check engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from jominipy.ast import (
    AstBlock,
    AstError,
    AstKeyValue,
    AstScalar,
    AstSourceFile,
    AstTaggedBlockValue,
)

type ValueShape = Literal["missing", "scalar", "block", "tagged", "error"]


@dataclass(frozen=True, slots=True)
class FieldFact:
    """Nested object field fact extracted from top-level object blocks."""

    object_key: str
    field_key: str
    path: tuple[str, ...]
    value: object | None
    object_occurrence: int
    field_occurrence: int


@dataclass(frozen=True, slots=True)
class AnalysisFacts:
    """Facts extracted once from AST and reused by multiple engines."""

    top_level_values: dict[str, tuple[object | None, ...]]
    top_level_shapes: dict[str, frozenset[ValueShape]]
    object_fields: dict[str, tuple[FieldFact, ...]]
    object_field_map: dict[str, dict[str, tuple[FieldFact, ...]]]
    all_field_facts: tuple[FieldFact, ...]


def build_analysis_facts(source_file: AstSourceFile) -> AnalysisFacts:
    values: dict[str, list[object | None]] = {}
    shapes: dict[str, set[ValueShape]] = {}
    object_fields: dict[str, list[FieldFact]] = {}
    object_field_groups: dict[str, dict[str, list[FieldFact]]] = {}
    all_field_facts: list[FieldFact] = []
    object_occurrences: dict[str, int] = {}

    for statement in source_file.statements:
        if not isinstance(statement, AstKeyValue):
            continue
        key = statement.key.raw_text
        value = statement.value
        object_occurrence = object_occurrences.get(key, 0)
        object_occurrences[key] = object_occurrence + 1
        values.setdefault(key, []).append(value)
        shapes.setdefault(key, set()).add(_shape_for_value(value))
        field_facts = _extract_object_field_facts(
            object_key=key,
            object_occurrence=object_occurrence,
            value=value,
        )
        if not field_facts:
            continue
        immediate_field_facts = tuple(fact for fact in field_facts if len(fact.path) == 2)
        if immediate_field_facts:
            object_fields.setdefault(key, []).extend(immediate_field_facts)
        grouped = object_field_groups.setdefault(key, {})
        for field_fact in immediate_field_facts:
            grouped.setdefault(field_fact.field_key, []).append(field_fact)
        all_field_facts.extend(field_facts)

    frozen_values = {key: tuple(group) for key, group in values.items()}
    frozen_shapes = {key: frozenset(group) for key, group in shapes.items()}
    frozen_object_fields = {key: tuple(group) for key, group in object_fields.items()}
    frozen_object_field_map = {
        object_key: {field_key: tuple(group) for field_key, group in grouped.items()}
        for object_key, grouped in object_field_groups.items()
    }
    return AnalysisFacts(
        top_level_values=frozen_values,
        top_level_shapes=frozen_shapes,
        object_fields=frozen_object_fields,
        object_field_map=frozen_object_field_map,
        all_field_facts=tuple(all_field_facts),
    )


def _shape_for_value(value: object | None) -> ValueShape:
    if value is None:
        return "missing"
    if isinstance(value, AstScalar):
        return "scalar"
    if isinstance(value, AstBlock):
        return "block"
    if isinstance(value, AstTaggedBlockValue):
        return "tagged"
    if isinstance(value, AstError):
        return "error"
    return "error"


def _extract_object_field_facts(
    *,
    object_key: str,
    object_occurrence: int,
    value: object | None,
) -> tuple[FieldFact, ...]:
    if not isinstance(value, AstBlock):
        return ()
    if not value.is_object_like:
        return ()
    return _collect_field_facts_recursive(
        object_key=object_key,
        object_occurrence=object_occurrence,
        block=value,
        parent_path=(object_key,),
    )


def _collect_field_facts_recursive(
    *,
    object_key: str,
    object_occurrence: int,
    block: AstBlock,
    parent_path: tuple[str, ...],
) -> tuple[FieldFact, ...]:
    field_occurrences: dict[str, int] = {}
    field_facts: list[FieldFact] = []
    for statement in block.statements:
        if not isinstance(statement, AstKeyValue):
            continue
        field_key = statement.key.raw_text
        field_occurrence = field_occurrences.get(field_key, 0)
        field_occurrences[field_key] = field_occurrence + 1
        current_path = (*parent_path, field_key)
        field_facts.append(
            FieldFact(
                object_key=object_key,
                field_key=field_key,
                path=current_path,
                value=statement.value,
                object_occurrence=object_occurrence,
                field_occurrence=field_occurrence,
            )
        )
        if isinstance(statement.value, AstBlock) and statement.value.is_object_like:
            field_facts.extend(
                _collect_field_facts_recursive(
                    object_key=object_key,
                    object_occurrence=object_occurrence,
                    block=statement.value,
                    parent_path=current_path,
                )
            )
    return tuple(field_facts)
