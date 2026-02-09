from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from jominipy.rules.ir import RuleStatement
from jominipy.rules.semantics import RuleFieldConstraint, RuleValueSpec


@dataclass(frozen=True, slots=True)
class ExpandedFieldConstraints:
    """Field constraints after semantic adapter expansion steps."""

    by_object: dict[str, dict[str, RuleFieldConstraint]]


@dataclass(frozen=True, slots=True)
class SubtypeMatcher:
    """Subtype matcher extracted from `type[...]` subtype declarations."""

    subtype_name: str
    expected_field_values: tuple[tuple[str, str], ...] = ()
    type_key_filters: tuple[str, ...] = ()
    excluded_type_key_filters: tuple[str, ...] = ()
    starts_with: str | None = None
    push_scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ComplexEnumDefinition:
    """Normalized `complex_enum[...]` definition."""

    enum_key: str
    paths: tuple[str, ...]
    path_strict: bool
    path_file: str | None
    path_extension: str | None
    start_from_root: bool
    name_tree: tuple[RuleStatement, ...]


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

