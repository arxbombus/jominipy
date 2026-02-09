from pathlib import Path

from jominipy.localisation import (
    CK3_PROFILE,
    HOI4_PROFILE,
    parse_localisation_file,
    parse_localisation_text,
)


def test_accepts_versioned_entry() -> None:
    source = """l_english:
my_loc:0 "hello world"
"""

    parsed = parse_localisation_text(source)

    assert parsed.diagnostics == ()
    assert len(parsed.entries) == 1
    assert parsed.entries[0].key == "my_loc"
    assert parsed.entries[0].version == 0
    assert parsed.entries[0].value_text == "hello world"


def test_accepts_dotted_key_without_version_number() -> None:
    source = """l_english:
my_event.t.1 "my event title without version number"
"""

    parsed = parse_localisation_text(source)

    assert parsed.diagnostics == ()
    assert len(parsed.entries) == 1
    assert parsed.entries[0].key == "my_event.t.1"
    assert parsed.entries[0].version is None


def test_accepts_colon_entry_without_version_number() -> None:
    source = """l_english:
my_loc: 'This is my loc'
"""

    parsed = parse_localisation_text(source)

    assert parsed.diagnostics == ()
    assert len(parsed.entries) == 1
    assert parsed.entries[0].key == "my_loc"
    assert parsed.entries[0].version is None
    assert parsed.entries[0].value_text == "This is my loc"


def test_reports_duplicate_key_diagnostic() -> None:
    source = """l_english:
my_event.t.1:0 "A"
my_event.t.1:0 "B"
"""

    parsed = parse_localisation_text(source)

    assert len(parsed.entries) == 2
    assert [d.code for d in parsed.diagnostics] == ["LOCALISATION_DUPLICATE_KEY"]


def test_reports_column_mismatch_for_children() -> None:
    source = """l_english:
  # comments
  my_loc: 'This is my loc' # comment
not_on_the_same_col_loc:0 "oh no"
"""

    parsed = parse_localisation_text(source)

    assert len(parsed.entries) == 1
    assert parsed.entries[0].key == "my_loc"
    assert [d.code for d in parsed.diagnostics] == ["LOCALISATION_INVALID_COLUMN"]


def test_accepts_loose_double_quote_value() -> None:
    source = """l_english:
my_loc:0 "Hello "World"
"""

    parsed = parse_localisation_text(source)

    assert parsed.diagnostics == ()
    assert len(parsed.entries) == 1
    assert parsed.entries[0].value_text == 'Hello "World'


def test_rejects_single_quoted_value_with_double_quote_terminator() -> None:
    source = """l_english:
my_loc:0 'Hello "World"
"""

    parsed = parse_localisation_text(source)

    assert len(parsed.entries) == 0
    assert [d.code for d in parsed.diagnostics] == ["LEXER_UNTERMINATED_STRING"]


def test_accepts_single_quote_with_inner_double_quote() -> None:
    source = """l_english:
my_loc:0 'Hello "World'
"""

    parsed = parse_localisation_text(source)

    assert parsed.diagnostics == ()
    assert len(parsed.entries) == 1
    assert parsed.entries[0].value_text == 'Hello "World'


def test_rejects_space_before_version() -> None:
    source = """l_english:
my_loc: 0 'Hello "World"'
"""

    parsed = parse_localisation_text(source)

    assert len(parsed.entries) == 0
    assert [d.code for d in parsed.diagnostics] == ["LOCALISATION_INVALID_ENTRY"]


def test_rejects_multiline_string_value() -> None:
    source = """l_english:
my_loc:0 "Hello
# world"
"""

    parsed = parse_localisation_text(source)

    assert len(parsed.entries) == 0
    assert [d.code for d in parsed.diagnostics] == ["LEXER_UNTERMINATED_STRING"]


def test_localisation_parser_requires_header() -> None:
    source = 'my_event.t.1:0 "value"\n'

    parsed = parse_localisation_text(source)

    assert len(parsed.entries) == 0
    assert parsed.diagnostics
    assert parsed.diagnostics[0].code == "LOCALISATION_MISSING_HEADER"


def test_localisation_parser_validates_header_by_profile() -> None:
    source = """l_default:
my_event.t.1:0 "value"
"""

    hoi4 = parse_localisation_text(source, profile=HOI4_PROFILE)
    ck3 = parse_localisation_text(source, profile=CK3_PROFILE)

    assert hoi4.diagnostics == ()
    assert [d.code for d in ck3.diagnostics] == ["LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE"]


def test_parse_localisation_file_wrapper(tmp_path: Path) -> None:
    path: Path = tmp_path / "events_l_english.yml"
    path.write_text(
        'l_english:\nmy_event.t.1:0 "Title"\n',
        encoding="utf-8-sig",
    )

    parsed = parse_localisation_file(path, profile=HOI4_PROFILE)

    assert parsed.source_path.endswith("events_l_english.yml")
    assert parsed.had_bom is True
    assert parsed.locale == "english"
    assert len(parsed.entries) == 1
    assert parsed.entries[0].key == "my_event.t.1"


def test_parse_test_loc_file() -> None:
    path = "/Users/harrisonchan/Programming/paradox/jominipy/tests/test_loc_l_english.yml"
    parsed = parse_localisation_file(path, profile=HOI4_PROFILE)
    assert parsed.had_bom is True
    assert parsed.locale == "english"
    keys = {entry.key for entry in parsed.entries}
    assert "naval_bomber_1" in keys
    assert "SouthSudan.6.t" in keys
    assert "SouthSudan.6.d" in keys
    assert "SouthSudan.6.a" in keys
    assert "SouthSudan.7.t" in keys
    trivia_text = "".join(piece.text for piece in parsed.trivia)
    assert "#this prevents vanilla air equipment loc from being loaded" in trivia_text
    assert "# This is also a comment" in trivia_text
    print(parsed)
