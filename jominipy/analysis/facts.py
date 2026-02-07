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
class AnalysisFacts:
    """Facts extracted once from AST and reused by multiple engines."""

    top_level_values: dict[str, tuple[object | None, ...]]
    top_level_shapes: dict[str, frozenset[ValueShape]]


def build_analysis_facts(source_file: AstSourceFile) -> AnalysisFacts:
    values: dict[str, list[object | None]] = {}
    shapes: dict[str, set[ValueShape]] = {}

    for statement in source_file.statements:
        if not isinstance(statement, AstKeyValue):
            continue
        key = statement.key.raw_text
        value = statement.value
        values.setdefault(key, []).append(value)
        shapes.setdefault(key, set()).add(_shape_for_value(value))

    frozen_values = {key: tuple(group) for key, group in values.items()}
    frozen_shapes = {key: frozenset(group) for key, group in shapes.items()}
    return AnalysisFacts(top_level_values=frozen_values, top_level_shapes=frozen_shapes)


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
