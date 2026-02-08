"""Type-check pipeline for Jomini game-script sources."""

from jominipy.typecheck.assets import (
    AssetLookup,
    AssetLookupStatus,
    AssetRegistry,
    NullAssetRegistry,
    SetAssetRegistry,
)
from jominipy.typecheck.runner import run_typecheck
from jominipy.typecheck.services import (
    TypecheckPolicy,
    TypecheckServices,
    UnresolvedPolicy,
    build_typecheck_services_from_file_texts,
)

__all__ = [
    "AssetLookup",
    "AssetLookupStatus",
    "AssetRegistry",
    "NullAssetRegistry",
    "SetAssetRegistry",
    "TypecheckPolicy",
    "TypecheckServices",
    "UnresolvedPolicy",
    "build_typecheck_services_from_file_texts",
    "run_typecheck",
]
