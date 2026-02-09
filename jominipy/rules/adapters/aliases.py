from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType
from typing import Mapping

from jominipy.rules.adapters.common import (
    build_constraints_from_rule_block,
    merge_specs,
    parse_bracket_key,
)
from jominipy.rules.adapters.models import (
    AliasDefinition,
    AliasInvocation,
    ExpandedFieldConstraints,
    SingleAliasDefinition,
    SingleAliasInvocation,
    TypeLocalisationTemplate,
)
from jominipy.rules.ir import RuleStatement
from jominipy.rules.schema_graph import RuleSchemaGraph, load_hoi4_schema_graph
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    build_field_constraints_by_object,
    extract_value_specs,
)


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
                build_constraints_from_rule_block(
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
                value_specs=merge_specs(existing.value_specs, value_specs),
                field_constraints=MappingProxyType(merged_fields),
            )
    return {family: MappingProxyType(definitions) for family, definitions in by_family.items() if definitions}


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
            merged_specs = merge_specs(merged_specs, extract_value_specs(statement.value))
            if statement.value.kind == "block":
                merged_fields = _merge_field_constraints(
                    merged_fields,
                    build_constraints_from_rule_block(
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
    return {object_key: tuple(_dedupe_alias_invocations(items)) for object_key, items in invocations.items() if items}


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
        object_key: tuple(_dedupe_single_alias_invocations(items)) for object_key, items in invocations.items() if items
    }


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
            merged = merge_specs(merged, specs)
        if merged:
            aliases[alias_name] = RuleFieldConstraint(required=False, value_specs=merged)
    return aliases


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
        family = parse_bracket_key(statement.key, expected_family="alias_name")
        if family is not None:
            specs = extract_value_specs(statement.value)
            if any(spec.kind == "alias_match_left_ref" and (spec.argument or "").strip() == family for spec in specs):
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
            value_specs=merge_specs(existing.value_specs, constraint.value_specs),
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


def _subtype_name(key: str | None) -> str | None:
    if key is None:
        return None
    if not key.startswith("subtype[") or not key.endswith("]"):
        return None
    name = key[len("subtype[") : -1].strip()
    return name or None


def _expand_single_alias_specs(
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
