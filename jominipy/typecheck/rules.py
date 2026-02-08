"""Type-check rules and rule contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Literal, Mapping, Protocol

from jominipy.analysis import AnalysisFacts
from jominipy.ast import (
    AstBlock,
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
    Diagnostic,
)
from jominipy.rules.adapter import SubtypeMatcher
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

            active_scopes = _resolve_active_scopes_before_path(relative_path=relative_path, by_path=by_object)
            scope_context = _resolve_scope_context_before_path(relative_path=relative_path, by_path=by_object)
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
            if active_scopes and required.intersection(active_scopes):
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
            policy=resolved_services.policy,
        ),
        FieldScopeContextRule(),
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
        )
    return merged


def _resolve_active_subtypes(
    *,
    object_key: str,
    object_occurrence: int,
    matchers: tuple[SubtypeMatcher, ...],
    facts: AnalysisFacts,
) -> tuple[str, ...]:
    if not matchers:
        return ()
    fields = facts.object_fields.get(object_key, ())
    by_field: dict[str, list[AstScalar]] = {}
    for field_fact in fields:
        if field_fact.object_occurrence != object_occurrence:
            continue
        if not isinstance(field_fact.value, AstScalar):
            continue
        by_field.setdefault(field_fact.field_key, []).append(field_fact.value)
    active: list[str] = []
    for matcher in matchers:
        if _matcher_applies(matcher, by_field=by_field):
            active.append(matcher.subtype_name)
    return tuple(active)


def _matcher_applies(
    matcher: SubtypeMatcher,
    *,
    by_field: Mapping[str, list[AstScalar]],
) -> bool:
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
        candidate = raw.strip().lower()
        if candidate in _SCOPE_ALIAS_KEYS:
            resolved = scope_context.aliases.get(candidate)
            if resolved is None:
                return policy.unresolved_reference == "defer"
            candidate = resolved
        elif candidate not in known_scopes:
            return policy.unresolved_reference == "defer"
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


def _build_icon_candidate(*, raw_value: str, argument: str | None) -> str:
    if argument is None:
        return f"{raw_value}.dds"
    prefix = argument.strip().rstrip("/")
    if not prefix:
        return f"{raw_value}.dds"
    return f"{prefix}/{raw_value}.dds"


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
) -> set[str]:
    context = _resolve_scope_context_before_path(relative_path=relative_path, by_path=by_path)
    return set(context.active_scopes)


def _resolve_scope_context_before_path(
    *,
    relative_path: tuple[str, ...],
    by_path: Mapping[tuple[str, ...], RuleFieldScopeConstraint],
) -> ScopeContext:
    aliases: dict[str, str] = {}
    ambiguity: str | None = None
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
