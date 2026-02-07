"""Type-check rules and rule contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from jominipy.analysis import AnalysisFacts
from jominipy.diagnostics import TYPECHECK_INCONSISTENT_VALUE_SHAPE, Diagnostic
from jominipy.text import TextRange, TextSize

type TypecheckDomain = Literal["correctness"]
type TypecheckConfidence = Literal["sound"]


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


def build_typecheck_facts(facts: AnalysisFacts) -> TypecheckFacts:
    inconsistent: dict[str, tuple[str, ...]] = {}
    for key, shapes in facts.top_level_shapes.items():
        if len(shapes) > 1:
            inconsistent[key] = tuple(sorted(shapes))
    return TypecheckFacts(inconsistent_top_level_shapes=inconsistent)


def default_typecheck_rules() -> tuple[TypecheckRule, ...]:
    rules: list[TypecheckRule] = [InconsistentTopLevelShapeRule()]
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
