"""CWTools semantics adapters over normalized rule/schema artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Mapping

from jominipy.ast import AstBlock, AstKeyValue
from jominipy.parser import parse_result
from jominipy.rules.ir import RuleStatement
from jominipy.rules.schema_graph import RuleSchemaGraph, load_hoi4_schema_graph
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    build_field_constraints_by_object,
    extract_value_specs,
)


@dataclass(frozen=True, slots=True)
class ExpandedFieldConstraints:
    """Field constraints after semantic adapter expansion steps."""

    by_object: dict[str, dict[str, RuleFieldConstraint]]


@dataclass(frozen=True, slots=True)
class SubtypeMatcher:
    """Subtype matcher extracted from `type[...]` subtype declarations."""

    subtype_name: str
    expected_field_values: tuple[tuple[str, str], ...] = ()


_SUBTYPE_PATTERN = re.compile(r"^subtype\[(?P<name>[^\]]+)\]$")


@dataclass(frozen=True, slots=True)
class NameTreePattern:
    """Pattern node for complex enum name-tree traversal."""

    matcher: str
    wildcard: bool
    terminal: bool
    children: tuple[NameTreePattern, ...] = ()


@dataclass(frozen=True, slots=True)
class ComplexEnumDefinition:
    """Normalized `complex_enum[...]` definition."""

    enum_key: str
    path: str | None
    path_file: str | None
    path_extension: str | None
    start_from_root: bool
    patterns: tuple[NameTreePattern, ...]


def build_alias_members_by_family(schema: RuleSchemaGraph) -> dict[str, frozenset[str]]:
    """Build alias-family membership maps from `alias[family:name]` declarations."""
    aliases: dict[str, set[str]] = {}
    for raw_name in schema.aliases_by_key:
        if ":" not in raw_name:
            continue
        family, alias_name = raw_name.split(":", 1)
        family = family.strip()
        alias_name = alias_name.strip()
        if not family or not alias_name:
            continue
        aliases.setdefault(family, set()).add(alias_name)
    return {family: frozenset(names) for family, names in aliases.items()}


def build_expanded_field_constraints(
    schema: RuleSchemaGraph,
    *,
    include_implicit_required: bool = False,
) -> ExpandedFieldConstraints:
    """Build field constraints and apply single-alias expansion."""
    base = build_field_constraints_by_object(
        schema.top_level_rule_statements,
        include_implicit_required=include_implicit_required,
    )
    single_alias_constraints = _collect_single_alias_constraints(schema)
    expanded: dict[str, dict[str, RuleFieldConstraint]] = {}
    for object_key, by_field in base.items():
        expanded_fields: dict[str, RuleFieldConstraint] = {}
        for field_name, constraint in by_field.items():
            expanded_specs = _expand_single_alias_specs(
                constraint.value_specs,
                single_alias_constraints=single_alias_constraints,
            )
            expanded_fields[field_name] = RuleFieldConstraint(
                required=constraint.required,
                value_specs=expanded_specs,
            )
        expanded[object_key] = expanded_fields
    return ExpandedFieldConstraints(by_object=expanded)


@lru_cache(maxsize=1)
def load_hoi4_alias_members_by_family() -> dict[str, frozenset[str]]:
    """Load alias-family memberships from HOI4 schema graph."""
    schema = load_hoi4_schema_graph()
    return build_alias_members_by_family(schema)


@lru_cache(maxsize=1)
def load_hoi4_expanded_field_constraints(
    *,
    include_implicit_required: bool = False,
) -> dict[str, dict[str, RuleFieldConstraint]]:
    """Load HOI4 field constraints with semantic adapter expansions applied."""
    schema = load_hoi4_schema_graph()
    if not schema.top_level_rule_statements:
        return {}
    return build_expanded_field_constraints(
        schema,
        include_implicit_required=include_implicit_required,
    ).by_object


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


def build_complex_enum_definitions(schema: RuleSchemaGraph) -> dict[str, tuple[ComplexEnumDefinition, ...]]:
    """Build complex enum definitions from schema graph."""
    definitions: dict[str, list[ComplexEnumDefinition]] = {}
    for declaration in schema.by_category.get("complex_enum", ()):
        if declaration.argument is None:
            continue
        statement = declaration.statement
        if statement.value.kind != "block":
            continue
        path = _find_scalar_child(statement.value.block, "path")
        path_file = _find_scalar_child(statement.value.block, "path_file")
        path_extension = _find_scalar_child(statement.value.block, "path_extension")
        start_from_root = _find_scalar_child(statement.value.block, "start_from_root") == "yes"
        name_node = _find_block_child(statement.value.block, "name")
        if name_node is None:
            continue
        patterns = tuple(
            pattern
            for child in name_node.value.block
            if (pattern := _build_name_tree_pattern(child)) is not None
        )
        if not patterns:
            continue
        definitions.setdefault(declaration.argument, []).append(
            ComplexEnumDefinition(
                enum_key=declaration.argument,
                path=path,
                path_file=path_file,
                path_extension=path_extension,
                start_from_root=start_from_root,
                patterns=patterns,
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
                bucket.append(
                    SubtypeMatcher(
                        subtype_name=subtype_name,
                        expected_field_values=expected,
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
            subtype_fields = _build_constraints_from_rule_block(
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
            merged = _merge_specs(merged, specs)
        if merged:
            aliases[alias_name] = RuleFieldConstraint(required=False, value_specs=merged)
    return aliases


def _find_scalar_child(statements: tuple[RuleStatement, ...], key: str) -> str | None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key != key:
            continue
        if statement.value.kind != "scalar":
            continue
        return (statement.value.text or "").strip().strip('"')
    return None


def _find_block_child(statements: tuple[RuleStatement, ...], key: str) -> RuleStatement | None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key != key:
            continue
        if statement.value.kind != "block":
            continue
        return statement
    return None


def _build_name_tree_pattern(statement: RuleStatement) -> NameTreePattern | None:
    if statement.kind != "key_value" or statement.key is None:
        return None
    raw_matcher = statement.key.strip()
    lowered = raw_matcher.lower()
    wildcard = lowered in {"scalar", "enum_name"}
    matcher = "*" if wildcard else raw_matcher
    terminal = lowered == "enum_name"
    if statement.value.kind == "scalar":
        terminal = terminal or (statement.value.text or "").strip().lower() == "enum_name"
        return NameTreePattern(matcher=matcher, wildcard=wildcard, terminal=terminal)
    if statement.value.kind != "block":
        return NameTreePattern(matcher=matcher, wildcard=wildcard, terminal=terminal)
    children = tuple(
        child_pattern
        for child in statement.value.block
        if (child_pattern := _build_name_tree_pattern(child)) is not None
    )
    return NameTreePattern(
        matcher=matcher,
        wildcard=wildcard,
        terminal=terminal,
        children=children,
    )


def _matches_complex_enum_path(*, file_path: str, definition: ComplexEnumDefinition) -> bool:
    if definition.path_file is not None and _basename(file_path) != _basename(definition.path_file):
        return False
    if definition.path_extension is not None and not file_path.endswith(definition.path_extension):
        return False
    if definition.path is None:
        return True
    declared = _normalize_path(definition.path)
    if declared.startswith("game/"):
        declared = declared[len("game/") :]
    declared = declared.rstrip("/")
    if not declared:
        return True
    return file_path == declared or file_path.startswith(f"{declared}/")


def _extract_complex_enum_values_from_text(*, text: str, definition: ComplexEnumDefinition) -> set[str]:
    parsed = parse_result(text)
    root = parsed.ast_root()
    top_level = [statement for statement in root.statements if isinstance(statement, AstKeyValue)]
    values: set[str] = set()
    if definition.start_from_root:
        for pattern in definition.patterns:
            values.update(_walk_patterns_in_children(top_level, pattern))
        return values
    for candidate in top_level:
        for pattern in definition.patterns:
            values.update(_walk_name_tree(candidate, pattern))
    return values


def _walk_name_tree(node: AstKeyValue, pattern: NameTreePattern) -> set[str]:
    values: set[str] = set()
    children = _ast_child_key_values(node)
    matches = _matching_children(children, pattern)
    for match in matches:
        if pattern.terminal:
            raw = match.key.raw_text.strip()
            if raw:
                values.add(raw)
        for child_pattern in pattern.children:
            values.update(_walk_name_tree(match, child_pattern))
    return values


def _walk_patterns_in_children(children: list[AstKeyValue], pattern: NameTreePattern) -> set[str]:
    values: set[str] = set()
    matches = _matching_children(children, pattern)
    for match in matches:
        if pattern.terminal:
            raw = match.key.raw_text.strip()
            if raw:
                values.add(raw)
        for child_pattern in pattern.children:
            values.update(_walk_name_tree(match, child_pattern))
    return values


def _matching_children(children: list[AstKeyValue], pattern: NameTreePattern) -> list[AstKeyValue]:
    return [child for child in children if pattern.wildcard or child.key.raw_text == pattern.matcher]


def _ast_child_key_values(node: AstKeyValue) -> list[AstKeyValue]:
    if not isinstance(node.value, AstBlock):
        return []
    if not node.value.is_object_like:
        return []
    return [statement for statement in node.value.statements if isinstance(statement, AstKeyValue)]


def _basename(path: str) -> str:
    normalized = _normalize_path(path).rstrip("/")
    if "/" not in normalized:
        return normalized
    return normalized.rsplit("/", 1)[1]


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _build_constraints_from_rule_block(
    statements: tuple[RuleStatement, ...],
    *,
    single_alias_constraints: dict[str, RuleFieldConstraint],
) -> dict[str, RuleFieldConstraint]:
    by_field: dict[str, RuleFieldConstraint] = {}
    for child in statements:
        if child.kind != "key_value" or child.key is None:
            continue
        required = _is_required(child)
        specs = _expand_single_alias_specs(
            extract_value_specs(child.value),
            single_alias_constraints=single_alias_constraints,
        )
        existing = by_field.get(child.key)
        if existing is None:
            by_field[child.key] = RuleFieldConstraint(required=required, value_specs=specs)
            continue
        by_field[child.key] = RuleFieldConstraint(
            required=existing.required or required,
            value_specs=_merge_specs(existing.value_specs, specs),
        )
    return by_field


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


def _is_required(statement: RuleStatement) -> bool:
    cardinality = statement.metadata.cardinality
    if cardinality is None:
        return False
    if cardinality.minimum_unbounded:
        return True
    return bool(cardinality.minimum is not None and cardinality.minimum > 0)


def _expand_single_alias_specs(
    specs: tuple[RuleValueSpec, ...],
    *,
    single_alias_constraints: dict[str, RuleFieldConstraint],
) -> tuple[RuleValueSpec, ...]:
    expanded: tuple[RuleValueSpec, ...] = ()
    for spec in specs:
        if spec.kind != "single_alias_ref":
            expanded = _merge_specs(expanded, (spec,))
            continue
        alias_name = (spec.argument or "").strip()
        alias_constraint = single_alias_constraints.get(alias_name)
        if alias_constraint is None:
            expanded = _merge_specs(expanded, (spec,))
            continue
        expanded = _merge_specs(expanded, alias_constraint.value_specs)
    return expanded


def _merge_specs(
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
