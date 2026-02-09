"""Service and policy wiring for type-check rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

from jominipy.localisation.keys import (
    LocalisationKeyProvider,
    load_localisation_key_provider_from_project_root,
)
from jominipy.rules.adapter import (
    AliasDefinition,
    AliasInvocation,
    LinkDefinition,
    LocalisationCommandDefinition,
    ModifierDefinition,
    SingleAliasDefinition,
    SingleAliasInvocation,
    SubtypeMatcher,
    TypeLocalisationTemplate,
)
from jominipy.rules.semantics import RuleFieldConstraint
from jominipy.typecheck.assets import AssetRegistry, NullAssetRegistry

type UnresolvedPolicy = Literal["defer", "error"]


@dataclass(frozen=True, slots=True)
class TypecheckPolicy:
    """Policy toggles for unresolved checks in type-check rules."""

    unresolved_asset: UnresolvedPolicy = "defer"
    unresolved_reference: UnresolvedPolicy = "defer"
    localisation_coverage: Literal["any", "all"] = "any"
    localisation_required_locales: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class TypecheckServices:
    """Shared resolver/services injected into type-check execution."""

    asset_registry: AssetRegistry = field(default_factory=NullAssetRegistry)
    policy: TypecheckPolicy = field(default_factory=TypecheckPolicy)
    type_memberships_by_key: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    value_memberships_by_key: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    special_value_memberships_by_key: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    known_scopes: frozenset[str] = frozenset()
    enum_memberships_by_key: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    alias_memberships_by_family: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    alias_definitions_by_family: Mapping[str, Mapping[str, AliasDefinition]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    alias_invocations_by_object: Mapping[str, tuple[AliasInvocation, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    single_alias_definitions_by_name: Mapping[str, SingleAliasDefinition] = field(
        default_factory=lambda: MappingProxyType({})
    )
    single_alias_invocations_by_object: Mapping[str, tuple[SingleAliasInvocation, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    link_definitions_by_name: Mapping[str, LinkDefinition] = field(
        default_factory=lambda: MappingProxyType({})
    )
    modifier_definitions_by_name: Mapping[str, ModifierDefinition] = field(
        default_factory=lambda: MappingProxyType({})
    )
    localisation_command_definitions_by_name: Mapping[str, LocalisationCommandDefinition] = field(
        default_factory=lambda: MappingProxyType({})
    )
    type_localisation_templates_by_type: Mapping[str, tuple[TypeLocalisationTemplate, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    localisation_key_provider: LocalisationKeyProvider = field(
        default_factory=LocalisationKeyProvider
    )


def build_typecheck_services_from_file_texts(
    *,
    file_texts_by_path: Mapping[str, str],
    asset_registry: AssetRegistry | None = None,
    policy: TypecheckPolicy | None = None,
) -> TypecheckServices:
    """Build generic type-membership services from schema + project file texts."""
    from jominipy.rules import (
        build_complex_enum_values_from_file_texts,
        build_type_memberships_from_file_texts,
        extract_type_definitions,
        load_hoi4_alias_definitions_by_family,
        load_hoi4_alias_invocations_by_object,
        load_hoi4_alias_members_by_family,
        load_hoi4_complex_enum_definitions,
        load_hoi4_field_constraints,
        load_hoi4_known_scopes,
        load_hoi4_link_definitions,
        load_hoi4_localisation_command_definitions,
        load_hoi4_modifier_definitions,
        load_hoi4_schema_graph,
        load_hoi4_single_alias_definitions,
        load_hoi4_single_alias_invocations_by_object,
        load_hoi4_subtype_field_constraints_by_object,
        load_hoi4_subtype_matchers_by_object,
        load_hoi4_type_localisation_templates_by_type,
        load_hoi4_values_memberships_by_key,
    )

    schema = load_hoi4_schema_graph()
    type_definitions = extract_type_definitions(schema)
    memberships = build_type_memberships_from_file_texts(
        file_texts_by_path=file_texts_by_path,
        type_definitions_by_key=type_definitions,
    )
    field_constraints = load_hoi4_field_constraints(include_implicit_required=False)
    value_memberships = build_value_memberships_from_file_texts(
        file_texts_by_path=file_texts_by_path,
        field_constraints_by_object=field_constraints,
    )
    special_value_memberships = load_hoi4_values_memberships_by_key()
    merged_value_memberships = _merge_memberships(value_memberships, special_value_memberships)
    modifier_definitions = load_hoi4_modifier_definitions()
    localisation_command_definitions = load_hoi4_localisation_command_definitions()
    type_localisation_templates = load_hoi4_type_localisation_templates_by_type()
    modifier_names = frozenset(modifier_definitions.keys())
    alias_memberships = _merge_family_memberships(
        load_hoi4_alias_members_by_family(),
        family="modifier",
        values=modifier_names,
    )
    alias_definitions = load_hoi4_alias_definitions_by_family()
    alias_invocations = load_hoi4_alias_invocations_by_object()
    single_alias_definitions = load_hoi4_single_alias_definitions()
    single_alias_invocations = load_hoi4_single_alias_invocations_by_object()
    type_memberships = _merge_memberships(
        memberships,
        {"modifier": modifier_names},
    )
    complex_enum_memberships = build_complex_enum_values_from_file_texts(
        file_texts_by_path=file_texts_by_path,
        definitions_by_key=load_hoi4_complex_enum_definitions(),
    )
    return TypecheckServices(
        asset_registry=asset_registry or NullAssetRegistry(),
        policy=policy or TypecheckPolicy(),
        type_memberships_by_key=MappingProxyType(type_memberships),
        value_memberships_by_key=MappingProxyType(merged_value_memberships),
        special_value_memberships_by_key=MappingProxyType(special_value_memberships),
        known_scopes=load_hoi4_known_scopes(),
        enum_memberships_by_key=MappingProxyType(complex_enum_memberships),
        alias_memberships_by_family=MappingProxyType(alias_memberships),
        alias_definitions_by_family=MappingProxyType(alias_definitions),
        alias_invocations_by_object=MappingProxyType(alias_invocations),
        single_alias_definitions_by_name=MappingProxyType(single_alias_definitions),
        single_alias_invocations_by_object=MappingProxyType(single_alias_invocations),
        subtype_matchers_by_object=MappingProxyType(load_hoi4_subtype_matchers_by_object()),
        subtype_field_constraints_by_object=MappingProxyType(load_hoi4_subtype_field_constraints_by_object()),
        link_definitions_by_name=MappingProxyType(load_hoi4_link_definitions()),
        modifier_definitions_by_name=MappingProxyType(modifier_definitions),
        localisation_command_definitions_by_name=MappingProxyType(localisation_command_definitions),
        type_localisation_templates_by_type=MappingProxyType(type_localisation_templates),
        localisation_key_provider=LocalisationKeyProvider(),
    )


def build_typecheck_services_from_project_root(
    *,
    project_root: str,
    asset_registry: AssetRegistry | None = None,
    policy: TypecheckPolicy | None = None,
) -> TypecheckServices:
    """Build generic type-membership services from project-root script files."""
    from jominipy.rules import collect_file_texts_under_root

    file_texts = collect_file_texts_under_root(project_root)
    services = build_typecheck_services_from_file_texts(
        file_texts_by_path=file_texts,
        asset_registry=asset_registry,
        policy=policy,
    )
    return TypecheckServices(
        asset_registry=services.asset_registry,
        policy=services.policy,
        type_memberships_by_key=services.type_memberships_by_key,
        value_memberships_by_key=services.value_memberships_by_key,
        special_value_memberships_by_key=services.special_value_memberships_by_key,
        known_scopes=services.known_scopes,
        enum_memberships_by_key=services.enum_memberships_by_key,
        alias_memberships_by_family=services.alias_memberships_by_family,
        alias_definitions_by_family=services.alias_definitions_by_family,
        alias_invocations_by_object=services.alias_invocations_by_object,
        single_alias_definitions_by_name=services.single_alias_definitions_by_name,
        single_alias_invocations_by_object=services.single_alias_invocations_by_object,
        subtype_matchers_by_object=services.subtype_matchers_by_object,
        subtype_field_constraints_by_object=services.subtype_field_constraints_by_object,
        link_definitions_by_name=services.link_definitions_by_name,
        modifier_definitions_by_name=services.modifier_definitions_by_name,
        localisation_command_definitions_by_name=services.localisation_command_definitions_by_name,
        type_localisation_templates_by_type=services.type_localisation_templates_by_type,
        localisation_key_provider=load_localisation_key_provider_from_project_root(project_root=project_root),
    )


def build_value_memberships_from_file_texts(
    *,
    file_texts_by_path: Mapping[str, str],
    field_constraints_by_object: Mapping[str, Mapping[str, object]],
) -> dict[str, frozenset[str]]:
    from jominipy.ast import AstScalar
    from jominipy.parser import parse_result

    memberships: dict[str, set[str]] = {}
    for text in file_texts_by_path.values():
        parsed = parse_result(text)
        facts = parsed.analysis_facts()
        for object_key, field_constraints in field_constraints_by_object.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue
            for field_name, constraint in field_constraints.items():
                specs = getattr(constraint, "value_specs", ())
                keys = {
                    (spec.argument or "").strip()
                    for spec in specs
                    if getattr(spec, "kind", None) == "value_set_ref" and (spec.argument or "").strip()
                }
                if not keys:
                    continue
                for field_fact in field_map.get(field_name, ()):
                    if not isinstance(field_fact.value, AstScalar):
                        continue
                    raw = field_fact.value.raw_text.strip().strip('"')
                    if not raw:
                        continue
                    for key in keys:
                        memberships.setdefault(key, set()).add(raw)
    return {key: frozenset(values) for key, values in memberships.items()}


def _merge_memberships(
    left: Mapping[str, frozenset[str]],
    right: Mapping[str, frozenset[str]],
) -> dict[str, frozenset[str]]:
    merged: dict[str, set[str]] = {}
    for key, values in left.items():
        merged.setdefault(key, set()).update(values)
    for key, values in right.items():
        merged.setdefault(key, set()).update(values)
    return {key: frozenset(values) for key, values in merged.items()}


def _merge_family_memberships(
    memberships: Mapping[str, frozenset[str]],
    *,
    family: str,
    values: frozenset[str],
) -> dict[str, frozenset[str]]:
    merged = dict(memberships)
    existing = set(merged.get(family, frozenset()))
    existing.update(values)
    merged[family] = frozenset(existing)
    return merged
