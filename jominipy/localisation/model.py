"""Models for Paradox localisation parsing and indexing."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from jominipy.diagnostics import Diagnostic
from jominipy.lexer.tokens import TriviaKind
from jominipy.text import TextRange


@dataclass(frozen=True, slots=True)
class LocalisationEntry:
    """One parsed localisation key/value entry."""

    source_path: str
    locale: str
    key: str
    version: int | None
    leading_trivia: str
    raw_value: str
    trailing_trivia: str
    value_text: str
    key_range: TextRange
    version_range: TextRange
    value_range: TextRange
    line: int


@dataclass(frozen=True, slots=True)
class LocalisationTrivia:
    """One preserved trivia token from localisation source."""

    kind: TriviaKind
    text: str
    range: TextRange


@dataclass(frozen=True, slots=True)
class LocalisationParseResult:
    """Lossless localisation parse result for a single file."""

    source_path: str
    source_text: str
    had_bom: bool
    header_key: str | None
    locale: str | None
    entries: tuple[LocalisationEntry, ...]
    trivia: tuple[LocalisationTrivia, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LocalisationIndex:
    """Project-level localisation key index across parsed files."""

    entries_by_key: Mapping[str, tuple[LocalisationEntry, ...]] = MappingProxyType({})
    entries_by_locale: Mapping[str, tuple[LocalisationEntry, ...]] = MappingProxyType({})

    @property
    def duplicate_entries_by_key(self) -> Mapping[str, tuple[LocalisationEntry, ...]]:
        duplicates = {
            key: entries
            for key, entries in self.entries_by_key.items()
            if len(entries) > 1
        }
        return MappingProxyType(duplicates)

    def contains_key(self, key: str) -> bool:
        return key in self.entries_by_key

    def get(self, key: str) -> tuple[LocalisationEntry, ...]:
        return self.entries_by_key.get(key, ())
