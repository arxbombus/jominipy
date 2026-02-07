from pathlib import Path

from jominipy.rules import load_rules_paths, parse_rules_text, to_file_ir
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
