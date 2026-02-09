"""Compact localisation key provider for rules/typecheck workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from jominipy.localisation.model import (
    LocalisationEntry,
    LocalisationParseResult,
)
from jominipy.localisation.parser import parse_localisation_text
from jominipy.localisation.profile import (
    HOI4_PROFILE,
    LocalisationProfile,
)


@dataclass(frozen=True, slots=True)
class LocalisationKeyProvider:
    """Compact key -> locale coverage index using locale bitmasks."""

    locale_index_by_name: Mapping[str, int] = MappingProxyType({})
    key_mask_by_name: Mapping[str, int] = MappingProxyType({})

    @property
    def is_empty(self) -> bool:
        return not self.key_mask_by_name

    @property
    def locales(self) -> tuple[str, ...]:
        return tuple(sorted(self.locale_index_by_name, key=self.locale_index_by_name.__getitem__))

    def has_key(self, key: str) -> bool:
        return key in self.key_mask_by_name

    def has_key_for_locale(self, key: str, locale: str) -> bool:
        bit = self._locale_bit(locale)
        if bit is None:
            return False
        return bool(self.key_mask_by_name.get(key, 0) & bit)

    def locales_for_key(self, key: str) -> tuple[str, ...]:
        mask = self.key_mask_by_name.get(key)
        if mask is None:
            return ()
        return tuple(locale for locale in self.locales if self.has_key_for_locale(key, locale))

    def missing_locales_for_key(
        self,
        key: str,
        *,
        required_locales: Iterable[str] | None = None,
    ) -> tuple[str, ...]:
        if required_locales is None:
            required = self.locales
        else:
            required = tuple(locale for locale in required_locales if locale in self.locale_index_by_name)
        if not required:
            return ()
        mask = self.key_mask_by_name.get(key, 0)
        missing: list[str] = []
        for locale in required:
            bit = self._locale_bit(locale)
            if bit is None or not (mask & bit):
                missing.append(locale)
        return tuple(missing)

    def _locale_bit(self, locale: str) -> int | None:
        index = self.locale_index_by_name.get(locale)
        if index is None:
            return None
        return 1 << index


def build_localisation_key_provider(
    results: Iterable[LocalisationParseResult],
) -> LocalisationKeyProvider:
    """Build a compact key provider from parsed localisation results."""
    locale_names: set[str] = set()
    key_locales: dict[str, set[str]] = {}

    for result in results:
        if result.locale:
            locale_names.add(result.locale)
        for entry in result.entries:
            _add_entry(entry, locale_names, key_locales)

    return _freeze_key_provider(locale_names, key_locales)


def load_localisation_key_provider_from_project_root(
    *,
    project_root: str,
    profile: LocalisationProfile = HOI4_PROFILE,
) -> LocalisationKeyProvider:
    """Load localisation files and build a compact key provider."""
    root = Path(project_root)
    localisation_root = root / "localisation"
    if not localisation_root.exists():
        return LocalisationKeyProvider()

    paths = sorted(
        [
            *localisation_root.rglob("*.yml"),
            *localisation_root.rglob("*.yaml"),
        ]
    )

    locale_names: set[str] = set()
    key_locales: dict[str, set[str]] = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            decoded = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        had_bom = decoded.startswith("\ufeff")
        text = decoded[1:] if had_bom else decoded
        source_path = str(path.relative_to(root)).replace("\\", "/")
        parsed = parse_localisation_text(
            text,
            source_path=source_path,
            profile=profile,
            had_bom=had_bom,
        )
        if parsed.locale:
            locale_names.add(parsed.locale)
        for entry in parsed.entries:
            _add_entry(entry, locale_names, key_locales)

    return _freeze_key_provider(locale_names, key_locales)


def _add_entry(
    entry: LocalisationEntry,
    locale_names: set[str],
    key_locales: dict[str, set[str]],
) -> None:
    if not entry.key or not entry.locale:
        return
    locale_names.add(entry.locale)
    key_locales.setdefault(entry.key, set()).add(entry.locale)


def _freeze_key_provider(
    locale_names: set[str],
    key_locales: dict[str, set[str]],
) -> LocalisationKeyProvider:
    locale_index = {locale: index for index, locale in enumerate(sorted(locale_names))}
    key_mask_by_name: dict[str, int] = {}
    for key, locales in key_locales.items():
        mask = 0
        for locale in locales:
            index = locale_index.get(locale)
            if index is None:
                continue
            mask |= 1 << index
        if mask:
            key_mask_by_name[key] = mask
    return LocalisationKeyProvider(
        locale_index_by_name=MappingProxyType(locale_index),
        key_mask_by_name=MappingProxyType(key_mask_by_name),
    )
