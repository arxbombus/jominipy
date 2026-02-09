"""Type-check rules and rule contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Literal, Mapping, Protocol

from jominipy.analysis import AnalysisFacts, FieldFact
from jominipy.ast import (
    AstBlock,
    AstKeyValue,
    AstScalar,
    AstTaggedBlockValue,
    interpret_scalar,
)
from jominipy.diagnostics import (
    TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT,
    TYPECHECK_INCONSISTENT_VALUE_SHAPE,
    TYPECHECK_INVALID_FIELD_REFERENCE,
    TYPECHECK_INVALID_FIELD_TYPE,
    TYPECHECK_INVALID_SCOPE_CONTEXT,
    TYPECHECK_RULE_CUSTOM_ERROR,
    Diagnostic,
)
from jominipy.localisation.keys import LocalisationKeyProvider
from jominipy.rules.adapter import (
    AliasDefinition,
    AliasInvocation,
    LinkDefinition,
    SingleAliasDefinition,
    SingleAliasInvocation,
    SubtypeMatcher,
    TypeLocalisationTemplate,
)
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleFieldScopeConstraint,
    RuleValueSpec,
    load_hoi4_enum_values,
    load_hoi4_field_constraints,
    load_hoi4_field_scope_constraints,
    load_hoi4_known_scopes,
    load_hoi4_type_keys,
)
from jominipy.text import TextRange, TextSize
from jominipy.typecheck.assets import (
    AssetLookupStatus,
    AssetRegistry,
    NullAssetRegistry,
)
from jominipy.typecheck.services import TypecheckPolicy, TypecheckServices

type TypecheckDomain = Literal["correctness"]
type TypecheckConfidence = Literal["sound"]

_VARIABLE_REF_PATTERN = re.compile(r"^[A-Za-z_@][A-Za-z0-9_:@.\-]*$")
_RANGE_PATTERN = re.compile(r"^(?P<min>-?(?:\d+\.\d+|\d+)|-?inf)\.\.(?P<max>-?(?:\d+\.\d+|\d+)|inf)$")
_TYPE_REF_PATTERN = re.compile(r"^(?P<prefix>.*)<(?P<type_key>[A-Za-z_][A-Za-z0-9_]*)>(?P<suffix>.*)$")
_LOCALISATION_TOKEN_PATTERN = re.compile(r"\[(?P<body>[^\[\]]+)\]")
_LOCALISATION_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCOPE_ALIAS_ORDER = ("this", "from", "fromfrom", "fromfromfrom", "fromfromfromfrom")
_PREV_ALIAS_ORDER = ("prev", "prevprev", "prevprevprev", "prevprevprevprev")
_SCOPE_ALIAS_KEYS = frozenset((*_SCOPE_ALIAS_ORDER, *_PREV_ALIAS_ORDER, "root"))
_REFERENCE_SPEC_KINDS = {
    "enum_ref",
    "scope_ref",
    "value_ref",
    "value_set_ref",
    "type_ref",
    "alias_match_left_ref",
}


@dataclass(frozen=True, slots=True)
class TypecheckFacts:
    """Type facts produced from shared analysis facts."""

    inconsistent_top_level_shapes: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ScopeContext:
    """Resolved scope context before evaluating a field path."""

    active_scopes: frozenset[str]
    aliases: Mapping[str, str]
    ambiguity: str | None = None


class TypecheckRule(Protocol):
    """Biome-style type-check rule contract."""

    @property
    def code(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def domain(self) -> TypecheckDomain: ...

    @property
    def confidence(self) -> TypecheckConfidence: ...

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]: ...


@dataclass(frozen=True, slots=True)
class InconsistentTopLevelShapeRule:
    """Flags keys that switch between scalar/block/tagged forms at top-level."""

    code: str = TYPECHECK_INCONSISTENT_VALUE_SHAPE.code
    name: str = "inconsistentTopLevelShape"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for key, shapes in sorted(type_facts.inconsistent_top_level_shapes.items()):
            diagnostics.append(
                Diagnostic(
                    code=self.code,
                    message=f"{TYPECHECK_INCONSISTENT_VALUE_SHAPE.message} Key `{key}` uses {', '.join(shapes)}.",
                    range=_find_key_range(text, key),
                    severity=TYPECHECK_INCONSISTENT_VALUE_SHAPE.severity,
                    hint="Keep a stable value shape per key or split the key into explicit variants.",
                    category=TYPECHECK_INCONSISTENT_VALUE_SHAPE.category,
                )
            )
        return diagnostics


@dataclass(frozen=True, slots=True)
class FieldConstraintRule:
    """Checks field values against CWTools-derived primitive constraints in typecheck."""

    code: str = TYPECHECK_INVALID_FIELD_TYPE.code
    name: str = "fieldConstraint"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    field_constraints_by_object: dict[str, dict[str, RuleFieldConstraint]] | None = None
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = (
        MappingProxyType({})
    )
    asset_registry: AssetRegistry = NullAssetRegistry()
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)

        diagnostics: list[Diagnostic] = []
        for object_key, field_constraints in constraints.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            subtype_constraints = self.subtype_field_constraints_by_object.get(object_key, {})
            field_names = set(field_constraints.keys())
            for by_field in subtype_constraints.values():
                field_names.update(by_field.keys())
            for field_name in sorted(field_names):
                field_facts = field_map.get(field_name)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    constraint = _resolve_effective_field_constraint(
                        object_key=object_key,
                        object_occurrence=field_fact.object_occurrence,
                        field_name=field_name,
                        base_constraints=field_constraints,
                        subtype_matchers=subtype_matchers,
                        subtype_constraints=subtype_constraints,
                        facts=facts,
                    )
                    if constraint is None:
                        continue
                    primitive_specs = tuple(
                        spec for spec in constraint.value_specs if spec.kind not in _REFERENCE_SPEC_KINDS
                    )
                    if not primitive_specs:
                        continue
                    if _matches_value_specs(
                        field_fact.value,
                        primitive_specs,
                        asset_registry=self.asset_registry,
                        policy=self.policy,
                    ):
                        continue
                    if _has_reference_specs(constraint.value_specs):
                        # Leave mixed primitive/reference unions to the reference rule.
                        continue
                    diagnostics.append(
                        Diagnostic(
                            code=self.code,
                            message=(
                                f"{TYPECHECK_INVALID_FIELD_TYPE.message} "
                                f"`{object_key}.{field_name}` does not match {_format_value_specs(primitive_specs)}."
                            ),
                            range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                            severity=TYPECHECK_INVALID_FIELD_TYPE.severity,
                            hint=f"Use a value matching the schema for `{field_name}`.",
                            category=TYPECHECK_INVALID_FIELD_TYPE.category,
                        )
                    )
        return diagnostics


@dataclass(frozen=True, slots=True)
class FieldReferenceConstraintRule:
    """Checks field values against CWTools-derived resolved-reference constraints."""

    code: str = TYPECHECK_INVALID_FIELD_REFERENCE.code
    name: str = "fieldReferenceConstraint"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    field_constraints_by_object: dict[str, dict[str, RuleFieldConstraint]] | None = None
    enum_values_by_key: Mapping[str, frozenset[str]] | None = None
    known_type_keys: frozenset[str] | None = None
    type_memberships_by_key: Mapping[str, frozenset[str]] = MappingProxyType({})
    value_memberships_by_key: Mapping[str, frozenset[str]] = MappingProxyType({})
    known_scopes: frozenset[str] = frozenset()
    alias_memberships_by_family: Mapping[str, frozenset[str]] = MappingProxyType({})
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = (
        MappingProxyType({})
    )
    link_definitions_by_name: Mapping[str, LinkDefinition] = MappingProxyType({})
    field_scope_constraints_by_object: dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]] | None = None
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)
        enum_values = self.enum_values_by_key or load_hoi4_enum_values()
        if self.enum_values_by_key is not None:
            enum_values = _merge_membership_maps(load_hoi4_enum_values(), self.enum_values_by_key)
        known_type_keys = self.known_type_keys or load_hoi4_type_keys()
        known_scopes = self.known_scopes or load_hoi4_known_scopes()
        scope_constraints = self.field_scope_constraints_by_object
        if scope_constraints is None:
            scope_constraints = load_hoi4_field_scope_constraints()
        dynamic_values = _build_dynamic_value_memberships(facts=facts, constraints=constraints)
        merged_value_memberships = _merge_membership_maps(self.value_memberships_by_key, dynamic_values)

        diagnostics: list[Diagnostic] = []
        for object_key, field_constraints in constraints.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            subtype_constraints = self.subtype_field_constraints_by_object.get(object_key, {})
            field_names = set(field_constraints.keys())
            for by_field in subtype_constraints.values():
                field_names.update(by_field.keys())
            for field_name in sorted(field_names):
                field_facts = field_map.get(field_name)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    constraint = _resolve_effective_field_constraint(
                        object_key=object_key,
                        object_occurrence=field_fact.object_occurrence,
                        field_name=field_name,
                        base_constraints=field_constraints,
                        subtype_matchers=subtype_matchers,
                        subtype_constraints=subtype_constraints,
                        facts=facts,
                    )
                    if constraint is None:
                        continue
                    reference_specs = tuple(
                        spec for spec in constraint.value_specs if spec.kind in _REFERENCE_SPEC_KINDS
                    )
                    if not reference_specs:
                        continue
                    non_reference_specs = tuple(
                        spec for spec in constraint.value_specs if spec.kind not in _REFERENCE_SPEC_KINDS
                    )
                    relative_path = field_fact.path[1:]
                    scope_context = _resolve_scope_context_before_path(
                        relative_path=relative_path,
                        by_path=scope_constraints.get(object_key, {}),
                        initial_push_scopes=_resolve_subtype_push_scopes(
                            object_key=object_key,
                            object_occurrence=field_fact.object_occurrence,
                            matchers=subtype_matchers,
                            facts=facts,
                        ),
                    )
                    if scope_context.ambiguity is not None:
                        diagnostics.append(
                            Diagnostic(
                                code=TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.code,
                                message=(
                                    f"{TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.message} "
                                    f"`{object_key}.{field_name}`: {scope_context.ambiguity}"
                                ),
                                range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                severity=TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.severity,
                                hint="Remove conflicting replace_scope alias mappings.",
                                category=TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.category,
                            )
                        )
                        continue
                    if non_reference_specs and _matches_value_specs(
                        field_fact.value,
                        non_reference_specs,
                        asset_registry=NullAssetRegistry(),
                        policy=self.policy,
                    ):
                        continue
                    if _matches_reference_specs(
                        field_fact.value,
                        reference_specs,
                        enum_values_by_key=enum_values,
                        known_type_keys=known_type_keys,
                        type_memberships_by_key=self.type_memberships_by_key,
                        value_memberships_by_key=merged_value_memberships,
                        known_scopes=known_scopes,
                        alias_memberships_by_family=self.alias_memberships_by_family,
                        link_definitions_by_name=self.link_definitions_by_name,
                        scope_context=scope_context,
                        policy=self.policy,
                    ):
                        continue
                    diagnostics.append(
                        Diagnostic(
                            code=self.code,
                            message=(
                                f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                f"`{object_key}.{field_name}` does not match "
                                f"{_format_value_specs(reference_specs)}."
                            ),
                            range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                            severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                            hint=f"Use a schema-resolved reference for `{field_name}`.",
                            category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                        )
                    )
        return diagnostics


@dataclass(frozen=True, slots=True)
class FieldScopeContextRule:
    """Checks field declarations against scope context transitions from CWTools metadata."""

    code: str = TYPECHECK_INVALID_SCOPE_CONTEXT.code
    name: str = "fieldScopeContext"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    field_scope_constraints_by_object: dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]] | None = None
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        scope_constraints = self.field_scope_constraints_by_object
        if scope_constraints is None:
            scope_constraints = load_hoi4_field_scope_constraints()

        diagnostics: list[Diagnostic] = []
        for field_fact in facts.all_field_facts:
            by_object = scope_constraints.get(field_fact.object_key)
            if not by_object:
                continue
            relative_path = field_fact.path[1:]
            declaration_constraint = by_object.get(relative_path)
            if declaration_constraint is None or declaration_constraint.required_scope is None:
                continue

            subtype_push_scopes = _resolve_subtype_push_scopes(
                object_key=field_fact.object_key,
                object_occurrence=field_fact.object_occurrence,
                matchers=self.subtype_matchers_by_object.get(field_fact.object_key, ()),
                facts=facts,
            )
            scope_context = _resolve_scope_context_before_path(
                relative_path=relative_path,
                by_path=by_object,
                initial_push_scopes=subtype_push_scopes,
            )
            if scope_context.ambiguity is not None:
                diagnostics.append(
                    Diagnostic(
                        code=TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.code,
                        message=(
                            f"{TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.message} "
                            f"`{'.'.join(relative_path)}`: {scope_context.ambiguity}"
                        ),
                        range=_find_key_occurrence_range(text, field_fact.object_key, field_fact.object_occurrence),
                        severity=TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.severity,
                        hint="Remove conflicting replace_scope alias mappings.",
                        category=TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT.category,
                    )
                )
                continue
            required = set(scope.lower() for scope in declaration_constraint.required_scope)
            if scope_context.active_scopes and required.intersection(scope_context.active_scopes):
                continue
            diagnostics.append(
                Diagnostic(
                    code=self.code,
                    message=(
                        f"{TYPECHECK_INVALID_SCOPE_CONTEXT.message} "
                        f"`{'.'.join(relative_path)}` requires scope {', '.join(declaration_constraint.required_scope)}."
                    ),
                    range=_find_key_occurrence_range(text, field_fact.object_key, field_fact.object_occurrence),
                    severity=TYPECHECK_INVALID_SCOPE_CONTEXT.severity,
                    hint="Adjust surrounding scope transitions (push_scope/replace_scope) or move this field.",
                    category=TYPECHECK_INVALID_SCOPE_CONTEXT.category,
                )
            )
        return diagnostics


@dataclass(frozen=True, slots=True)
class LocalisationKeyExistenceRule:
    """Checks localisation key references against loaded localisation keys."""

    code: str = TYPECHECK_INVALID_FIELD_REFERENCE.code
    name: str = "localisationKeyExists"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    field_constraints_by_object: dict[str, dict[str, RuleFieldConstraint]] | None = None
    localisation_key_provider: LocalisationKeyProvider = LocalisationKeyProvider()
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = (
        MappingProxyType({})
    )
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)
        if self.localisation_key_provider.is_empty:
            return []

        diagnostics: list[Diagnostic] = []
        for object_key, field_constraints in constraints.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            subtype_constraints = self.subtype_field_constraints_by_object.get(object_key, {})
            field_names = set(field_constraints.keys())
            for by_field in subtype_constraints.values():
                field_names.update(by_field.keys())
            for field_name in sorted(field_names):
                field_facts = field_map.get(field_name)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    constraint = _resolve_effective_field_constraint(
                        object_key=object_key,
                        object_occurrence=field_fact.object_occurrence,
                        field_name=field_name,
                        base_constraints=field_constraints,
                        subtype_matchers=subtype_matchers,
                        subtype_constraints=subtype_constraints,
                        facts=facts,
                    )
                    if constraint is None:
                        continue
                    if not _allows_localisation_key_primitive(constraint.value_specs):
                        continue
                    if not isinstance(field_fact.value, AstScalar):
                        continue
                    key = _extract_localisation_key_reference(field_fact.value.raw_text)
                    if key is None:
                        continue
                    if not self.localisation_key_provider.has_key(key):
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Unknown localisation key `{key}` in `{object_key}.{field_name}`."
                                ),
                                range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint="Define this key in localisation files or change the reference.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
                        continue
                    if self.policy.localisation_coverage == "any":
                        continue
                    required_locales = (
                        self.policy.localisation_required_locales
                        if self.policy.localisation_required_locales
                        else self.localisation_key_provider.locales
                    )
                    missing = self.localisation_key_provider.missing_locales_for_key(
                        key,
                        required_locales=required_locales,
                    )
                    if missing:
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Localisation key `{key}` is missing locales: {', '.join(missing)}."
                                ),
                                range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint="Add missing locale entries or switch localisation coverage policy.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
        return diagnostics


@dataclass(frozen=True, slots=True)
class TypeLocalisationRequirementRule:
    """Checks required type-localisation templates against loaded localisation keys."""

    code: str = TYPECHECK_INVALID_FIELD_REFERENCE.code
    name: str = "typeLocalisationRequirement"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    type_memberships_by_key: Mapping[str, frozenset[str]] = MappingProxyType({})
    type_localisation_templates_by_type: Mapping[str, tuple[TypeLocalisationTemplate, ...]] = MappingProxyType({})
    localisation_key_provider: LocalisationKeyProvider = LocalisationKeyProvider()
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        if self.localisation_key_provider.is_empty:
            return []

        diagnostics: list[Diagnostic] = []
        for type_key, templates in sorted(self.type_localisation_templates_by_type.items()):
            members = self.type_memberships_by_key.get(type_key)
            if not members:
                continue
            required_templates = tuple(template for template in templates if template.required)
            if not required_templates:
                continue
            for member in sorted(members):
                for template in required_templates:
                    key = template.template.replace("$", member)
                    if not self.localisation_key_provider.has_key(key):
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Missing required localisation key `{key}` for type `{type_key}` member `{member}`."
                                ),
                                range=TextRange.empty(TextSize(0)),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint="Define this required localisation key or update the type localisation template.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
                        continue
                    if self.policy.localisation_coverage == "any":
                        continue
                    required_locales = (
                        self.policy.localisation_required_locales
                        if self.policy.localisation_required_locales
                        else self.localisation_key_provider.locales
                    )
                    missing = self.localisation_key_provider.missing_locales_for_key(
                        key,
                        required_locales=required_locales,
                    )
                    if missing:
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Required localisation key `{key}` is missing locales: {', '.join(missing)}."
                                ),
                                range=TextRange.empty(TextSize(0)),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint="Add missing locale entries or relax localisation coverage policy.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
        return diagnostics


@dataclass(frozen=True, slots=True)
class AliasExecutionRule:
    """Checks alias/single-alias invocation values against extracted definitions."""

    code: str = TYPECHECK_INVALID_FIELD_REFERENCE.code
    name: str = "aliasExecution"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    alias_definitions_by_family: Mapping[str, Mapping[str, AliasDefinition]] = MappingProxyType({})
    alias_invocations_by_object: Mapping[str, tuple[AliasInvocation, ...]] = MappingProxyType({})
    single_alias_definitions_by_name: Mapping[str, SingleAliasDefinition] = MappingProxyType({})
    single_alias_invocations_by_object: Mapping[str, tuple[SingleAliasInvocation, ...]] = MappingProxyType({})
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = (
        MappingProxyType({})
    )
    asset_registry: AssetRegistry = NullAssetRegistry()
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        diagnostics.extend(self._run_alias_invocations(facts=facts, text=text))
        diagnostics.extend(self._run_single_alias_invocations(facts=facts, text=text))
        return diagnostics

    def _run_alias_invocations(self, *, facts: AnalysisFacts, text: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for object_key, invocations in self.alias_invocations_by_object.items():
            object_fields: tuple[FieldFact, ...] = tuple(
                field_fact for field_fact in facts.all_field_facts if field_fact.object_key == object_key
            )
            if not object_fields:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            active_subtypes_by_occurrence: dict[int, tuple[str, ...]] = {}
            for invocation in invocations:
                family_definitions = self.alias_definitions_by_family.get(invocation.family)
                if not family_definitions:
                    if self.policy.unresolved_reference == "defer":
                        continue
                    for field_fact in object_fields:
                        if field_fact.path[:-1] != invocation.parent_path:
                            continue
                        if invocation.required_subtype is not None:
                            active_subtypes = active_subtypes_by_occurrence.get(field_fact.object_occurrence)
                            if active_subtypes is None:
                                active_subtypes = _resolve_active_subtypes(
                                    object_key=object_key,
                                    object_occurrence=field_fact.object_occurrence,
                                    matchers=subtype_matchers,
                                    facts=facts,
                                )
                                active_subtypes_by_occurrence[field_fact.object_occurrence] = active_subtypes
                            if invocation.required_subtype not in active_subtypes:
                                continue
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Unknown alias family `{invocation.family}` for `{object_key}` invocation path."
                                ),
                                range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint="Define the alias family in rules or relax unresolved reference policy.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
                    continue
                for field_fact in object_fields:
                    if field_fact.path[:-1] != invocation.parent_path:
                        continue
                    if invocation.required_subtype is not None:
                        active_subtypes = active_subtypes_by_occurrence.get(field_fact.object_occurrence)
                        if active_subtypes is None:
                            active_subtypes = _resolve_active_subtypes(
                                object_key=object_key,
                                object_occurrence=field_fact.object_occurrence,
                                matchers=subtype_matchers,
                                facts=facts,
                            )
                            active_subtypes_by_occurrence[field_fact.object_occurrence] = active_subtypes
                        if invocation.required_subtype not in active_subtypes:
                            continue
                    alias_definition = family_definitions.get(field_fact.field_key)
                    if alias_definition is None:
                        if self.policy.unresolved_reference == "error":
                            diagnostics.append(
                                Diagnostic(
                                    code=self.code,
                                    message=(
                                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                        f"Unknown alias key `{field_fact.field_key}` for family `{invocation.family}`."
                                    ),
                                    range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                    hint="Define the alias declaration or relax unresolved reference policy.",
                                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                                )
                            )
                        continue
                    diagnostics.extend(
                        _validate_alias_like_value(
                            object_key=object_key,
                            object_occurrence=field_fact.object_occurrence,
                            field_key=field_fact.field_key,
                            value=field_fact.value,
                            text=text,
                            value_specs=alias_definition.value_specs,
                            field_constraints=alias_definition.field_constraints,
                            alias_definitions_by_family=self.alias_definitions_by_family,
                            asset_registry=self.asset_registry,
                            policy=self.policy,
                        )
                    )
        return diagnostics

    def _run_single_alias_invocations(self, *, facts: AnalysisFacts, text: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for object_key, invocations in self.single_alias_invocations_by_object.items():
            object_fields: tuple[FieldFact, ...] = tuple(
                field_fact for field_fact in facts.all_field_facts if field_fact.object_key == object_key
            )
            if not object_fields:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            active_subtypes_by_occurrence: dict[int, tuple[str, ...]] = {}
            by_path: dict[tuple[str, ...], list[FieldFact]] = {}
            for field_fact in object_fields:
                by_path.setdefault(field_fact.path, []).append(field_fact)
            for invocation in invocations:
                field_facts = by_path.get(invocation.field_path)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    if invocation.required_subtype is not None:
                        active_subtypes = active_subtypes_by_occurrence.get(field_fact.object_occurrence)
                        if active_subtypes is None:
                            active_subtypes = _resolve_active_subtypes(
                                object_key=object_key,
                                object_occurrence=field_fact.object_occurrence,
                                matchers=subtype_matchers,
                                facts=facts,
                            )
                            active_subtypes_by_occurrence[field_fact.object_occurrence] = active_subtypes
                        if invocation.required_subtype not in active_subtypes:
                            continue
                    definition = self.single_alias_definitions_by_name.get(invocation.alias_name)
                    if definition is None:
                        if self.policy.unresolved_reference == "defer":
                            continue
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Unknown single-alias `{invocation.alias_name}`."
                                ),
                                range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint="Define the single_alias declaration or remove the single_alias_right reference.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
                        continue
                    diagnostics.extend(
                        _validate_alias_like_value(
                            object_key=object_key,
                            object_occurrence=field_fact.object_occurrence,
                            field_key=field_fact.field_key,
                            value=field_fact.value,
                            text=text,
                            value_specs=definition.value_specs,
                            field_constraints=definition.field_constraints,
                            alias_definitions_by_family=self.alias_definitions_by_family,
                            asset_registry=self.asset_registry,
                            policy=self.policy,
                        )
                    )
        return diagnostics


@dataclass(frozen=True, slots=True)
class LocalisationCommandScopeRule:
    """Checks localisation command usage against `localisation_commands` scope metadata."""

    code: str = TYPECHECK_INVALID_FIELD_REFERENCE.code
    name: str = "localisationCommandScope"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    field_constraints_by_object: dict[str, dict[str, RuleFieldConstraint]] | None = None
    localisation_command_definitions_by_name: Mapping[str, object] = MappingProxyType({})
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = (
        MappingProxyType({})
    )
    field_scope_constraints_by_object: dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]] | None = None
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)
        if not self.localisation_command_definitions_by_name:
            return []
        scope_constraints = self.field_scope_constraints_by_object
        if scope_constraints is None:
            scope_constraints = load_hoi4_field_scope_constraints()

        diagnostics: list[Diagnostic] = []
        for object_key, field_constraints in constraints.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            subtype_constraints = self.subtype_field_constraints_by_object.get(object_key, {})
            field_names = set(field_constraints.keys())
            for by_field in subtype_constraints.values():
                field_names.update(by_field.keys())
            for field_name in sorted(field_names):
                field_facts = field_map.get(field_name)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    constraint = _resolve_effective_field_constraint(
                        object_key=object_key,
                        object_occurrence=field_fact.object_occurrence,
                        field_name=field_name,
                        base_constraints=field_constraints,
                        subtype_matchers=subtype_matchers,
                        subtype_constraints=subtype_constraints,
                        facts=facts,
                    )
                    if constraint is None:
                        continue
                    if not _allows_localisation_primitive(constraint.value_specs):
                        continue
                    if not isinstance(field_fact.value, AstScalar):
                        continue
                    commands = _extract_localisation_commands(field_fact.value.raw_text)
                    if not commands:
                        continue
                    relative_path = field_fact.path[1:]
                    scope_context = _resolve_scope_context_before_path(
                        relative_path=relative_path,
                        by_path=scope_constraints.get(object_key, {}),
                        initial_push_scopes=_resolve_subtype_push_scopes(
                            object_key=object_key,
                            object_occurrence=field_fact.object_occurrence,
                            matchers=subtype_matchers,
                            facts=facts,
                        ),
                    )
                    for command in commands:
                        command_def = self.localisation_command_definitions_by_name.get(command)
                        if command_def is None:
                            if self.policy.unresolved_reference == "defer":
                                continue
                            diagnostics.append(
                                Diagnostic(
                                    code=self.code,
                                    message=(
                                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                        f"Unknown localisation command `{command}` in `{object_key}.{field_name}`."
                                    ),
                                    range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                    hint="Use a command declared in localisation_commands.cwt.",
                                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                                )
                            )
                            continue
                        supported_scopes = tuple(
                            scope.lower() for scope in getattr(command_def, "supported_scopes", ()) if scope
                        )
                        if "any" in supported_scopes:
                            continue
                        if not supported_scopes:
                            if self.policy.unresolved_reference == "defer":
                                continue
                            diagnostics.append(
                                Diagnostic(
                                    code=self.code,
                                    message=(
                                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                        f"Localisation command `{command}` has no resolvable scope metadata."
                                    ),
                                    range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                    hint="Add supported scope metadata for the command.",
                                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                                )
                            )
                            continue
                        if not scope_context.active_scopes:
                            if self.policy.unresolved_reference == "defer":
                                continue
                            diagnostics.append(
                                Diagnostic(
                                    code=self.code,
                                    message=(
                                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                        f"Cannot resolve scope context for localisation command `{command}`."
                                    ),
                                    range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                    hint="Set scope context via push_scope/replace_scope metadata.",
                                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                                )
                            )
                            continue
                        if set(scope_context.active_scopes).intersection(supported_scopes):
                            continue
                        diagnostics.append(
                            Diagnostic(
                                code=self.code,
                                message=(
                                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                                    f"Localisation command `{command}` is not valid for scope "
                                    f"{', '.join(sorted(scope_context.active_scopes))}."
                                ),
                                range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                                hint=f"Use a command valid for scopes: {', '.join(supported_scopes)}.",
                                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                            )
                        )
        return diagnostics


@dataclass(frozen=True, slots=True)
class ErrorIfOnlyMatchRule:
    """Emits custom diagnostics when `error_if_only_match` constraints match."""

    code: str = TYPECHECK_RULE_CUSTOM_ERROR.code
    name: str = "errorIfOnlyMatch"
    domain: TypecheckDomain = "correctness"
    confidence: TypecheckConfidence = "sound"
    field_constraints_by_object: dict[str, dict[str, RuleFieldConstraint]] | None = None
    enum_values_by_key: Mapping[str, frozenset[str]] | None = None
    known_type_keys: frozenset[str] | None = None
    type_memberships_by_key: Mapping[str, frozenset[str]] = MappingProxyType({})
    value_memberships_by_key: Mapping[str, frozenset[str]] = MappingProxyType({})
    known_scopes: frozenset[str] = frozenset()
    alias_memberships_by_family: Mapping[str, frozenset[str]] = MappingProxyType({})
    subtype_matchers_by_object: Mapping[str, tuple[SubtypeMatcher, ...]] = MappingProxyType({})
    subtype_field_constraints_by_object: Mapping[str, Mapping[str, Mapping[str, RuleFieldConstraint]]] = (
        MappingProxyType({})
    )
    link_definitions_by_name: Mapping[str, LinkDefinition] = MappingProxyType({})
    field_scope_constraints_by_object: dict[str, dict[tuple[str, ...], RuleFieldScopeConstraint]] | None = None
    asset_registry: AssetRegistry = NullAssetRegistry()
    policy: TypecheckPolicy = TypecheckPolicy()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)
        enum_values = self.enum_values_by_key or load_hoi4_enum_values()
        if self.enum_values_by_key is not None:
            enum_values = _merge_membership_maps(load_hoi4_enum_values(), self.enum_values_by_key)
        known_type_keys = self.known_type_keys or load_hoi4_type_keys()
        known_scopes = self.known_scopes or load_hoi4_known_scopes()
        scope_constraints = self.field_scope_constraints_by_object
        if scope_constraints is None:
            scope_constraints = load_hoi4_field_scope_constraints()
        dynamic_values = _build_dynamic_value_memberships(facts=facts, constraints=constraints)
        merged_value_memberships = _merge_membership_maps(self.value_memberships_by_key, dynamic_values)

        diagnostics: list[Diagnostic] = []
        for object_key, field_constraints in constraints.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue
            subtype_matchers = self.subtype_matchers_by_object.get(object_key, ())
            subtype_constraints = self.subtype_field_constraints_by_object.get(object_key, {})
            field_names = set(field_constraints.keys())
            for by_field in subtype_constraints.values():
                field_names.update(by_field.keys())
            for field_name in sorted(field_names):
                field_facts = field_map.get(field_name)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    constraint = _resolve_effective_field_constraint(
                        object_key=object_key,
                        object_occurrence=field_fact.object_occurrence,
                        field_name=field_name,
                        base_constraints=field_constraints,
                        subtype_matchers=subtype_matchers,
                        subtype_constraints=subtype_constraints,
                        facts=facts,
                    )
                    if constraint is None or not constraint.error_if_only_match:
                        continue
                    reference_specs = tuple(
                        spec for spec in constraint.value_specs if spec.kind in _REFERENCE_SPEC_KINDS
                    )
                    non_reference_specs = tuple(
                        spec for spec in constraint.value_specs if spec.kind not in _REFERENCE_SPEC_KINDS
                    )
                    relative_path = field_fact.path[1:]
                    scope_context = _resolve_scope_context_before_path(
                        relative_path=relative_path,
                        by_path=scope_constraints.get(object_key, {}),
                        initial_push_scopes=_resolve_subtype_push_scopes(
                            object_key=object_key,
                            object_occurrence=field_fact.object_occurrence,
                            matchers=subtype_matchers,
                            facts=facts,
                        ),
                    )
                    if scope_context.ambiguity is not None:
                        continue
                    matches_non_reference = bool(non_reference_specs) and _matches_value_specs(
                        field_fact.value,
                        non_reference_specs,
                        asset_registry=self.asset_registry,
                        policy=self.policy,
                    )
                    matches_reference = bool(reference_specs) and _matches_reference_specs(
                        field_fact.value,
                        reference_specs,
                        enum_values_by_key=enum_values,
                        known_type_keys=known_type_keys,
                        type_memberships_by_key=self.type_memberships_by_key,
                        value_memberships_by_key=merged_value_memberships,
                        known_scopes=known_scopes,
                        alias_memberships_by_family=self.alias_memberships_by_family,
                        link_definitions_by_name=self.link_definitions_by_name,
                        scope_context=scope_context,
                        policy=self.policy,
                    )
                    if not (matches_non_reference or matches_reference):
                        continue
                    diagnostics.append(
                        Diagnostic(
                            code=self.code,
                            message=f"{TYPECHECK_RULE_CUSTOM_ERROR.message} {constraint.error_if_only_match}",
                            range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                            severity=TYPECHECK_RULE_CUSTOM_ERROR.severity,
                            hint="Adjust the value or remove the matching custom-error rule condition.",
                            category=TYPECHECK_RULE_CUSTOM_ERROR.category,
                        )
                    )
        return diagnostics


def _validate_alias_like_value(
    *,
    object_key: str,
    object_occurrence: int,
    field_key: str,
    value: object | None,
    text: str,
    value_specs: tuple[RuleValueSpec, ...],
    field_constraints: Mapping[str, RuleFieldConstraint],
    alias_definitions_by_family: Mapping[str, Mapping[str, AliasDefinition]],
    asset_registry: AssetRegistry,
    policy: TypecheckPolicy,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value_specs and not _matches_value_specs(
        value,
        value_specs,
        asset_registry=asset_registry,
        policy=policy,
    ):
        diagnostics.append(
            Diagnostic(
                code=TYPECHECK_INVALID_FIELD_REFERENCE.code,
                message=(
                    f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                    f"Alias field `{field_key}` does not match {_format_value_specs(value_specs)}."
                ),
                range=_find_key_occurrence_range(text, object_key, object_occurrence),
                severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                hint=f"Use a value matching alias constraints for `{field_key}`.",
                category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
            )
        )
        return diagnostics

    if not field_constraints:
        return diagnostics
    if not isinstance(value, AstBlock) or not value.is_object_like:
        return diagnostics

    child_fields = [statement for statement in value.statements if isinstance(statement, AstKeyValue)]
    child_map: dict[str, list[AstKeyValue]] = {}
    for child in child_fields:
        child_map.setdefault(child.key.raw_text, []).append(child)

    static_constraints: dict[str, RuleFieldConstraint] = {}
    alias_families: list[str] = []
    for child_key, constraint in field_constraints.items():
        family = _parse_alias_name_family(child_key)
        if family is not None:
            alias_families.append(family)
            continue
        static_constraints[child_key] = constraint

    for child_key, constraint in static_constraints.items():
        if constraint.required and child_key not in child_map:
            diagnostics.append(
                Diagnostic(
                    code=TYPECHECK_INVALID_FIELD_REFERENCE.code,
                    message=(
                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                        f"Alias field `{field_key}` is missing required child field `{child_key}`."
                    ),
                    range=_find_key_occurrence_range(text, object_key, object_occurrence),
                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                    hint=f"Add `{child_key} = ...` to alias field `{field_key}`.",
                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                )
            )
            continue
        for child in child_map.get(child_key, []):
            if _matches_value_specs(child.value, constraint.value_specs, asset_registry=asset_registry, policy=policy):
                continue
            diagnostics.append(
                Diagnostic(
                    code=TYPECHECK_INVALID_FIELD_REFERENCE.code,
                    message=(
                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                        f"Alias child `{field_key}.{child_key}` does not match {_format_value_specs(constraint.value_specs)}."
                    ),
                    range=_find_key_occurrence_range(text, object_key, object_occurrence),
                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                    hint=f"Use a value matching alias constraints for `{child_key}`.",
                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                )
            )

    if alias_families:
        for child in child_fields:
            if child.key.raw_text in static_constraints:
                continue
            matched_dynamic = False
            known_families: list[str] = []
            for family in alias_families:
                family_defs = alias_definitions_by_family.get(family, {})
                if family_defs:
                    known_families.append(family)
                alias_definition = family_defs.get(child.key.raw_text)
                if alias_definition is None:
                    continue
                matched_dynamic = True
                diagnostics.extend(
                    _validate_alias_like_value(
                        object_key=object_key,
                        object_occurrence=object_occurrence,
                        field_key=child.key.raw_text,
                        value=child.value,
                        text=text,
                        value_specs=alias_definition.value_specs,
                        field_constraints=alias_definition.field_constraints,
                        alias_definitions_by_family=alias_definitions_by_family,
                        asset_registry=asset_registry,
                        policy=policy,
                    )
                )
            if matched_dynamic:
                continue
            if policy.unresolved_reference == "defer":
                continue
            diagnostics.append(
                Diagnostic(
                    code=TYPECHECK_INVALID_FIELD_REFERENCE.code,
                    message=(
                        f"{TYPECHECK_INVALID_FIELD_REFERENCE.message} "
                        f"Unknown alias key `{child.key.raw_text}` under `{field_key}`"
                        f" for families: {', '.join(sorted(known_families or alias_families))}."
                    ),
                    range=_find_key_occurrence_range(text, object_key, object_occurrence),
                    severity=TYPECHECK_INVALID_FIELD_REFERENCE.severity,
                    hint="Define the alias key in the referenced alias family or relax unresolved reference policy.",
                    category=TYPECHECK_INVALID_FIELD_REFERENCE.category,
                )
            )
    return diagnostics


def _parse_alias_name_family(raw_key: str) -> str | None:
    if not raw_key.startswith("alias_name[") or not raw_key.endswith("]"):
        return None
    family = raw_key[len("alias_name[") : -1].strip()
    return family or None


def build_typecheck_facts(facts: AnalysisFacts) -> TypecheckFacts:
    inconsistent: dict[str, tuple[str, ...]] = {}
    for key, shapes in facts.top_level_shapes.items():
        if len(shapes) > 1:
            inconsistent[key] = tuple(sorted(shapes))
    return TypecheckFacts(inconsistent_top_level_shapes=inconsistent)


def default_typecheck_rules(*, services: TypecheckServices | None = None) -> tuple[TypecheckRule, ...]:
    resolved_services = services if services is not None else TypecheckServices()
    rules: list[TypecheckRule] = [
        InconsistentTopLevelShapeRule(),
        FieldConstraintRule(
            asset_registry=resolved_services.asset_registry,
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
            subtype_field_constraints_by_object=resolved_services.subtype_field_constraints_by_object,
            policy=resolved_services.policy,
        ),
        FieldReferenceConstraintRule(
            enum_values_by_key=resolved_services.enum_memberships_by_key,
            type_memberships_by_key=resolved_services.type_memberships_by_key,
            value_memberships_by_key=resolved_services.value_memberships_by_key,
            known_scopes=resolved_services.known_scopes,
            alias_memberships_by_family=resolved_services.alias_memberships_by_family,
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
            subtype_field_constraints_by_object=resolved_services.subtype_field_constraints_by_object,
            link_definitions_by_name=resolved_services.link_definitions_by_name,
            policy=resolved_services.policy,
        ),
        ErrorIfOnlyMatchRule(
            enum_values_by_key=resolved_services.enum_memberships_by_key,
            type_memberships_by_key=resolved_services.type_memberships_by_key,
            value_memberships_by_key=resolved_services.value_memberships_by_key,
            known_scopes=resolved_services.known_scopes,
            alias_memberships_by_family=resolved_services.alias_memberships_by_family,
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
            subtype_field_constraints_by_object=resolved_services.subtype_field_constraints_by_object,
            link_definitions_by_name=resolved_services.link_definitions_by_name,
            asset_registry=resolved_services.asset_registry,
            policy=resolved_services.policy,
        ),
        LocalisationKeyExistenceRule(
            localisation_key_provider=resolved_services.localisation_key_provider,
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
            subtype_field_constraints_by_object=resolved_services.subtype_field_constraints_by_object,
            policy=resolved_services.policy,
        ),
        TypeLocalisationRequirementRule(
            type_memberships_by_key=resolved_services.type_memberships_by_key,
            type_localisation_templates_by_type=resolved_services.type_localisation_templates_by_type,
            localisation_key_provider=resolved_services.localisation_key_provider,
            policy=resolved_services.policy,
        ),
        AliasExecutionRule(
            alias_definitions_by_family=resolved_services.alias_definitions_by_family,
            alias_invocations_by_object=resolved_services.alias_invocations_by_object,
            single_alias_definitions_by_name=resolved_services.single_alias_definitions_by_name,
            single_alias_invocations_by_object=resolved_services.single_alias_invocations_by_object,
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
            subtype_field_constraints_by_object=resolved_services.subtype_field_constraints_by_object,
            asset_registry=resolved_services.asset_registry,
            policy=resolved_services.policy,
        ),
        LocalisationCommandScopeRule(
            localisation_command_definitions_by_name=resolved_services.localisation_command_definitions_by_name,
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
            subtype_field_constraints_by_object=resolved_services.subtype_field_constraints_by_object,
            policy=resolved_services.policy,
        ),
        FieldScopeContextRule(
            subtype_matchers_by_object=resolved_services.subtype_matchers_by_object,
        ),
    ]
    return tuple(sorted(rules, key=lambda rule: (rule.code, rule.name)))


def validate_typecheck_rules(rules: tuple[TypecheckRule, ...]) -> None:
    for rule in rules:
        if rule.domain != "correctness":
            raise ValueError(
                f"Typecheck rule `{rule.name}` has invalid domain `{rule.domain}`; expected `correctness`."
            )
        if rule.confidence != "sound":
            raise ValueError(
                f"Typecheck rule `{rule.name}` has invalid confidence `{rule.confidence}`; expected `sound`."
            )
        if not rule.code.startswith("TYPECHECK_"):
            raise ValueError(
                f"Typecheck rule `{rule.name}` has invalid code `{rule.code}`; expected `TYPECHECK_` prefix."
            )


def _find_key_range(text: str, key: str) -> TextRange:
    needle = f"{key}="
    index = text.find(needle)
    if index < 0:
        return TextRange.empty(TextSize(0))
    return TextRange.at(TextSize(index), TextSize(len(key)))


def _find_key_occurrence_range(text: str, key: str, occurrence: int) -> TextRange:
    needle = f"{key}="
    start = 0
    index = -1
    for _ in range(occurrence + 1):
        index = text.find(needle, start)
        if index < 0:
            return _find_key_range(text, key)
        start = index + len(needle)
    return TextRange.at(TextSize(index), TextSize(len(key)))


def _resolve_effective_field_constraint(
    *,
    object_key: str,
    object_occurrence: int,
    field_name: str,
    base_constraints: Mapping[str, RuleFieldConstraint],
    subtype_matchers: tuple[SubtypeMatcher, ...],
    subtype_constraints: Mapping[str, Mapping[str, RuleFieldConstraint]],
    facts: AnalysisFacts,
) -> RuleFieldConstraint | None:
    base = base_constraints.get(field_name)
    active_subtypes = _resolve_active_subtypes(
        object_key=object_key,
        object_occurrence=object_occurrence,
        matchers=subtype_matchers,
        facts=facts,
    )
    merged = base
    for subtype_name in active_subtypes:
        subtype_by_field = subtype_constraints.get(subtype_name)
        if not subtype_by_field:
            continue
        subtype_constraint = subtype_by_field.get(field_name)
        if subtype_constraint is None:
            continue
        if merged is None:
            merged = subtype_constraint
            continue
        merged = RuleFieldConstraint(
            required=merged.required or subtype_constraint.required,
            value_specs=_merge_value_specs(merged.value_specs, subtype_constraint.value_specs),
            comparison=merged.comparison or subtype_constraint.comparison,
            error_if_only_match=merged.error_if_only_match or subtype_constraint.error_if_only_match,
            outgoing_reference_label=merged.outgoing_reference_label or subtype_constraint.outgoing_reference_label,
            incoming_reference_label=merged.incoming_reference_label or subtype_constraint.incoming_reference_label,
        )
    return merged


def _resolve_active_subtypes(
    *,
    object_key: str,
    object_occurrence: int,
    matchers: tuple[SubtypeMatcher, ...],
    facts: AnalysisFacts,
) -> tuple[str, ...]:
    matcher = _resolve_active_subtype_matcher(
        object_key=object_key,
        object_occurrence=object_occurrence,
        matchers=matchers,
        facts=facts,
    )
    if matcher is None:
        return ()
    return (matcher.subtype_name,)


def _resolve_subtype_push_scopes(
    *,
    object_key: str,
    object_occurrence: int,
    matchers: tuple[SubtypeMatcher, ...],
    facts: AnalysisFacts,
) -> tuple[str, ...]:
    matcher = _resolve_active_subtype_matcher(
        object_key=object_key,
        object_occurrence=object_occurrence,
        matchers=matchers,
        facts=facts,
    )
    if matcher is None:
        return ()
    return matcher.push_scope


def _resolve_active_subtype_matcher(
    *,
    object_key: str,
    object_occurrence: int,
    matchers: tuple[SubtypeMatcher, ...],
    facts: AnalysisFacts,
) -> SubtypeMatcher | None:
    if not matchers:
        return None
    fields = facts.object_fields.get(object_key, ())
    by_field: dict[str, list[AstScalar]] = {}
    for field_fact in fields:
        if field_fact.object_occurrence != object_occurrence:
            continue
        if not isinstance(field_fact.value, AstScalar):
            continue
        by_field.setdefault(field_fact.field_key, []).append(field_fact.value)
    for matcher in matchers:
        if _matcher_applies(matcher, object_key=object_key, by_field=by_field):
            return matcher
    return None


def _matcher_applies(
    matcher: SubtypeMatcher,
    *,
    object_key: str,
    by_field: Mapping[str, list[AstScalar]],
) -> bool:
    if matcher.type_key_filters and object_key not in matcher.type_key_filters:
        return False
    if matcher.excluded_type_key_filters and object_key in matcher.excluded_type_key_filters:
        return False
    if matcher.starts_with and not object_key.startswith(matcher.starts_with):
        return False
    for field_name, expected_value in matcher.expected_field_values:
        candidates = by_field.get(field_name, [])
        if not candidates:
            return False
        if not any(_strip_scalar_quotes(value.raw_text) == expected_value for value in candidates):
            return False
    return True


def _matches_value_specs(
    value: object | None,
    specs: tuple[RuleValueSpec, ...],
    *,
    asset_registry: AssetRegistry,
    policy: TypecheckPolicy,
) -> bool:
    if not specs:
        return True
    return any(
        _matches_value_spec(value, spec, asset_registry=asset_registry, policy=policy)
        for spec in specs
    )


def _has_reference_specs(specs: tuple[RuleValueSpec, ...]) -> bool:
    return any(spec.kind in _REFERENCE_SPEC_KINDS for spec in specs)


def _matches_value_spec(
    value: object | None,
    spec: RuleValueSpec,
    *,
    asset_registry: AssetRegistry,
    policy: TypecheckPolicy,
) -> bool:
    if spec.kind in {"missing", "unknown_ref"}:
        return True
    if spec.kind in _REFERENCE_SPEC_KINDS:
        return False
    if spec.kind == "block":
        return isinstance(value, AstBlock)
    if spec.kind == "tagged_block":
        return isinstance(value, AstTaggedBlockValue)
    if spec.kind == "error":
        return True
    if spec.kind != "primitive":
        return True
    if not isinstance(value, AstScalar):
        return False
    primitive = spec.primitive
    if primitive is None:
        return True
    return _matches_primitive(
        value=value,
        primitive=primitive,
        argument=spec.argument,
        asset_registry=asset_registry,
        policy=policy,
    )


def _matches_primitive(
    *,
    value: AstScalar,
    primitive: str,
    argument: str | None,
    asset_registry: AssetRegistry,
    policy: TypecheckPolicy,
) -> bool:
    parsed = interpret_scalar(value.raw_text, was_quoted=value.was_quoted)
    number_value = parsed.number_value

    if primitive in {"scalar", "localisation", "localisation_synced", "localisation_inline"}:
        return True
    if primitive == "bool":
        return parsed.bool_value is not None
    if primitive == "int":
        return _matches_numeric(number_value, argument=argument, require_int=True)
    if primitive == "float":
        return _matches_numeric(number_value, argument=argument, require_int=False)
    if primitive == "date_field":
        return parsed.date_value is not None
    if primitive == "percentage_field":
        raw = value.raw_text.strip()
        if not raw.endswith("%"):
            return False
        return interpret_scalar(raw[:-1], was_quoted=value.was_quoted).number_value is not None
    if primitive in {"variable_field", "value_field"}:
        return _matches_numeric_or_reference(value.raw_text, number_value, argument=argument, require_int=False)
    if primitive in {"int_variable_field", "int_value_field"}:
        return _matches_numeric_or_reference(value.raw_text, number_value, argument=argument, require_int=True)
    if primitive in {"filepath", "icon", "scope_field"}:
        if primitive == "scope_field":
            return True
        return _matches_asset_primitive(
            raw_text=value.raw_text,
            primitive=primitive,
            argument=argument,
            asset_registry=asset_registry,
            policy=policy,
        )
    return True


def _matches_numeric(number_value: int | float | None, *, argument: str | None, require_int: bool) -> bool:
    if number_value is None:
        return False
    if require_int and not isinstance(number_value, int):
        return False
    range_bounds = _parse_range_argument(argument)
    if range_bounds is None:
        return True
    return _in_range(float(number_value), range_bounds)


def _matches_numeric_or_reference(
    raw_text: str,
    number_value: int | float | None,
    *,
    argument: str | None,
    require_int: bool,
) -> bool:
    if number_value is not None:
        if require_int and not isinstance(number_value, int):
            return False
        bounds = _parse_range_argument(argument)
        if bounds is None:
            return True
        return _in_range(float(number_value), bounds)
    return _VARIABLE_REF_PATTERN.fullmatch(raw_text.strip()) is not None


def _matches_asset_primitive(
    *,
    raw_text: str,
    primitive: str,
    argument: str | None,
    asset_registry: AssetRegistry,
    policy: TypecheckPolicy,
) -> bool:
    raw_value = _strip_scalar_quotes(raw_text)
    if not raw_value:
        return False

    if primitive == "filepath":
        candidate = _build_filepath_candidate(raw_value=raw_value, argument=argument)
    elif primitive == "icon":
        candidate = _build_icon_candidate(raw_value=raw_value, argument=argument)
    else:
        return True

    if not candidate:
        return False

    lookup = asset_registry.lookup(candidate)
    if lookup.status == AssetLookupStatus.UNKNOWN:
        return policy.unresolved_asset == "defer"
    return lookup.status == AssetLookupStatus.FOUND


def _matches_reference_specs(
    value: object | None,
    specs: tuple[RuleValueSpec, ...],
    *,
    enum_values_by_key: Mapping[str, frozenset[str]],
    known_type_keys: frozenset[str],
    type_memberships_by_key: Mapping[str, frozenset[str]],
    value_memberships_by_key: Mapping[str, frozenset[str]],
    known_scopes: frozenset[str],
    alias_memberships_by_family: Mapping[str, frozenset[str]],
    link_definitions_by_name: Mapping[str, LinkDefinition],
    scope_context: ScopeContext,
    policy: TypecheckPolicy,
) -> bool:
    return any(
        _matches_reference_spec(
            value,
            spec,
            enum_values_by_key=enum_values_by_key,
            known_type_keys=known_type_keys,
            type_memberships_by_key=type_memberships_by_key,
            value_memberships_by_key=value_memberships_by_key,
            known_scopes=known_scopes,
            alias_memberships_by_family=alias_memberships_by_family,
            link_definitions_by_name=link_definitions_by_name,
            scope_context=scope_context,
            policy=policy,
        )
        for spec in specs
    )


def _matches_reference_spec(
    value: object | None,
    spec: RuleValueSpec,
    *,
    enum_values_by_key: Mapping[str, frozenset[str]],
    known_type_keys: frozenset[str],
    type_memberships_by_key: Mapping[str, frozenset[str]],
    value_memberships_by_key: Mapping[str, frozenset[str]],
    known_scopes: frozenset[str],
    alias_memberships_by_family: Mapping[str, frozenset[str]],
    link_definitions_by_name: Mapping[str, LinkDefinition],
    scope_context: ScopeContext,
    policy: TypecheckPolicy,
) -> bool:
    if not isinstance(value, AstScalar):
        return False
    raw = _strip_scalar_quotes(value.raw_text)
    key = (spec.argument or "").strip()

    if spec.kind == "enum_ref":
        allowed = enum_values_by_key.get(key)
        if allowed is None:
            return policy.unresolved_reference == "defer"
        return raw in allowed

    if spec.kind == "type_ref":
        raw_pattern = spec.raw.strip()
        parsed_pattern = _TYPE_REF_PATTERN.match(raw_pattern)
        if parsed_pattern is not None:
            key = parsed_pattern.group("type_key").strip()
        if not key:
            return policy.unresolved_reference == "defer"
        if key not in known_type_keys:
            return False
        members = type_memberships_by_key.get(key)
        if members is None:
            return policy.unresolved_reference == "defer"
        if parsed_pattern is None:
            return raw in members
        prefix = parsed_pattern.group("prefix")
        suffix = parsed_pattern.group("suffix")
        if not raw.startswith(prefix):
            return False
        if suffix and not raw.endswith(suffix):
            return False
        inner = raw[len(prefix) :]
        if suffix:
            inner = inner[: -len(suffix)]
        return inner in members

    if spec.kind == "scope_ref":
        if not key:
            return policy.unresolved_reference == "defer"
        if not known_scopes:
            return policy.unresolved_reference == "defer"
        candidate_raw = raw.strip()
        candidate = candidate_raw.lower()
        if candidate in _SCOPE_ALIAS_KEYS:
            resolved = scope_context.aliases.get(candidate)
            if resolved is None:
                return policy.unresolved_reference == "defer"
            candidate = resolved
        elif candidate not in known_scopes:
            link_scope = _resolve_scope_from_link_candidate(
                candidate=candidate_raw,
                scope_context=scope_context,
                link_definitions_by_name=link_definitions_by_name,
                enum_values_by_key=enum_values_by_key,
                known_type_keys=known_type_keys,
                type_memberships_by_key=type_memberships_by_key,
                value_memberships_by_key=value_memberships_by_key,
                alias_memberships_by_family=alias_memberships_by_family,
                policy=policy,
            )
            if link_scope is None:
                return policy.unresolved_reference == "defer"
            candidate = link_scope
        return candidate == key.lower()

    if spec.kind == "value_set_ref":
        # Setter declarations register values; they do not require prior membership.
        return True

    if spec.kind == "value_ref":
        if not key:
            return policy.unresolved_reference == "defer"
        members = value_memberships_by_key.get(key)
        if members is None:
            return policy.unresolved_reference == "defer"
        return raw in members
    if spec.kind == "alias_match_left_ref":
        if not key:
            return policy.unresolved_reference == "defer"
        members = alias_memberships_by_family.get(key)
        if members is None:
            return policy.unresolved_reference == "defer"
        return raw in members

    return False


def _build_filepath_candidate(*, raw_value: str, argument: str | None) -> str:
    if argument is None:
        return raw_value

    spec = argument.strip()
    if not spec:
        return raw_value

    prefix = spec
    extension = ""
    if "," in spec:
        prefix, extension = (part.strip() for part in spec.split(",", 1))
    return f"{prefix}{raw_value}{extension}"


def _resolve_scope_from_link_candidate(
    *,
    candidate: str,
    scope_context: ScopeContext,
    link_definitions_by_name: Mapping[str, LinkDefinition],
    enum_values_by_key: Mapping[str, frozenset[str]],
    known_type_keys: frozenset[str],
    type_memberships_by_key: Mapping[str, frozenset[str]],
    value_memberships_by_key: Mapping[str, frozenset[str]],
    alias_memberships_by_family: Mapping[str, frozenset[str]],
    policy: TypecheckPolicy,
) -> str | None:
    segments = tuple(part.strip() for part in candidate.split(".") if part.strip())
    if not segments:
        return None
    active_scopes = set(scope_context.active_scopes)
    for segment in segments:
        next_scopes = _resolve_link_segment_scopes(
            segment=segment,
            active_scopes=frozenset(active_scopes),
            link_definitions_by_name=link_definitions_by_name,
            enum_values_by_key=enum_values_by_key,
            known_type_keys=known_type_keys,
            type_memberships_by_key=type_memberships_by_key,
            value_memberships_by_key=value_memberships_by_key,
            alias_memberships_by_family=alias_memberships_by_family,
            policy=policy,
        )
        if next_scopes is None:
            return None
        active_scopes = set(next_scopes)
    if not active_scopes:
        return None
    unique = tuple(sorted(active_scopes))
    if len(unique) != 1:
        return None
    return unique[0]


def _resolve_link_segment_scopes(
    *,
    segment: str,
    active_scopes: frozenset[str],
    link_definitions_by_name: Mapping[str, LinkDefinition],
    enum_values_by_key: Mapping[str, frozenset[str]],
    known_type_keys: frozenset[str],
    type_memberships_by_key: Mapping[str, frozenset[str]],
    value_memberships_by_key: Mapping[str, frozenset[str]],
    alias_memberships_by_family: Mapping[str, frozenset[str]],
    policy: TypecheckPolicy,
) -> tuple[str, ...] | None:
    valid_scopes: set[str] = set()
    saw_unresolved = False
    if ":" in segment:
        prefix_head, value_key = segment.split(":", 1)
        prefix = prefix_head.lower() + ":"
        value_key = value_key.strip()
        matches = [link for link in link_definitions_by_name.values() if (link.prefix or "").lower() == prefix]
        if not matches:
            return None
        for link in matches:
            output_scope = (link.output_scope or "").strip().lower()
            if not output_scope:
                saw_unresolved = True
                continue
            if not _link_input_scope_allows(link, active_scopes=active_scopes, policy=policy):
                continue
            if not _link_data_source_allows(
                link,
                value_key=value_key,
                enum_values_by_key=enum_values_by_key,
                known_type_keys=known_type_keys,
                type_memberships_by_key=type_memberships_by_key,
                value_memberships_by_key=value_memberships_by_key,
                alias_memberships_by_family=alias_memberships_by_family,
                policy=policy,
            ):
                continue
            valid_scopes.add(output_scope)
    else:
        matches = [link for link in link_definitions_by_name.values() if link.name.lower() == segment.lower()]
        if not matches:
            return None
        for link in matches:
            output_scope = (link.output_scope or "").strip().lower()
            if not output_scope:
                saw_unresolved = True
                continue
            if link.from_data:
                saw_unresolved = True
                continue
            if not _link_input_scope_allows(link, active_scopes=active_scopes, policy=policy):
                continue
            valid_scopes.add(output_scope)
    if valid_scopes:
        return tuple(sorted(valid_scopes))
    if saw_unresolved and policy.unresolved_reference == "defer":
        return None
    return None


def _link_input_scope_allows(
    link: LinkDefinition,
    *,
    active_scopes: frozenset[str],
    policy: TypecheckPolicy,
) -> bool:
    if not link.input_scopes:
        return True
    normalized = {scope.lower() for scope in link.input_scopes}
    if "any" in normalized:
        return True
    if not active_scopes:
        return policy.unresolved_reference == "defer"
    return bool(set(active_scopes).intersection(normalized))


def _link_data_source_allows(
    link: LinkDefinition,
    *,
    value_key: str,
    enum_values_by_key: Mapping[str, frozenset[str]],
    known_type_keys: frozenset[str],
    type_memberships_by_key: Mapping[str, frozenset[str]],
    value_memberships_by_key: Mapping[str, frozenset[str]],
    alias_memberships_by_family: Mapping[str, frozenset[str]],
    policy: TypecheckPolicy,
) -> bool:
    if not link.from_data:
        return True
    if not value_key:
        return False
    if not link.data_sources:
        return policy.unresolved_reference == "defer"

    saw_unresolved = False
    for data_source in link.data_sources:
        match = _matches_link_data_source(
            data_source=data_source,
            value_key=value_key,
            enum_values_by_key=enum_values_by_key,
            known_type_keys=known_type_keys,
            type_memberships_by_key=type_memberships_by_key,
            value_memberships_by_key=value_memberships_by_key,
            alias_memberships_by_family=alias_memberships_by_family,
        )
        if match is True:
            return True
        if match is None:
            saw_unresolved = True
    if saw_unresolved:
        return policy.unresolved_reference == "defer"
    return False


def _matches_link_data_source(
    *,
    data_source: str,
    value_key: str,
    enum_values_by_key: Mapping[str, frozenset[str]],
    known_type_keys: frozenset[str],
    type_memberships_by_key: Mapping[str, frozenset[str]],
    value_memberships_by_key: Mapping[str, frozenset[str]],
    alias_memberships_by_family: Mapping[str, frozenset[str]],
) -> bool | None:
    raw = data_source.strip()
    if not raw:
        return None
    source_type = _TYPE_REF_PATTERN.fullmatch(raw)
    if source_type is not None:
        type_key = source_type.group("type_key")
        if type_key not in known_type_keys:
            return False
        members = type_memberships_by_key.get(type_key)
        if members is None:
            return None
        return value_key in members
    if not raw.endswith("]") or "[" not in raw:
        return None
    family, argument = raw.split("[", 1)
    family = family.strip().lower()
    argument = argument[:-1].strip()
    if not argument:
        return None
    if family == "value":
        members = value_memberships_by_key.get(argument)
        if members is None:
            return None
        return value_key in members
    if family == "type":
        if argument not in known_type_keys:
            return False
        members = type_memberships_by_key.get(argument)
        if members is None:
            return None
        return value_key in members
    if family == "enum":
        members = enum_values_by_key.get(argument)
        if members is None:
            return None
        return value_key in members
    if family in {"alias_match_left", "alias_name", "alias"}:
        members = alias_memberships_by_family.get(argument)
        if members is None:
            return None
        return value_key in members
    return None


def _build_icon_candidate(*, raw_value: str, argument: str | None) -> str:
    if argument is None:
        return f"{raw_value}.dds"
    prefix = argument.strip().rstrip("/")
    if not prefix:
        return f"{raw_value}.dds"
    return f"{prefix}/{raw_value}.dds"


def _allows_localisation_primitive(specs: tuple[RuleValueSpec, ...]) -> bool:
    return any(
        spec.kind == "primitive" and spec.primitive in {"localisation", "localisation_synced", "localisation_inline"}
        for spec in specs
    )


def _allows_localisation_key_primitive(specs: tuple[RuleValueSpec, ...]) -> bool:
    return any(
        spec.kind == "primitive" and spec.primitive in {"localisation", "localisation_synced"}
        for spec in specs
    )


def _extract_localisation_key_reference(raw_text: str) -> str | None:
    text = _strip_scalar_quotes(raw_text).strip()
    if not text:
        return None
    if "[" in text or "]" in text:
        return None
    if text.startswith("$"):
        return None
    if any(ch.isspace() for ch in text):
        return None
    return text


def _extract_localisation_commands(raw_text: str) -> tuple[str, ...]:
    text = _strip_scalar_quotes(raw_text)
    commands: list[str] = []
    seen: set[str] = set()
    for match in _LOCALISATION_TOKEN_PATTERN.finditer(text):
        body = match.group("body").strip()
        if not body or "?" in body or ":" in body:
            continue
        parts = [part.strip() for part in body.split(".") if part.strip()]
        if not parts:
            continue
        candidate = parts[-1]
        if _LOCALISATION_IDENTIFIER_PATTERN.fullmatch(candidate) is None:
            continue
        if len(parts) < 2 and not candidate.startswith("Get"):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        commands.append(candidate)
    return tuple(commands)


def _strip_scalar_quotes(raw_text: str) -> str:
    stripped = raw_text.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def _parse_range_argument(argument: str | None) -> tuple[float | None, float | None] | None:
    if argument is None:
        return None
    match = _RANGE_PATTERN.fullmatch(argument.strip().lower())
    if match is None:
        return None
    return (_parse_range_bound(match.group("min")), _parse_range_bound(match.group("max")))


def _parse_range_bound(raw: str) -> float | None:
    if raw in {"-inf", "inf"}:
        return None
    return float(raw)


def _in_range(value: float, bounds: tuple[float | None, float | None]) -> bool:
    minimum, maximum = bounds
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


def _format_value_specs(specs: tuple[RuleValueSpec, ...]) -> str:
    rendered: list[str] = []
    for spec in specs:
        if spec.kind == "primitive":
            rendered.append(spec.raw)
        else:
            rendered.append(spec.raw)
    if not rendered:
        return "schema constraints"
    return " | ".join(rendered)


def _build_dynamic_value_memberships(
    *,
    facts: AnalysisFacts,
    constraints: dict[str, dict[str, RuleFieldConstraint]],
) -> Mapping[str, frozenset[str]]:
    collected: dict[str, set[str]] = {}
    for object_key, field_constraints in constraints.items():
        field_map = facts.object_field_map.get(object_key)
        if not field_map:
            continue
        for field_name, constraint in field_constraints.items():
            keys = {
                (spec.argument or "").strip()
                for spec in constraint.value_specs
                if spec.kind == "value_set_ref" and (spec.argument or "").strip()
            }
            if not keys:
                continue
            for field_fact in field_map.get(field_name, ()):
                if not isinstance(field_fact.value, AstScalar):
                    continue
                value = _strip_scalar_quotes(field_fact.value.raw_text.strip())
                if not value:
                    continue
                for key in keys:
                    collected.setdefault(key, set()).add(value)
    return {key: frozenset(values) for key, values in collected.items()}


def _merge_membership_maps(
    left: Mapping[str, frozenset[str]],
    right: Mapping[str, frozenset[str]],
) -> Mapping[str, frozenset[str]]:
    merged: dict[str, set[str]] = {}
    for key, values in left.items():
        merged.setdefault(key, set()).update(values)
    for key, values in right.items():
        merged.setdefault(key, set()).update(values)
    return {key: frozenset(values) for key, values in merged.items()}


def _merge_value_specs(
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


def _resolve_active_scopes_before_path(
    *,
    relative_path: tuple[str, ...],
    by_path: Mapping[tuple[str, ...], RuleFieldScopeConstraint],
    initial_push_scopes: tuple[str, ...] = (),
) -> set[str]:
    context = _resolve_scope_context_before_path(
        relative_path=relative_path,
        by_path=by_path,
        initial_push_scopes=initial_push_scopes,
    )
    return set(context.active_scopes)


def _resolve_scope_context_before_path(
    *,
    relative_path: tuple[str, ...],
    by_path: Mapping[tuple[str, ...], RuleFieldScopeConstraint],
    initial_push_scopes: tuple[str, ...] = (),
) -> ScopeContext:
    aliases: dict[str, str] = {}
    ambiguity: str | None = None
    for scope in initial_push_scopes:
        _apply_push_scope(aliases, scope.lower())
    path_prefixes: list[tuple[str, ...]] = [()]
    for i in range(1, len(relative_path)):
        path_prefixes.append(relative_path[:i])

    for prefix in path_prefixes:
        constraint = by_path.get(prefix)
        if constraint is None:
            continue
        if constraint.push_scope:
            for scope in constraint.push_scope:
                _apply_push_scope(aliases, scope.lower())
            # CWTools precedence: when push_scope is present, replace_scope is not applied.
            continue
        if constraint.replace_scope:
            seen_local: dict[str, str] = {}
            for replacement in constraint.replace_scope:
                source = replacement.source.lower()
                target = replacement.target.lower()
                previous = seen_local.get(source)
                if previous is not None and previous != target and ambiguity is None:
                    ambiguity = (
                        f"replace_scope maps `{source}` to both `{previous}` and `{target}` at path "
                        f"`{'.'.join(prefix) or '<root>'}`"
                    )
                seen_local[source] = target
                aliases[source] = target
                if source == "this" and "root" not in aliases:
                    aliases["root"] = target
    active_scopes = frozenset(scope for scope in aliases.values() if scope)
    return ScopeContext(
        active_scopes=active_scopes,
        aliases=MappingProxyType(dict(aliases)),
        ambiguity=ambiguity,
    )


def _apply_push_scope(aliases: dict[str, str], scope: str) -> None:
    for idx in range(len(_PREV_ALIAS_ORDER) - 1, 0, -1):
        aliases[_PREV_ALIAS_ORDER[idx]] = aliases.get(_PREV_ALIAS_ORDER[idx - 1], "")
    aliases["prev"] = aliases.get("this", "")
    for idx in range(len(_SCOPE_ALIAS_ORDER) - 1, 0, -1):
        aliases[_SCOPE_ALIAS_ORDER[idx]] = aliases.get(_SCOPE_ALIAS_ORDER[idx - 1], "")
    aliases["this"] = scope
    aliases.setdefault("root", scope)
