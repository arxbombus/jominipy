from __future__ import annotations

"""
Compatibility facade for rules semantic adapters.

Implementation is split across `jominipy.rules.adapters.*` modules for maintainability.
This module re-exports the existing public surface to avoid churn in callers.
"""

from jominipy.rules.adapters.aliases import (
    build_alias_definitions_by_family,
    build_alias_invocations_by_object,
    build_alias_members_by_family,
    build_expanded_field_constraints,
    build_single_alias_definitions,
    build_single_alias_invocations_by_object,
    build_type_localisation_templates_by_type,
    load_hoi4_alias_definitions_by_family,
    load_hoi4_alias_invocations_by_object,
    load_hoi4_alias_members_by_family,
    load_hoi4_expanded_field_constraints,
    load_hoi4_single_alias_definitions,
    load_hoi4_single_alias_invocations_by_object,
    load_hoi4_type_localisation_templates_by_type,
)
from jominipy.rules.adapters.complex_enums import (
    build_complex_enum_definitions,
    build_complex_enum_values_from_file_texts,
    load_hoi4_complex_enum_definitions,
)
from jominipy.rules.adapters.models import (
    AliasDefinition,
    AliasInvocation,
    ComplexEnumDefinition,
    ExpandedFieldConstraints,
    LinkDefinition,
    LocalisationCommandDefinition,
    ModifierDefinition,
    SingleAliasDefinition,
    SingleAliasInvocation,
    SubtypeMatcher,
    TypeLocalisationTemplate,
)
from jominipy.rules.adapters.special_files import (
    build_link_definitions,
    build_localisation_command_definitions,
    build_modifier_definitions,
    build_values_memberships_by_key,
    load_hoi4_link_definitions,
    load_hoi4_localisation_command_definitions,
    load_hoi4_modifier_definitions,
    load_hoi4_values_memberships_by_key,
)
from jominipy.rules.adapters.subtypes import (
    build_subtype_field_constraints_by_object,
    build_subtype_matchers_by_object,
    load_hoi4_subtype_field_constraints_by_object,
    load_hoi4_subtype_matchers_by_object,
)

__all__ = [
    "AliasDefinition",
    "AliasInvocation",
    "ComplexEnumDefinition",
    "ExpandedFieldConstraints",
    "LinkDefinition",
    "LocalisationCommandDefinition",
    "ModifierDefinition",
    "SingleAliasDefinition",
    "SingleAliasInvocation",
    "SubtypeMatcher",
    "TypeLocalisationTemplate",
    "build_alias_definitions_by_family",
    "build_alias_invocations_by_object",
    "build_alias_members_by_family",
    "build_complex_enum_definitions",
    "build_complex_enum_values_from_file_texts",
    "build_expanded_field_constraints",
    "build_link_definitions",
    "build_localisation_command_definitions",
    "build_modifier_definitions",
    "build_single_alias_definitions",
    "build_single_alias_invocations_by_object",
    "build_subtype_field_constraints_by_object",
    "build_subtype_matchers_by_object",
    "build_type_localisation_templates_by_type",
    "build_values_memberships_by_key",
    "load_hoi4_alias_definitions_by_family",
    "load_hoi4_alias_invocations_by_object",
    "load_hoi4_alias_members_by_family",
    "load_hoi4_complex_enum_definitions",
    "load_hoi4_expanded_field_constraints",
    "load_hoi4_link_definitions",
    "load_hoi4_localisation_command_definitions",
    "load_hoi4_modifier_definitions",
    "load_hoi4_single_alias_definitions",
    "load_hoi4_single_alias_invocations_by_object",
    "load_hoi4_subtype_field_constraints_by_object",
    "load_hoi4_subtype_matchers_by_object",
    "load_hoi4_type_localisation_templates_by_type",
    "load_hoi4_values_memberships_by_key",
]
