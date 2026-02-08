"""Lint rules and rule contracts."""

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
    LINT_SEMANTIC_INCONSISTENT_SHAPE,
    LINT_SEMANTIC_INVALID_FIELD_TYPE,
    LINT_SEMANTIC_MISSING_REQUIRED_FIELD,
    LINT_STYLE_SINGLE_LINE_BLOCK,
    Diagnostic,
)
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    load_hoi4_field_constraints,
    load_hoi4_required_fields,
)
from jominipy.text import TextRange, TextSize
from jominipy.typecheck.rules import TypecheckFacts

type LintDomain = Literal["semantic", "style", "heuristic"]
type LintConfidence = Literal["policy", "heuristic"]


class LintRule(Protocol):
    """Biome-style lint rule contract."""

    @property
    def code(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def category(self) -> str: ...

    @property
    def domain(self) -> LintDomain: ...

    @property
    def confidence(self) -> LintConfidence: ...

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]: ...


@dataclass(frozen=True, slots=True)
class SemanticInconsistentShapeRule:
    """Semantic scaffold that consumes type-check facts."""

    code: str = LINT_SEMANTIC_INCONSISTENT_SHAPE.code
    name: str = "semanticInconsistentShape"
    category: str = "semantic"
    domain: LintDomain = "semantic"
    confidence: LintConfidence = "heuristic"

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for key in sorted(type_facts.inconsistent_top_level_shapes):
            diagnostics.append(
                Diagnostic(
                    code=self.code,
                    message=f"{LINT_SEMANTIC_INCONSISTENT_SHAPE.message} Key `{key}` should use one shape.",
                    range=_find_key_range(text, key),
                    severity=LINT_SEMANTIC_INCONSISTENT_SHAPE.severity,
                    hint="Move alternative shapes under explicit nested keys.",
                    category=LINT_SEMANTIC_INCONSISTENT_SHAPE.category,
                )
            )
        return diagnostics


@dataclass(frozen=True, slots=True)
class SemanticMissingRequiredFieldRule:
    """Derives required fields from CWTools schema and enforces them on object blocks."""

    code: str = LINT_SEMANTIC_MISSING_REQUIRED_FIELD.code
    name: str = "semanticMissingRequiredField"
    category: str = "semantic"
    domain: LintDomain = "semantic"
    confidence: LintConfidence = "policy"
    required_fields_by_object: dict[str, tuple[str, ...]] | None = None

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        required = self.required_fields_by_object
        if required is None:
            required = load_hoi4_required_fields(include_implicit_required=False)

        diagnostics: list[Diagnostic] = []
        for key, values in facts.top_level_values.items():
            object_required = required.get(key)
            if object_required is None:
                continue
            for value in values:
                if not isinstance(value, AstBlock):
                    continue
                block_object = value.to_object() if value.is_object_like else None
                if block_object is None:
                    continue
                for required_field in object_required:
                    if required_field in block_object:
                        continue
                    diagnostics.append(
                        Diagnostic(
                            code=self.code,
                            message=(
                                f"{LINT_SEMANTIC_MISSING_REQUIRED_FIELD.message} "
                                f"Object `{key}` is missing `{required_field}`."
                            ),
                            range=_find_key_range(text, key),
                            severity=LINT_SEMANTIC_MISSING_REQUIRED_FIELD.severity,
                            hint=f"Add `{required_field} = ...` to `{key}`.",
                            category=LINT_SEMANTIC_MISSING_REQUIRED_FIELD.category,
                        )
                    )
        return diagnostics


@dataclass(frozen=True, slots=True)
class SemanticInvalidFieldTypeRule:
    """Checks scalar field values against CWTools-derived primitive constraints."""

    code: str = LINT_SEMANTIC_INVALID_FIELD_TYPE.code
    name: str = "semanticInvalidFieldType"
    category: str = "semantic"
    domain: LintDomain = "semantic"
    confidence: LintConfidence = "policy"
    field_constraints_by_object: dict[str, dict[str, RuleFieldConstraint]] | None = None

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        constraints = self.field_constraints_by_object
        if constraints is None:
            constraints = load_hoi4_field_constraints(include_implicit_required=False)

        diagnostics: list[Diagnostic] = []
        for key, values in facts.top_level_values.items():
            object_constraints = constraints.get(key)
            if object_constraints is None:
                continue
            for value in values:
                if not isinstance(value, AstBlock) or not value.is_object_like:
                    continue
                block_object = value.to_object()
                for field_name, field_constraint in object_constraints.items():
                    if field_name not in block_object:
                        continue
                    field_value = block_object[field_name]
                    if _matches_field_constraint(field_value, field_constraint):
                        continue
                    diagnostics.append(
                        Diagnostic(
                            code=self.code,
                            message=(
                                f"{LINT_SEMANTIC_INVALID_FIELD_TYPE.message} "
                                f"`{key}.{field_name}` does not match {_format_value_specs(field_constraint.value_specs)}."
                            ),
                            range=_find_key_range(text, key),
                            severity=LINT_SEMANTIC_INVALID_FIELD_TYPE.severity,
                            hint=f"Use a value matching the CWTools schema for `{field_name}`.",
                            category=LINT_SEMANTIC_INVALID_FIELD_TYPE.category,
                        )
                    )
        return diagnostics


@dataclass(frozen=True, slots=True)
class StyleSingleLineMultiValueBlockRule:
    """Flags `{ ... }` blocks that contain multiple values on one line."""

    code: str = LINT_STYLE_SINGLE_LINE_BLOCK.code
    name: str = "styleSingleLineMultiValueBlock"
    category: str = "style"
    domain: LintDomain = "style"
    confidence: LintConfidence = "policy"

    _pattern: re.Pattern[str] = re.compile(r"\{[^\n{}]*\s+[^\n{}]*\}")

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for match in self._pattern.finditer(text):
            diagnostics.append(
                Diagnostic(
                    code=self.code,
                    message=LINT_STYLE_SINGLE_LINE_BLOCK.message,
                    range=TextRange.at(TextSize(match.start()), TextSize(match.end() - match.start())),
                    severity=LINT_STYLE_SINGLE_LINE_BLOCK.severity,
                    hint="Use multiline layout inside braces when multiple values are present.",
                    category=LINT_STYLE_SINGLE_LINE_BLOCK.category,
                )
            )
        return diagnostics


def default_lint_rules() -> tuple[LintRule, ...]:
    rules: list[LintRule] = [
        SemanticInconsistentShapeRule(),
        SemanticMissingRequiredFieldRule(),
        SemanticInvalidFieldTypeRule(),
        StyleSingleLineMultiValueBlockRule(),
    ]
    return tuple(sorted(rules, key=lambda rule: (rule.category, rule.code, rule.name)))


def validate_lint_rules(rules: tuple[LintRule, ...]) -> None:
    allowed_domains = {"semantic", "style", "heuristic"}
    allowed_confidence = {"policy", "heuristic"}
    for rule in rules:
        if rule.domain not in allowed_domains:
            raise ValueError(
                f"Lint rule `{rule.name}` has invalid domain `{rule.domain}`; expected semantic/style/heuristic."
            )
        if rule.confidence not in allowed_confidence:
            raise ValueError(
                f"Lint rule `{rule.name}` has invalid confidence `{rule.confidence}`; expected policy/heuristic."
            )
        if not rule.code.startswith("LINT_"):
            raise ValueError(
                f"Lint rule `{rule.name}` has invalid code `{rule.code}`; expected `LINT_` prefix."
            )


def _find_key_range(text: str, key: str) -> TextRange:
    needle = f"{key}="
    index = text.find(needle)
    if index < 0:
        return TextRange.empty(TextSize(0))
    return TextRange.at(TextSize(index), TextSize(len(key)))


def _matches_field_constraint(value: object | None, constraint: RuleFieldConstraint) -> bool:
    if not constraint.value_specs:
        return True
    return any(_matches_value_spec(value, spec) for spec in constraint.value_specs)


def _matches_value_spec(value: object | None, spec: RuleValueSpec) -> bool:
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
    if primitive in {"scalar", "localisation", "localisation_synced", "localisation_inline"}:
        return True
    parsed = interpret_scalar(value.raw_text, was_quoted=value.was_quoted)
    if primitive == "bool":
        return parsed.bool_value is not None
    if primitive == "int":
        number_value = parsed.number_value
        return number_value is not None and isinstance(number_value, int)
    if primitive == "float":
        return parsed.number_value is not None
    return True


def _format_value_specs(specs: tuple[RuleValueSpec, ...]) -> str:
    rendered: list[str] = []
    for spec in specs:
        if spec.kind == "primitive":
            rendered.append(spec.primitive or spec.raw)
        else:
            rendered.append(spec.raw)
    if not rendered:
        return "schema constraints"
    return " | ".join(rendered)
