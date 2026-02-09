"""Index builders for localisation parse results."""

from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType
from typing import Iterable

from jominipy.localisation.model import (
    LocalisationEntry,
    LocalisationIndex,
    LocalisationParseResult,
)


def build_localisation_index(results: Iterable[LocalisationParseResult]) -> LocalisationIndex:
    """Build a project-wide localisation index from parse results."""
    entries_by_key: dict[str, list[LocalisationEntry]] = defaultdict(list)
    entries_by_locale: dict[str, list[LocalisationEntry]] = defaultdict(list)

    for result in results:
        for entry in result.entries:
            entries_by_key[entry.key].append(entry)
            entries_by_locale[entry.locale].append(entry)

    frozen_by_key = MappingProxyType({key: tuple(entries) for key, entries in entries_by_key.items()})
    frozen_by_locale = MappingProxyType({key: tuple(entries) for key, entries in entries_by_locale.items()})
    return LocalisationIndex(entries_by_key=frozen_by_key, entries_by_locale=frozen_by_locale)
