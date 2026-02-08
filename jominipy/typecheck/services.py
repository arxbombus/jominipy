"""Service and policy wiring for type-check rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

from jominipy.typecheck.assets import AssetRegistry, NullAssetRegistry

type UnresolvedPolicy = Literal["defer", "error"]


@dataclass(frozen=True, slots=True)
class TypecheckPolicy:
    """Policy toggles for unresolved checks in type-check rules."""

    unresolved_asset: UnresolvedPolicy = "defer"
    unresolved_reference: UnresolvedPolicy = "defer"


@dataclass(frozen=True, slots=True)
class TypecheckServices:
    """Shared resolver/services injected into type-check execution."""

    asset_registry: AssetRegistry = field(default_factory=NullAssetRegistry)
    policy: TypecheckPolicy = field(default_factory=TypecheckPolicy)
    type_memberships_by_key: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    value_memberships_by_key: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    known_scopes: frozenset[str] = frozenset()
