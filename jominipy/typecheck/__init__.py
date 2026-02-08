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
    "run_typecheck",
]
