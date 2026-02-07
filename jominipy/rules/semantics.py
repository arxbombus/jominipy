"""Semantic extraction over normalized rules IR."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from jominipy.rules.ir import RuleStatement
from jominipy.rules.load import load_rules_paths

_SIMPLE_FIELD_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
