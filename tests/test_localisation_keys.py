from pathlib import Path

from jominipy.localisation import (
    HOI4_PROFILE,
    build_localisation_key_provider,
    load_localisation_key_provider_from_project_root,
    parse_localisation_text,
)


def test_build_localisation_key_provider_tracks_locale_coverage() -> None:
    english = parse_localisation_text(
        'l_english:\nshared_key:0 "A"\nenglish_only:0 "B"\n',
        source_path="localisation/english/test_l_english.yml",
        profile=HOI4_PROFILE,
    )
    german = parse_localisation_text(
        'l_german:\nshared_key:0 "A"\n',
        source_path="localisation/german/test_l_german.yml",
        profile=HOI4_PROFILE,
    )

    provider = build_localisation_key_provider((english, german))

    assert provider.has_key("shared_key")
    assert provider.has_key_for_locale("shared_key", "english")
    assert provider.has_key_for_locale("shared_key", "german")
    assert provider.has_key("english_only")
    assert provider.has_key_for_locale("english_only", "english")
    assert not provider.has_key_for_locale("english_only", "german")
    assert provider.missing_locales_for_key("english_only") == ("german",)


def test_load_localisation_key_provider_from_project_root(tmp_path: Path) -> None:
    root = tmp_path
    loc_english = root / "localisation" / "english" / "test_l_english.yml"
    loc_german = root / "localisation" / "german" / "test_l_german.yml"
    loc_english.parent.mkdir(parents=True, exist_ok=True)
    loc_german.parent.mkdir(parents=True, exist_ok=True)
    loc_english.write_text('\ufeffl_english:\nfocus_key:0 "Focus"\n', encoding="utf-8")
    loc_german.write_text('\ufeffl_german:\nfocus_key:0 "Fokus"\n', encoding="utf-8")

    provider = load_localisation_key_provider_from_project_root(
        project_root=str(root),
        profile=HOI4_PROFILE,
    )

    assert provider.has_key("focus_key")
    assert provider.locales_for_key("focus_key") == ("english", "german")
