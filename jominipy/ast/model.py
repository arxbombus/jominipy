"""AST data model for Jomini source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast, overload

from jominipy.syntax import JominiSyntaxKind


@dataclass(frozen=True, slots=True)
class AstScalar:
    """Scalar value preserved as raw CST token text."""

    raw_text: str
    token_kinds: tuple[JominiSyntaxKind, ...]
    was_quoted: bool


@dataclass(frozen=True, slots=True)
class AstTaggedBlockValue:
    """Externally tagged block value, e.g. `rgb { 100 200 150 }`."""

    tag: AstScalar
    block: AstBlock


@dataclass(frozen=True, slots=True)
class AstKeyValue:
    """Key-value statement with optional operator (implicit block assignment)."""

    key: AstScalar
    operator: str | None
    value: AstValue | None


@dataclass(frozen=True, slots=True)
class AstError:
    """Recoverable parse fragment retained during lowering."""

    raw_text: str


@dataclass(frozen=True, slots=True)
class AstBlock:
    """Block statement/value preserving statement order."""

    statements: tuple[AstStatement, ...]

    @property
    def is_empty_ambiguous(self) -> bool:
        return len(self.statements) == 0

    @property
    def is_object_like(self) -> bool:
        return (
            not self.is_empty_ambiguous
            and all(
                isinstance(statement, AstKeyValue) for statement in self.statements
            )
        )

    @property
    def is_array_like(self) -> bool:
        return (
            not self.is_empty_ambiguous
            and all(
                isinstance(statement, (AstScalar, AstBlock, AstTaggedBlockValue))
                for statement in self.statements
            )
        )

    @property
    def is_mixed(self) -> bool:
        if self.is_empty_ambiguous:
            return False

        has_key_values = any(
            isinstance(statement, AstKeyValue) for statement in self.statements
        )
        has_array_values = any(
            isinstance(statement, (AstScalar, AstBlock, AstTaggedBlockValue))
            for statement in self.statements
        )
        return has_key_values and has_array_values

    @overload
    def to_object(self, *, multimap: Literal[False] = False) -> AstObject: ...

    @overload
    def to_object(self, *, multimap: Literal[True]) -> AstObjectMultimap: ...

    def to_object(self, *, multimap: bool = False) -> AstObject | AstObjectMultimap:
        if not (self.is_object_like or self.is_empty_ambiguous):
            raise ValueError("Block is not object-like")

        if multimap:
            multimap_result: AstObjectMultimap = {}
            for statement in self.statements:
                key_value = cast(AstKeyValue, statement)
                key = key_value.key.raw_text
                if key not in multimap_result:
                    multimap_result[key] = []
                multimap_result[key].append(key_value.value)
            return multimap_result

        object_result: AstObject = {}
        for statement in self.statements:
            key_value = cast(AstKeyValue, statement)
            object_result[key_value.key.raw_text] = key_value.value
        return object_result

    def to_array(self) -> list[AstArrayValue]:
        if not (self.is_array_like or self.is_empty_ambiguous):
            raise ValueError("Block is not array-like")

        return [cast(AstArrayValue, statement) for statement in self.statements]


@dataclass(frozen=True, slots=True)
class AstSourceFile:
    statements: tuple[AstStatement, ...]


type AstValue = AstScalar | AstBlock | AstTaggedBlockValue
type AstStatement = AstKeyValue | AstScalar | AstBlock | AstError
type AstArrayValue = AstScalar | AstBlock | AstTaggedBlockValue
type AstObjectValue = AstValue | None
type AstObject = dict[str, AstObjectValue]
type AstObjectMultimap = dict[str, list[AstObjectValue]]


__all__ = [
    "AstArrayValue",
    "AstBlock",
    "AstError",
    "AstKeyValue",
    "AstObject",
    "AstObjectMultimap",
    "AstObjectValue",
    "AstScalar",
    "AstSourceFile",
    "AstStatement",
    "AstTaggedBlockValue",
    "AstValue",
]
