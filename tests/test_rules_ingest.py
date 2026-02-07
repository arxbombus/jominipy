from pathlib import Path

from jominipy.rules import load_rules_paths, parse_rules_text, to_file_ir
from jominipy.rules.normalize import normalize_ruleset
from tests._debug import debug_dump_rules_ir


def test_rules_parser_attaches_comment_options_and_docs() -> None:
    source = """### Example docs
## cardinality = 0..1
## required
technology = {
    ## scope = country
    alias[effect:add_stability] = variable_field
}
"""
    parsed = parse_rules_text(source, source_path="inline.cwt")
    file_ir = to_file_ir(parsed)

    top = file_ir.statements[0]
    assert top.key == "technology"
    assert top.metadata.documentation == ("Example docs",)
    assert len(top.metadata.options) == 2
    assert top.metadata.options[0].key == "cardinality"
    assert top.metadata.options[0].value == "0..1"
    assert top.metadata.options[1].key == "required"
    assert top.metadata.options[1].value is None

    nested = top.value.block[0]
    assert nested.key == "alias[effect:add_stability]"
    assert len(nested.metadata.options) == 1
    assert nested.metadata.options[0].key == "scope"
    assert nested.metadata.options[0].value == "country"


def test_rules_loader_ingests_hoi4_samples_and_indexes_categories() -> None:
    root = Path(__file__).resolve().parents[1]
    sample_paths = [
        root / "references/hoi4-rules/Config/effects.cwt",
        root / "references/hoi4-rules/Config/triggers.cwt",
        root / "references/hoi4-rules/Config/modifiers.cwt",
        root / "references/hoi4-rules/Config/links.cwt",
        root / "references/hoi4-rules/Config/scopes.cwt",
        root / "references/hoi4-rules/Config/common/technologies.cwt",
    ]
    loaded = load_rules_paths(sample_paths)
    debug_dump_rules_ir("test_rules_loader_ingests_hoi4_samples_and_indexes_categories", loaded.ruleset)

    assert len(loaded.parse_results) == len(sample_paths)
    assert len(loaded.file_irs) == len(sample_paths)
    assert "alias" in loaded.ruleset.by_category
    assert "type" in loaded.ruleset.by_category
    assert "enum" in loaded.ruleset.by_category
    assert "rule" in loaded.ruleset.by_category

    aliases = loaded.ruleset.by_category["alias"]
    assert any(item.key.startswith("alias[effect:") for item in aliases)
    assert any(item.key.startswith("alias[trigger:") for item in aliases)

    types = loaded.ruleset.by_category["type"]
    assert any(item.key == "type[technology]" for item in types)


def test_rules_normalization_parses_typed_metadata_options() -> None:
    source = """### Rule docs
## cardinality = ~1..inf
## scope = { country state }
## push_scope = country
## replace_scope = { this = planet root = country }
## severity = warning
## required
allow = {
    value = int
}
"""
    parsed = parse_rules_text(source, source_path="inline-options.cwt")
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    debug_dump_rules_ir("test_rules_normalization_parses_typed_metadata_options", ruleset)

    allow_entries = [item for item in ruleset.indexed if item.key == "allow"]
    assert len(allow_entries) == 1
    metadata = allow_entries[0].statement.metadata
    assert metadata.documentation == ("Rule docs",)
    assert metadata.cardinality is not None
    assert metadata.cardinality.soft_minimum is True
    assert metadata.cardinality.minimum == 1
    assert metadata.cardinality.maximum is None
    assert metadata.cardinality.maximum_unbounded is True
    assert metadata.scope == ("country", "state")
    assert metadata.push_scope == ("country",)
    assert metadata.replace_scope is not None
    assert tuple((entry.source, entry.target) for entry in metadata.replace_scope) == (
        ("this", "planet"),
        ("root", "country"),
    )
    assert metadata.severity == "warning"
    assert "required" in metadata.flags


def test_rules_indexing_disambiguates_repeated_keys_with_declaration_paths() -> None:
    source = """technology = {
    x = int
    x = float
    child = {
        x = bool
    }
}
"""
    parsed = parse_rules_text(source, source_path="inline-paths.cwt")
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    debug_dump_rules_ir("test_rules_indexing_disambiguates_repeated_keys_with_declaration_paths", ruleset)

    x_entries = [item for item in ruleset.indexed if item.key == "x"]
    assert len(x_entries) == 3
    paths = {entry.declaration_path for entry in x_entries}
    assert len(paths) == 3
    assert ("technology#0", "x#0") in paths
    assert ("technology#0", "x#1") in paths
    assert ("technology#0", "child#0", "x#0") in paths
