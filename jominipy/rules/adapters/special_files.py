from __future__ import annotations

from functools import lru_cache

from jominipy.rules.adapters.common import (
    extract_scope_list,
    find_scalar_child,
    parse_bracket_key,
)
from jominipy.rules.adapters.models import (
    LinkDefinition,
    LocalisationCommandDefinition,
    ModifierDefinition,
)
from jominipy.rules.ir import RuleStatement
from jominipy.rules.schema_graph import RuleSchemaGraph, load_hoi4_schema_graph


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
            parsed = parse_bracket_key(child.key, expected_family="value")
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
            scopes = extract_scope_list(child)
            if not scopes:
                scopes = ("any",)
            commands[name] = LocalisationCommandDefinition(
                name=name,
                supported_scopes=tuple(scope.lower() for scope in scopes),
            )
    return commands


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
                scopes = extract_scope_list(child)
                break
            scopes_by_category[category] = scopes
    return scopes_by_category


def _collect_link_options(
    statements: tuple[RuleStatement, ...],
) -> tuple[str | None, tuple[str, ...], str | None, bool, tuple[str, ...], str | None]:
    output_scope = find_scalar_child(statements, "output_scope")
    prefix = find_scalar_child(statements, "prefix")
    link_type = find_scalar_child(statements, "type")
    from_data = (find_scalar_child(statements, "from_data") or "").lower() == "yes"
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
            input_scopes = extract_scope_list(statement)
    return (
        output_scope.lower() if output_scope else None,
        tuple(scope.lower() for scope in input_scopes),
        prefix,
        from_data,
        tuple(data_sources),
        link_type.lower() if link_type else None,
    )
