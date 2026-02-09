"""Paradox localisation parsing and indexing APIs."""

from jominipy.localisation.index import build_localisation_index
from jominipy.localisation.keys import (
    LocalisationKeyProvider,
    build_localisation_key_provider,
    load_localisation_key_provider_from_project_root,
)
from jominipy.localisation.load import (
    LoadLocalisationResult,
    load_localisation_from_project_root,
)
from jominipy.localisation.model import (
    LocalisationEntry,
    LocalisationIndex,
    LocalisationParseResult,
    LocalisationTrivia,
)
from jominipy.localisation.parser import (
    parse_localisation_file,
    parse_localisation_text,
)
from jominipy.localisation.profile import (
    CK3_PROFILE,
    HOI4_PROFILE,
    PERMISSIVE_PROFILE,
    LocalisationProfile,
)

__all__ = [
    "CK3_PROFILE",
    "HOI4_PROFILE",
    "PERMISSIVE_PROFILE",
    "LoadLocalisationResult",
    "LocalisationEntry",
    "LocalisationIndex",
    "LocalisationKeyProvider",
    "LocalisationParseResult",
    "LocalisationProfile",
    "LocalisationTrivia",
    "build_localisation_index",
    "build_localisation_key_provider",
    "load_localisation_from_project_root",
    "load_localisation_key_provider_from_project_root",
    "parse_localisation_file",
    "parse_localisation_text",
]
