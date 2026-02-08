"""Type-check rules and rule contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Protocol

from jominipy.analysis import AnalysisFacts
from jominipy.ast import (
    AstBlock,
    AstScalar,
    AstTaggedBlockValue,
    interpret_scalar,
)
from jominipy.diagnostics import (
    TYPECHECK_INCONSISTENT_VALUE_SHAPE,
    TYPECHECK_INVALID_FIELD_TYPE,
    Diagnostic,
)
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    load_hoi4_field_constraints,
)
from jominipy.text import TextRange, TextSize
from jominipy.typecheck.assets import (
    AssetLookupStatus,
    AssetRegistry,
    NullAssetRegistry,
)

type TypecheckDomain = Literal["correctness"]
type TypecheckConfidence = Literal["sound"]

_VARIABLE_REF_PATTERN = re.compile(r"^[A-Za-z_@][A-Za-z0-9_:@.\-]*$")
_RANGE_PATTERN = re.compile(r"^(?P<min>-?(?:\d+\.\d+|\d+)|-?inf)\.\.(?P<max>-?(?:\d+\.\d+|\d+)|inf)$")


@dataclass(frozen=True, slots=True)
class TypecheckFacts:
    """Type facts produced from shared analysis facts."""

    inconsistent_top_level_shapes: dict[str, tuple[str, ...]]


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
    asset_registry: AssetRegistry = NullAssetRegistry()

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)

        diagnostics: list[Diagnostic] = []
        for object_key, field_constraints in constraints.items():
            field_map = facts.object_field_map.get(object_key)
            if not field_map:
                continue

            for field_name, constraint in field_constraints.items():
                field_facts = field_map.get(field_name)
                if not field_facts:
                    continue
                for field_fact in field_facts:
                    if _matches_field_constraint(
                        field_fact.value,
                        constraint,
                        asset_registry=self.asset_registry,
                    ):
                        continue
                    diagnostics.append(
                        Diagnostic(
                            code=self.code,
                            message=(
                                f"{TYPECHECK_INVALID_FIELD_TYPE.message} "
                                f"`{object_key}.{field_name}` does not match {_format_value_specs(constraint.value_specs)}."
                            ),
                            range=_find_key_occurrence_range(text, object_key, field_fact.object_occurrence),
                            severity=TYPECHECK_INVALID_FIELD_TYPE.severity,
                            hint=f"Use a value matching the schema for `{field_name}`.",
                            category=TYPECHECK_INVALID_FIELD_TYPE.category,
                        )
                    )
        return diagnostics


def build_typecheck_facts(facts: AnalysisFacts) -> TypecheckFacts:
    inconsistent: dict[str, tuple[str, ...]] = {}
    for key, shapes in facts.top_level_shapes.items():
        if len(shapes) > 1:
            inconsistent[key] = tuple(sorted(shapes))
    return TypecheckFacts(inconsistent_top_level_shapes=inconsistent)


def default_typecheck_rules() -> tuple[TypecheckRule, ...]:
    rules: list[TypecheckRule] = [InconsistentTopLevelShapeRule(), FieldConstraintRule()]
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


def _matches_field_constraint(
    value: object | None,
    constraint: RuleFieldConstraint,
    *,
    asset_registry: AssetRegistry,
) -> bool:
    if not constraint.value_specs:
        return True
    return any(_matches_value_spec(value, spec, asset_registry=asset_registry) for spec in constraint.value_specs)


def _matches_value_spec(
    value: object | None,
    spec: RuleValueSpec,
    *,
    asset_registry: AssetRegistry,
) -> bool:
    if spec.kind in {"missing", "unknown_ref", "enum_ref", "scope_ref", "value_ref", "value_set_ref", "type_ref"}:
        return True
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
    )


def _matches_primitive(
    *,
    value: AstScalar,
    primitive: str,
    argument: str | None,
    asset_registry: AssetRegistry,
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
        # No project registry configured: skip hard decision for now.
        return True
    return lookup.status == AssetLookupStatus.FOUND


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
