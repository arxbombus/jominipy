"""AST data model for Jomini source."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class AstSourceFile:
    statements: tuple[AstStatement, ...]


type AstValue = AstScalar | AstBlock | AstTaggedBlockValue
type AstStatement = AstKeyValue | AstScalar | AstBlock | AstError


__all__ = [
    "AstBlock",
    "AstError",
    "AstKeyValue",
    "AstScalar",
    "AstSourceFile",
    "AstStatement",
    "AstTaggedBlockValue",
    "AstValue",
]
