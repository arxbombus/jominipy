"""Filesystem loaders for localisation files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jominipy.localisation.index import build_localisation_index
from jominipy.localisation.model import (
    LocalisationIndex,
    LocalisationParseResult,
)
from jominipy.localisation.parser import parse_localisation_text
from jominipy.localisation.profile import (
    PERMISSIVE_PROFILE,
    LocalisationProfile,
)


@dataclass(frozen=True, slots=True)
class LoadLocalisationResult:
    """Loaded localisation parse results and merged index."""

    parse_results: tuple[LocalisationParseResult, ...]
    index: LocalisationIndex


def load_localisation_from_project_root(
    *,
    project_root: str,
    profile: LocalisationProfile = PERMISSIVE_PROFILE,
) -> LoadLocalisationResult:
    """Load and parse localisation files under `<project>/localisation`."""
    root = Path(project_root)
    localisation_root = root / "localisation"
    if not localisation_root.exists():
        return LoadLocalisationResult(parse_results=(), index=build_localisation_index(()))

    paths = sorted(
        [
            *localisation_root.rglob("*.yml"),
            *localisation_root.rglob("*.yaml"),
        ]
    )

    parsed: list[LocalisationParseResult] = []
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
        parsed.append(
            parse_localisation_text(
                text,
                source_path=source_path,
                profile=profile,
                had_bom=had_bom,
            )
        )

    parsed_results = tuple(parsed)
    return LoadLocalisationResult(
        parse_results=parsed_results,
        index=build_localisation_index(parsed_results),
    )
