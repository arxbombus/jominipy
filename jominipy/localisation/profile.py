"""Header language profile scaffolds for localisation parsing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalisationProfile:
    """Profile defining allowed localisation header keys for a game."""

    name: str
    allowed_header_keys: frozenset[str] | None = None

    def is_supported_header_key(self, header_key: str) -> bool:
        if self.allowed_header_keys is None:
            return True
        return header_key in self.allowed_header_keys


PERMISSIVE_PROFILE = LocalisationProfile(name="permissive", allowed_header_keys=None)

HOI4_PROFILE = LocalisationProfile(
    name="hoi4",
    allowed_header_keys=frozenset(
        {
            "l_english",
            "l_french",
            "l_german",
            "l_spanish",
            "l_simp_chinese",
            "l_russian",
            "l_polish",
            "l_braz_por",
            "l_default",
        }
    ),
)

CK3_PROFILE = LocalisationProfile(
    name="ck3",
    allowed_header_keys=frozenset(
        {
            "l_english",
            "l_french",
            "l_german",
            "l_spanish",
            "l_simp_chinese",
            "l_russian",
            "l_korean",
        }
    ),
)
