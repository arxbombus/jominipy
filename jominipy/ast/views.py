"""AST consumer views built on top of canonical AST nodes."""

from __future__ import annotations

from dataclasses import dataclass

from jominipy.ast.model import (
    AstArrayValue,
    AstBlock,
    AstObject,
    AstObjectMultimap,
    AstObjectValue,
    AstScalar,
)
from jominipy.ast.scalar import ScalarInterpretation, interpret_scalar


@dataclass(frozen=True, slots=True)
class AstBlockView:
    """Explicit consumer view over an `AstBlock`."""

    block: AstBlock

    @property
    def is_empty_ambiguous(self) -> bool:
        return self.block.is_empty_ambiguous

    @property
    def is_object_like(self) -> bool:
        return self.block.is_object_like

    @property
    def is_array_like(self) -> bool:
        return self.block.is_array_like

    @property
    def is_mixed(self) -> bool:
        return self.block.is_mixed

    def as_object(self) -> AstObject | None:
        if not (self.is_object_like or self.is_empty_ambiguous):
            return None
        return self.block.to_object()

    def as_multimap(self) -> AstObjectMultimap | None:
        if not (self.is_object_like or self.is_empty_ambiguous):
            return None
        return self.block.to_object(multimap=True)

    def as_array(self) -> list[AstArrayValue] | None:
        if not (self.is_array_like or self.is_empty_ambiguous):
            return None
        return self.block.to_array()

    def get_scalar(
        self,
        key: str,
        *,
        allow_quoted: bool = False,
    ) -> ScalarInterpretation | None:
        object_view = self.as_object()
        if object_view is None:
            return None

        scalar = _as_scalar(object_view.get(key))
        if scalar is None:
            return None

        return _interpret_from_scalar(scalar, allow_quoted=allow_quoted)

    def get_scalar_all(
        self,
        key: str,
        *,
        allow_quoted: bool = False,
    ) -> list[ScalarInterpretation]:
        multimap_view = self.as_multimap()
        if multimap_view is None:
            return []

        interpretations: list[ScalarInterpretation] = []
        for value in multimap_view.get(key, []):
            scalar = _as_scalar(value)
            if scalar is None:
                continue
            interpretations.append(_interpret_from_scalar(scalar, allow_quoted=allow_quoted))
        return interpretations


def _as_scalar(value: AstObjectValue | None) -> AstScalar | None:
    if isinstance(value, AstScalar):
        return value
    return None


def _interpret_from_scalar(
    scalar: AstScalar,
    *,
    allow_quoted: bool,
) -> ScalarInterpretation:
    text = scalar.raw_text
    if scalar.was_quoted and allow_quoted:
        text = _strip_matching_quotes(text)

    return interpret_scalar(
        text,
        was_quoted=scalar.was_quoted,
        allow_quoted=allow_quoted,
    )


def _strip_matching_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


__all__ = ["AstBlockView"]
