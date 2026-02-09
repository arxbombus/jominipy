"""CWTools semantics adapters over normalized rule/schema artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from types import MappingProxyType
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


@dataclass(frozen=True, slots=True)
class LinkDefinition:
    """Normalized link definition from special-file `links` section."""

    name: str
    output_scope: str | None = None
    input_scopes: tuple[str, ...] = ()
    prefix: str | None = None
    from_data: bool = False
    data_sources: tuple[str, ...] = ()
    link_type: str | None = None


@dataclass(frozen=True, slots=True)
class ModifierDefinition:
    """Normalized modifier definition from special-file `modifiers` section."""

    name: str
    category: str | None = None
    supported_scopes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LocalisationCommandDefinition:
    """Normalized command definition from special-file `localisation_commands` section."""

    name: str
    supported_scopes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TypeLocalisationTemplate:
    """Normalized type-localisation template declaration."""

    template: str
    required: bool = False
    subtype_name: str | None = None


@dataclass(frozen=True, slots=True)
class AliasDefinition:
    """Normalized alias declaration (`alias[family:name]`)."""

    family: str
    name: str
    value_specs: tuple[RuleValueSpec, ...]
    field_constraints: Mapping[str, RuleFieldConstraint]


@dataclass(frozen=True, slots=True)
class AliasInvocation:
    """Invocation site where dynamic alias keys are accepted."""

    family: str
    parent_path: tuple[str, ...]
    required_subtype: str | None = None


@dataclass(frozen=True, slots=True)
class SingleAliasDefinition:
    """Normalized single-alias declaration (`single_alias[...]`)."""

    name: str
    value_specs: tuple[RuleValueSpec, ...]
    field_constraints: Mapping[str, RuleFieldConstraint]


@dataclass(frozen=True, slots=True)
class SingleAliasInvocation:
    """Invocation site where a single-alias should apply."""

    alias_name: str
    field_path: tuple[str, ...]
    required_subtype: str | None = None


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
                comparison=constraint.comparison,
                error_if_only_match=constraint.error_if_only_match,
                outgoing_reference_label=constraint.outgoing_reference_label,
                incoming_reference_label=constraint.incoming_reference_label,
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


def build_values_memberships_by_key(schema: RuleSchemaGraph) -> dict[str, frozenset[str]]:
    """Build memberships from special-file `values` section (`value[key] = { ... }`)."""
    memberships: dict[str, set[str]] = {}
    for section in schema.sections_by_key.get("values", ()):
        statement = section.statement
        if statement.value.kind != "block":
            continue
        for child in statement.value.block:
            if child.kind != "key_value" or child.key is None:
                continue
            parsed = _parse_bracket_key(child.key, expected_family="value")
            if parsed is None:
                continue
            value_key = parsed
            if child.value.kind != "block":
                continue
            bucket = memberships.setdefault(value_key, set())
            for leaf in child.value.block:
                if leaf.kind != "value" or leaf.value.kind != "scalar":
                    continue
                raw = (leaf.value.text or "").strip().strip('"')
                if raw:
                    bucket.add(raw)
    return {key: frozenset(values) for key, values in memberships.items()}


def build_link_definitions(schema: RuleSchemaGraph) -> dict[str, LinkDefinition]:
    """Build link definitions from special-file `links` section."""
    links: dict[str, LinkDefinition] = {}
    for section in schema.sections_by_key.get("links", ()):
        statement = section.statement
        if statement.value.kind != "block":
            continue
        for child in statement.value.block:
            if child.kind != "key_value" or child.key is None:
                continue
            name = child.key.strip()
            if not name or child.value.kind != "block":
                continue
            (
                output_scope,
                input_scopes,
                prefix,
                from_data,
                data_sources,
                link_type,
            ) = _collect_link_options(child.value.block)
            links[name] = LinkDefinition(
                name=name,
                output_scope=output_scope,
                input_scopes=input_scopes,
                prefix=prefix,
                from_data=from_data,
                data_sources=data_sources,
                link_type=link_type,
            )
    return links


def build_modifier_definitions(schema: RuleSchemaGraph) -> dict[str, ModifierDefinition]:
    """Build modifier definitions from `modifiers` and `modifier_categories` sections."""
    supported_scopes_by_category = _collect_modifier_category_scopes(schema)
    modifiers: dict[str, ModifierDefinition] = {}
    for section in schema.sections_by_key.get("modifiers", ()):
        statement = section.statement
        if statement.value.kind != "block":
            continue
        for child in statement.value.block:
            if child.kind != "key_value" or child.key is None:
                continue
            name = child.key.strip()
            if not name:
                continue
            category = None
            if child.value.kind == "scalar":
                raw_category = (child.value.text or "").strip().strip('"')
                if raw_category:
                    category = raw_category
            scopes = tuple(scope.lower() for scope in supported_scopes_by_category.get(category or "", ()))
            modifiers[name] = ModifierDefinition(name=name, category=category, supported_scopes=scopes)
    return modifiers


def build_localisation_command_definitions(
    schema: RuleSchemaGraph,
) -> dict[str, LocalisationCommandDefinition]:
    """Build localisation command definitions from `localisation_commands` section."""
    commands: dict[str, LocalisationCommandDefinition] = {}
    for section in schema.sections_by_key.get("localisation_commands", ()):
        statement = section.statement
        if statement.value.kind != "block":
            continue
        for child in statement.value.block:
            if child.kind != "key_value" or child.key is None:
                continue
            name = child.key.strip()
            if not name:
                continue
            scopes = _extract_scope_list(child)
            if not scopes:
                scopes = ("any",)
            commands[name] = LocalisationCommandDefinition(
                name=name,
                supported_scopes=tuple(scope.lower() for scope in scopes),
            )
    return commands


def build_type_localisation_templates_by_type(
    schema: RuleSchemaGraph,
) -> dict[str, tuple[TypeLocalisationTemplate, ...]]:
    """Build per-type localisation templates from `type[...]` declarations."""
    templates_by_type: dict[str, list[TypeLocalisationTemplate]] = {}
    for type_key, declarations in schema.types_by_key.items():
        bucket = templates_by_type.setdefault(type_key, [])
        for declaration in declarations:
            statement = declaration.statement
            if statement.value.kind != "block":
                continue
            for child in statement.value.block:
                if child.kind != "key_value" or child.key != "localisation":
                    continue
                if child.value.kind != "block":
                    continue
                bucket.extend(_collect_type_localisation_templates(child.value.block))
    return {type_key: tuple(templates) for type_key, templates in templates_by_type.items() if templates}


def build_alias_definitions_by_family(
    schema: RuleSchemaGraph,
) -> dict[str, Mapping[str, AliasDefinition]]:
    """Build alias definitions grouped by family then alias name."""
    by_family: dict[str, dict[str, AliasDefinition]] = {}
    for raw_alias_name, declarations in schema.aliases_by_key.items():
        if ":" not in raw_alias_name:
            continue
        family, declared_name = (part.strip() for part in raw_alias_name.split(":", 1))
        if not family:
            continue
        bucket = by_family.setdefault(family, {})
        for declaration in declarations:
            name_raw = (declaration.argument or declared_name).strip()
            name = name_raw.split(":", 1)[1].strip() if ":" in name_raw else name_raw
            if not name:
                continue
            statement = declaration.statement
            value_specs = extract_value_specs(statement.value)
            field_constraints = (
                _build_constraints_from_rule_block(
                    statement.value.block,
                    single_alias_constraints={},
                )
                if statement.value.kind == "block"
                else {}
            )
            existing = bucket.get(name)
            if existing is None:
                bucket[name] = AliasDefinition(
                    family=family,
                    name=name,
                    value_specs=value_specs,
                    field_constraints=MappingProxyType(field_constraints),
                )
                continue
            merged_fields = _merge_field_constraints(existing.field_constraints, field_constraints)
            bucket[name] = AliasDefinition(
                family=family,
                name=name,
                value_specs=_merge_specs(existing.value_specs, value_specs),
                field_constraints=MappingProxyType(merged_fields),
            )
    return {
        family: MappingProxyType(definitions)
        for family, definitions in by_family.items()
        if definitions
    }


def build_single_alias_definitions(
    schema: RuleSchemaGraph,
) -> dict[str, SingleAliasDefinition]:
    """Build single-alias definitions by alias name."""
    definitions: dict[str, SingleAliasDefinition] = {}
    for alias_name, declarations in schema.single_aliases_by_key.items():
        merged_specs: tuple[RuleValueSpec, ...] = ()
        merged_fields: dict[str, RuleFieldConstraint] = {}
        for declaration in declarations:
            statement = declaration.statement
            merged_specs = _merge_specs(merged_specs, extract_value_specs(statement.value))
            if statement.value.kind == "block":
                merged_fields = _merge_field_constraints(
                    merged_fields,
                    _build_constraints_from_rule_block(
                        statement.value.block,
                        single_alias_constraints={},
                    ),
                )
        if merged_specs or merged_fields:
            definitions[alias_name] = SingleAliasDefinition(
                name=alias_name,
                value_specs=merged_specs,
                field_constraints=MappingProxyType(merged_fields),
            )
    return definitions


def build_alias_invocations_by_object(schema: RuleSchemaGraph) -> dict[str, tuple[AliasInvocation, ...]]:
    """Build alias invocation paths from top-level rule declarations."""
    invocations: dict[str, list[AliasInvocation]] = {}
    for statement in schema.top_level_rule_statements:
        object_key = statement.key
        if object_key is None or statement.value.kind != "block":
            continue
        bucket = invocations.setdefault(object_key, [])
        _collect_alias_invocations(
            statement.value.block,
            path=(object_key,),
            output=bucket,
        )
    return {
        object_key: tuple(_dedupe_alias_invocations(items))
        for object_key, items in invocations.items()
        if items
    }


def build_single_alias_invocations_by_object(
    schema: RuleSchemaGraph,
) -> dict[str, tuple[SingleAliasInvocation, ...]]:
    """Build single-alias invocation paths from top-level rule declarations."""
    invocations: dict[str, list[SingleAliasInvocation]] = {}
    for statement in schema.top_level_rule_statements:
        object_key = statement.key
        if object_key is None or statement.value.kind != "block":
            continue
        bucket = invocations.setdefault(object_key, [])
        _collect_single_alias_invocations(
            statement.value.block,
            path=(object_key,),
            output=bucket,
        )
    return {
        object_key: tuple(_dedupe_single_alias_invocations(items))
        for object_key, items in invocations.items()
        if items
    }


@lru_cache(maxsize=1)
def load_hoi4_values_memberships_by_key() -> dict[str, frozenset[str]]:
    """Load special-file values memberships from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_values_memberships_by_key(schema)


@lru_cache(maxsize=1)
def load_hoi4_link_definitions() -> dict[str, LinkDefinition]:
    """Load special-file link definitions from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_link_definitions(schema)


@lru_cache(maxsize=1)
def load_hoi4_modifier_definitions() -> dict[str, ModifierDefinition]:
    """Load special-file modifier definitions from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_modifier_definitions(schema)


@lru_cache(maxsize=1)
def load_hoi4_localisation_command_definitions() -> dict[str, LocalisationCommandDefinition]:
    """Load special-file localisation command definitions from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_localisation_command_definitions(schema)


@lru_cache(maxsize=1)
def load_hoi4_type_localisation_templates_by_type() -> dict[str, tuple[TypeLocalisationTemplate, ...]]:
    """Load per-type localisation templates from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_type_localisation_templates_by_type(schema)


@lru_cache(maxsize=1)
def load_hoi4_alias_definitions_by_family() -> dict[str, Mapping[str, AliasDefinition]]:
    """Load alias definitions grouped by family/name from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_alias_definitions_by_family(schema)


@lru_cache(maxsize=1)
def load_hoi4_alias_invocations_by_object() -> dict[str, tuple[AliasInvocation, ...]]:
    """Load alias invocation paths grouped by top-level object from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_alias_invocations_by_object(schema)


@lru_cache(maxsize=1)
def load_hoi4_single_alias_definitions() -> dict[str, SingleAliasDefinition]:
    """Load single-alias definitions by alias name from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_single_alias_definitions(schema)


@lru_cache(maxsize=1)
def load_hoi4_single_alias_invocations_by_object() -> dict[str, tuple[SingleAliasInvocation, ...]]:
    """Load single-alias invocation paths grouped by top-level object from HOI4 schema."""
    schema = load_hoi4_schema_graph()
    return build_single_alias_invocations_by_object(schema)


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


def _collect_type_localisation_templates(
    statements: tuple[RuleStatement, ...],
    *,
    subtype_name: str | None = None,
) -> tuple[TypeLocalisationTemplate, ...]:
    templates: list[TypeLocalisationTemplate] = []
    seen: set[tuple[str, bool, str | None]] = set()
    for statement in statements:
        if statement.kind != "key_value" or statement.key is None:
            continue
        nested_subtype = _subtype_name(statement.key)
        if nested_subtype is not None and statement.value.kind == "block":
            for item in _collect_type_localisation_templates(
                statement.value.block,
                subtype_name=nested_subtype,
            ):
                dedupe = (item.template, item.required, item.subtype_name)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                templates.append(item)
            continue
        if statement.value.kind != "scalar":
            continue
        template = (statement.value.text or "").strip().strip('"')
        if not template or "$" not in template:
            continue
        required = any(flag.lower() == "required" for flag in statement.metadata.flags)
        item = TypeLocalisationTemplate(template=template, required=required, subtype_name=subtype_name)
        dedupe = (item.template, item.required, item.subtype_name)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        templates.append(item)
    return tuple(templates)


def _collect_alias_invocations(
    statements: tuple[RuleStatement, ...],
    *,
    path: tuple[str, ...],
    output: list[AliasInvocation],
    subtype_name: str | None = None,
) -> None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key is None:
            continue
        family = _parse_bracket_key(statement.key, expected_family="alias_name")
        if family is not None:
            specs = extract_value_specs(statement.value)
            if any(
                spec.kind == "alias_match_left_ref" and (spec.argument or "").strip() == family
                for spec in specs
            ):
                output.append(
                    AliasInvocation(
                        family=family,
                        parent_path=path,
                        required_subtype=subtype_name,
                    )
                )
        child_path = (*path, statement.key)
        if statement.value.kind == "block":
            nested_subtype = _subtype_name(statement.key)
            _collect_alias_invocations(
                statement.value.block,
                path=child_path,
                output=output,
                subtype_name=nested_subtype if nested_subtype is not None else subtype_name,
            )


def _collect_single_alias_invocations(
    statements: tuple[RuleStatement, ...],
    *,
    path: tuple[str, ...],
    output: list[SingleAliasInvocation],
    subtype_name: str | None = None,
) -> None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key is None:
            continue
        child_path = (*path, statement.key)
        specs = extract_value_specs(statement.value)
        for spec in specs:
            if spec.kind != "single_alias_ref":
                continue
            alias_name = (spec.argument or "").strip()
            if not alias_name:
                continue
            output.append(
                SingleAliasInvocation(
                    alias_name=alias_name,
                    field_path=child_path,
                    required_subtype=subtype_name,
                )
            )
        if statement.value.kind == "block":
            nested_subtype = _subtype_name(statement.key)
            _collect_single_alias_invocations(
                statement.value.block,
                path=child_path,
                output=output,
                subtype_name=nested_subtype if nested_subtype is not None else subtype_name,
            )


def _merge_field_constraints(
    left: Mapping[str, RuleFieldConstraint],
    right: Mapping[str, RuleFieldConstraint],
) -> dict[str, RuleFieldConstraint]:
    merged = dict(left)
    for field_name, constraint in right.items():
        existing = merged.get(field_name)
        if existing is None:
            merged[field_name] = constraint
            continue
        merged[field_name] = RuleFieldConstraint(
            required=existing.required or constraint.required,
            value_specs=_merge_specs(existing.value_specs, constraint.value_specs),
            comparison=existing.comparison or constraint.comparison,
            error_if_only_match=existing.error_if_only_match or constraint.error_if_only_match,
            outgoing_reference_label=existing.outgoing_reference_label or constraint.outgoing_reference_label,
            incoming_reference_label=existing.incoming_reference_label or constraint.incoming_reference_label,
        )
    return merged


def _dedupe_alias_invocations(
    invocations: list[AliasInvocation],
) -> list[AliasInvocation]:
    deduped: list[AliasInvocation] = []
    seen: set[tuple[str, tuple[str, ...], str | None]] = set()
    for invocation in invocations:
        key = (invocation.family, invocation.parent_path, invocation.required_subtype)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(invocation)
    return deduped


def _dedupe_single_alias_invocations(
    invocations: list[SingleAliasInvocation],
) -> list[SingleAliasInvocation]:
    deduped: list[SingleAliasInvocation] = []
    seen: set[tuple[str, tuple[str, ...], str | None]] = set()
    for invocation in invocations:
        key = (
            invocation.alias_name,
            invocation.field_path,
            invocation.required_subtype,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(invocation)
    return deduped


def _collect_modifier_category_scopes(schema: RuleSchemaGraph) -> dict[str, tuple[str, ...]]:
    scopes_by_category: dict[str, tuple[str, ...]] = {}
    for section in schema.sections_by_key.get("modifier_categories", ()):
        statement = section.statement
        if statement.value.kind != "block":
            continue
        for category_entry in statement.value.block:
            if category_entry.kind != "key_value" or category_entry.key is None:
                continue
            category = category_entry.key.strip()
            if not category or category_entry.value.kind != "block":
                continue
            scopes: tuple[str, ...] = ()
            for child in category_entry.value.block:
                if child.kind != "key_value" or child.key != "supported_scopes":
                    continue
                scopes = _extract_scope_list(child)
                break
            scopes_by_category[category] = scopes
    return scopes_by_category


def _collect_link_options(
    statements: tuple[RuleStatement, ...],
) -> tuple[str | None, tuple[str, ...], str | None, bool, tuple[str, ...], str | None]:
    output_scope = _find_scalar_child(statements, "output_scope")
    prefix = _find_scalar_child(statements, "prefix")
    link_type = _find_scalar_child(statements, "type")
    from_data = (_find_scalar_child(statements, "from_data") or "").lower() == "yes"
    data_sources: list[str] = []
    input_scopes: tuple[str, ...] = ()
    for statement in statements:
        if statement.kind != "key_value" or statement.key is None:
            continue
        if statement.key == "data_source" and statement.value.kind == "scalar":
            raw = (statement.value.text or "").strip()
            if raw:
                data_sources.append(raw)
            continue
        if statement.key == "input_scopes":
            input_scopes = _extract_scope_list(statement)
    return (
        output_scope.lower() if output_scope else None,
        tuple(scope.lower() for scope in input_scopes),
        prefix,
        from_data,
        tuple(data_sources),
        link_type.lower() if link_type else None,
    )


def _extract_scope_list(statement: RuleStatement) -> tuple[str, ...]:
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


def _find_block_child(statements: tuple[RuleStatement, ...], key: str) -> RuleStatement | None:
    for statement in statements:
        if statement.kind != "key_value" or statement.key != key:
            continue
        if statement.value.kind != "block":
            continue
        return statement
    return None


def _parse_bracket_key(raw_key: str, *, expected_family: str) -> str | None:
    prefix = f"{expected_family}["
    if not raw_key.startswith(prefix) or not raw_key.endswith("]"):
        return None
    inner = raw_key[len(prefix) : -1].strip()
    return inner or None


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
            value_specs=_merge_specs(existing.value_specs, specs),
            comparison=existing.comparison or child.metadata.comparison,
            error_if_only_match=existing.error_if_only_match or child.metadata.error_if_only_match,
            outgoing_reference_label=existing.outgoing_reference_label or child.metadata.outgoing_reference_label,
            incoming_reference_label=existing.incoming_reference_label or child.metadata.incoming_reference_label,
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
