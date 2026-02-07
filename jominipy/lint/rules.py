"""Lint rules and rule contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Protocol

from jominipy.analysis import AnalysisFacts
from jominipy.ast import AstBlock
from jominipy.diagnostics import (
    LINT_SEMANTIC_INCONSISTENT_SHAPE,
    LINT_SEMANTIC_MISSING_REQUIRED_FIELD,
    LINT_STYLE_SINGLE_LINE_BLOCK,
    Diagnostic,
)
from jominipy.rules.semantics import load_hoi4_required_fields
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
