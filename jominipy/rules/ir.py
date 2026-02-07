"""Normalized intermediate representation for CWTools-like rules files."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from jominipy.text import TextRange

if TYPE_CHECKING:
    from jominipy.diagnostics import Diagnostic

type RuleExpressionKind = Literal["missing", "scalar", "block", "tagged_block", "error"]
type RuleStatementKind = Literal["key_value", "value", "error"]


@dataclass(frozen=True, slots=True)
class RuleOption:
    """Structured option parsed from a `##` comment."""

    key: str
    value: str | None
    raw: str


@dataclass(frozen=True, slots=True)
class RuleCardinality:
    """Typed cardinality parsed from `## cardinality = ...`."""

    minimum: int | None
    maximum: int | None
    soft_minimum: bool
    minimum_unbounded: bool = False
    maximum_unbounded: bool = False


@dataclass(frozen=True, slots=True)
class RuleScopeReplacement:
    """Typed item parsed from `## replace_scope = { this = planet ... }`."""

    source: str
    target: str


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    """Documentation and options attached to one declaration."""

    documentation: tuple[str, ...] = ()
    options: tuple[RuleOption, ...] = ()
    cardinality: RuleCardinality | None = None
    scope: tuple[str, ...] | None = None
    push_scope: tuple[str, ...] | None = None
    replace_scope: tuple[RuleScopeReplacement, ...] | None = None
    severity: str | None = None
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class RuleExpression:
    """Right-hand expression for rule statements."""

    kind: RuleExpressionKind
    text: str | None = None
    block: tuple[RuleStatement, ...] = ()
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class RuleStatement:
    """One normalized statement from a rules file."""

    source_path: str
    source_range: TextRange
    kind: RuleStatementKind
    key: str | None
    operator: str | None
    value: RuleExpression
    metadata: RuleMetadata = field(default_factory=RuleMetadata)

    def __repr__(self) -> str:
        key_str = f"key={self.key!r}" if self.key is not None else "value"
        metadata_str = f" metadata={self.metadata!r}" if self.metadata.documentation or self.metadata.options else ""
        return f"RuleStatement({key_str} op={self.operator!r} value={self.value!r}{metadata_str})"


@dataclass(frozen=True, slots=True)
class RuleFileIR:
    """IR for one parsed rules file."""

    path: str
    statements: tuple[RuleStatement, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class IndexedRuleStatement:
    """Category-indexed declaration reference."""

    category: str
    source_path: str
    source_range: TextRange
    key: str
    family: str | None
    argument: str | None
    declaration_path: tuple[str, ...]
    statement: RuleStatement


@dataclass(frozen=True, slots=True)
class RuleSetIR:
    """Merged rules IR across multiple files."""

    files: tuple[RuleFileIR, ...]
    indexed: tuple[IndexedRuleStatement, ...]
    by_category: dict[str, tuple[IndexedRuleStatement, ...]]
