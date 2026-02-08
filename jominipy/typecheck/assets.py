"""Asset registry contracts for type-check rules that resolve file-backed values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class AssetLookupStatus(StrEnum):
    """Asset lookup status for registry-backed checks."""

    FOUND = "found"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AssetLookup:
    """Result of a registry lookup for one logical asset path."""

    status: AssetLookupStatus
    normalized_path: str


class AssetRegistry(Protocol):
    """Abstract asset registry used by type-check rules."""

    def lookup(self, path: str) -> AssetLookup: ...


@dataclass(frozen=True, slots=True)
class NullAssetRegistry:
    """Default registry that reports unknown lookups (no project registry configured)."""

    def lookup(self, path: str) -> AssetLookup:
        return AssetLookup(status=AssetLookupStatus.UNKNOWN, normalized_path=_normalize_path(path))


@dataclass(frozen=True, slots=True)
class SetAssetRegistry:
    """Simple in-memory registry for tests and local wiring."""

    known_paths: frozenset[str]

    def lookup(self, path: str) -> AssetLookup:
        normalized = _normalize_path(path)
        if normalized in self.known_paths:
            return AssetLookup(status=AssetLookupStatus.FOUND, normalized_path=normalized)
        return AssetLookup(status=AssetLookupStatus.MISSING, normalized_path=normalized)


def _normalize_path(path: str) -> str:
    stripped = path.strip()
    if not stripped:
        return ""
    return stripped.replace("\\", "/")
