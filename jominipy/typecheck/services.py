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


def build_typecheck_services_from_file_texts(
    *,
    file_texts_by_path: Mapping[str, str],
    asset_registry: AssetRegistry | None = None,
    policy: TypecheckPolicy | None = None,
) -> TypecheckServices:
    """Build generic type-membership services from schema + project file texts."""
    from jominipy.rules import (
        build_type_memberships_from_file_texts,
        extract_type_definitions,
        load_hoi4_schema_graph,
    )

    schema = load_hoi4_schema_graph()
    type_definitions = extract_type_definitions(schema)
    memberships = build_type_memberships_from_file_texts(
        file_texts_by_path=file_texts_by_path,
        type_definitions_by_key=type_definitions,
    )
    return TypecheckServices(
        asset_registry=asset_registry or NullAssetRegistry(),
        policy=policy or TypecheckPolicy(),
        type_memberships_by_key=MappingProxyType(memberships),
    )


def build_typecheck_services_from_project_root(
    *,
    project_root: str,
    asset_registry: AssetRegistry | None = None,
    policy: TypecheckPolicy | None = None,
) -> TypecheckServices:
    """Build generic type-membership services from project-root script files."""
    from jominipy.rules import collect_file_texts_under_root

    file_texts = collect_file_texts_under_root(project_root)
    return build_typecheck_services_from_file_texts(
        file_texts_by_path=file_texts,
        asset_registry=asset_registry,
        policy=policy,
    )
