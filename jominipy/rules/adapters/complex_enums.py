from __future__ import annotations

from functools import lru_cache
from typing import Mapping

from jominipy.ast import AstBlock, AstKeyValue, AstScalar, AstStatement
from jominipy.parser import parse_result
from jominipy.rules.adapters.common import (
    find_block_child,
    find_scalar_child,
    find_scalar_children,
)
from jominipy.rules.adapters.models import ComplexEnumDefinition
from jominipy.rules.ir import RuleStatement
from jominipy.rules.schema_graph import RuleSchemaGraph, load_hoi4_schema_graph


def build_complex_enum_definitions(schema: RuleSchemaGraph) -> dict[str, tuple[ComplexEnumDefinition, ...]]:
    """Build complex enum definitions from schema graph."""
    definitions: dict[str, list[ComplexEnumDefinition]] = {}
    for declaration in schema.by_category.get("complex_enum", ()):
        if declaration.argument is None:
            continue
        statement = declaration.statement
        if statement.value.kind != "block":
            continue
        paths = tuple(path for path in find_scalar_children(statement.value.block, "path") if path)
        path_strict = find_scalar_child(statement.value.block, "path_strict") == "yes"
        path_file = find_scalar_child(statement.value.block, "path_file")
        path_extension = find_scalar_child(statement.value.block, "path_extension")
        start_from_root = find_scalar_child(statement.value.block, "start_from_root") == "yes"
        name_node = find_block_child(statement.value.block, "name")
        if name_node is None:
            continue
        if not name_node.value.block:
            continue
        definitions.setdefault(declaration.argument, []).append(
            ComplexEnumDefinition(
                enum_key=declaration.argument,
                paths=paths,
                path_strict=path_strict,
                path_file=path_file,
                path_extension=path_extension,
                start_from_root=start_from_root,
                name_tree=name_node.value.block,
            )
        )
    return {key: tuple(items) for key, items in definitions.items()}


def build_complex_enum_values_from_file_texts(
    *,
    file_texts_by_path: Mapping[str, str],
    definitions_by_key: Mapping[str, tuple[ComplexEnumDefinition, ...]],
) -> dict[str, frozenset[str]]:
    """Materialize complex enum values by scanning project file texts."""
    values: dict[str, set[str]] = {}
    normalized_files = {_normalize_path(path): text for path, text in file_texts_by_path.items()}
    for enum_key, definitions in definitions_by_key.items():
        bucket = values.setdefault(enum_key, set())
        for definition in definitions:
            for file_path, text in normalized_files.items():
                if not _matches_complex_enum_path(file_path=file_path, definition=definition):
                    continue
                bucket.update(_extract_complex_enum_values_from_text(text=text, definition=definition))
    return {key: frozenset(items) for key, items in values.items() if items}


@lru_cache(maxsize=1)
def load_hoi4_complex_enum_definitions() -> dict[str, tuple[ComplexEnumDefinition, ...]]:
    """Load HOI4 complex enum definitions."""
    schema = load_hoi4_schema_graph()
    return build_complex_enum_definitions(schema)


def _matches_complex_enum_path(*, file_path: str, definition: ComplexEnumDefinition) -> bool:
    if definition.path_file is not None and _basename(file_path) != _basename(definition.path_file):
        return False
    if definition.path_extension is not None and not file_path.endswith(definition.path_extension):
        return False
    if not definition.paths:
        return True
    normalized_file = _normalize_path(file_path)
    file_dir = _dirname(normalized_file)
    for raw_declared in definition.paths:
        declared = _normalize_path(raw_declared)
        if declared.startswith("game/"):
            declared = declared[len("game/") :]
        declared = declared.rstrip("/")
        if not declared:
            return True
        if definition.path_strict:
            if file_dir == declared:
                return True
            continue
        if normalized_file == declared or normalized_file.startswith(f"{declared}/"):
            return True
    return False


def _extract_complex_enum_values_from_text(*, text: str, definition: ComplexEnumDefinition) -> set[str]:
    parsed = parse_result(text)
    root = parsed.ast_root()
    if definition.start_from_root:
        return _extract_complex_enum_values_in_clause(statements=root.statements, name_tree=definition.name_tree)
    values: set[str] = set()
    for statement in root.statements:
        if not isinstance(statement, AstKeyValue):
            continue
        if not isinstance(statement.value, AstBlock):
            continue
        values.update(
            _extract_complex_enum_values_in_clause(
                statements=statement.value.statements,
                name_tree=definition.name_tree,
            )
        )
    return values


def _extract_complex_enum_values_in_clause(
    *,
    statements: tuple[AstStatement, ...],
    name_tree: tuple[RuleStatement, ...],
) -> set[str]:
    values: set[str] = set()
    key_values = _ast_clause_key_values(statements)

    for enumtree_node in name_tree:
        if enumtree_node.kind != "key_value" or enumtree_node.key is None:
            continue
        if enumtree_node.value.kind != "block":
            continue
        lowered = enumtree_node.key.strip().lower()
        wildcard = lowered in {"scalar", "enum_name", "name"}
        if lowered == "enum_name":
            for candidate in key_values:
                raw = candidate.key.raw_text.strip()
                if raw:
                    values.add(raw)
        candidate_nodes = (
            key_values
            if wildcard
            else [candidate for candidate in key_values if candidate.key.raw_text.lower() == lowered]
        )
        for candidate in candidate_nodes:
            if not isinstance(candidate.value, AstBlock):
                continue
            values.update(
                _extract_complex_enum_values_in_clause(
                    statements=candidate.value.statements,
                    name_tree=enumtree_node.value.block,
                )
            )

    if any(_is_enum_name_leaf_value(statement) for statement in name_tree):
        for scalar in _ast_clause_scalars(statements):
            raw = _normalize_scalar_text(scalar.raw_text)
            if raw:
                values.add(raw)

    leaf_terminal = _first_leaf_with_enum_name_value(name_tree)
    if leaf_terminal is not None:
        leaf_key = leaf_terminal.lower()
        if leaf_key == "scalar":
            for candidate in key_values:
                if isinstance(candidate.value, AstScalar):
                    raw = _normalize_scalar_text(candidate.value.raw_text)
                    if raw:
                        values.add(raw)
        else:
            for candidate in key_values:
                if candidate.key.raw_text.lower() != leaf_key:
                    continue
                if not isinstance(candidate.value, AstScalar):
                    continue
                raw = _normalize_scalar_text(candidate.value.raw_text)
                if raw:
                    values.add(raw)
    else:
        enum_name_leaf = _first_leaf_with_enum_name_key(name_tree)
        if enum_name_leaf is not None:
            if enum_name_leaf.lower() == "scalar":
                for candidate in key_values:
                    raw = candidate.key.raw_text.strip()
                    if raw:
                        values.add(raw)
            else:
                for candidate in key_values:
                    if not isinstance(candidate.value, AstScalar):
                        continue
                    if _normalize_scalar_text(candidate.value.raw_text) != enum_name_leaf:
                        continue
                    raw = candidate.key.raw_text.strip()
                    if raw:
                        values.add(raw)
    return values


def _ast_clause_key_values(statements: tuple[AstStatement, ...]) -> list[AstKeyValue]:
    return [statement for statement in statements if isinstance(statement, AstKeyValue)]


def _ast_clause_scalars(statements: tuple[AstStatement, ...]) -> list[AstScalar]:
    return [statement for statement in statements if isinstance(statement, AstScalar)]


def _is_enum_name_leaf_value(statement: RuleStatement) -> bool:
    if statement.kind != "value" or statement.value.kind != "scalar":
        return False
    return (statement.value.text or "").strip().strip('"').lower() == "enum_name"


def _first_leaf_with_enum_name_value(name_tree: tuple[RuleStatement, ...]) -> str | None:
    for statement in name_tree:
        if statement.kind != "key_value" or statement.key is None:
            continue
        if statement.value.kind != "scalar":
            continue
        if (statement.value.text or "").strip().strip('"').lower() != "enum_name":
            continue
        return statement.key.strip()
    return None


def _first_leaf_with_enum_name_key(name_tree: tuple[RuleStatement, ...]) -> str | None:
    for statement in name_tree:
        if statement.kind != "key_value" or statement.key is None:
            continue
        if statement.key.strip().lower() != "enum_name":
            continue
        if statement.value.kind != "scalar":
            continue
        return (statement.value.text or "").strip().strip('"')
    return None


def _basename(path: str) -> str:
    normalized = _normalize_path(path).rstrip("/")
    if "/" not in normalized:
        return normalized
    return normalized.rsplit("/", 1)[1]


def _dirname(path: str) -> str:
    normalized = _normalize_path(path).rstrip("/")
    if "/" not in normalized:
        return ""
    return normalized.rsplit("/", 1)[0]


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _normalize_scalar_text(raw: str) -> str:
    return raw.strip().strip('"')
