from pathlib import Path

from jominipy.rules import (
    RuleFieldConstraint,
    RuleSchemaGraph,
    RuleValueSpec,
    build_alias_members_by_family,
    build_expanded_field_constraints,
    build_field_constraints_by_object,
    build_required_fields_by_object,
    build_schema_graph,
    build_subtype_field_constraints_by_object,
    build_subtype_matchers_by_object,
    load_hoi4_enum_values,
    load_hoi4_known_scopes,
    load_hoi4_required_fields,
    load_hoi4_schema_graph,
    load_hoi4_type_keys,
    load_rules_paths,
    parse_rules_text,
    to_file_ir,
)
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


def test_required_fields_extraction_from_cardinality() -> None:
    source = """technology = {
    ## cardinality = 1..1
    required_field = int
    ## cardinality = 0..1
    optional_field = int
    pattern[field] = int
}
"""
    parsed = parse_rules_text(source, source_path="inline-required.cwt")
    file_ir = to_file_ir(parsed)
    normalized = normalize_ruleset((file_ir,))
    required = build_required_fields_by_object(normalized.files[0].statements, include_implicit_required=False)

    assert required == {"technology": ("required_field",)}


def test_field_constraint_extraction_from_scalar_specs() -> None:
    source = """technology = {
    ## cardinality = 1..1
    required_field = int
    optional_float = float[0..1]
    scoped = scope[country]
    complex = { child = int }
}
"""
    parsed = parse_rules_text(source, source_path="inline-typed.cwt")
    file_ir = to_file_ir(parsed)
    normalized = normalize_ruleset((file_ir,))
    constraints = build_field_constraints_by_object(
        normalized.files[0].statements,
        include_implicit_required=False,
    )

    expected = {
        "technology": {
            "required_field": RuleFieldConstraint(
                required=True,
                value_specs=(RuleValueSpec(kind="primitive", raw="int", primitive="int", argument=None),),
            ),
            "optional_float": RuleFieldConstraint(
                required=False,
                value_specs=(RuleValueSpec(kind="primitive", raw="float[0..1]", primitive="float", argument="0..1"),),
            ),
            "scoped": RuleFieldConstraint(
                required=False,
                value_specs=(
                    RuleValueSpec(kind="scope_ref", raw="scope[country]", primitive=None, argument="country"),
                ),
            ),
            "complex": RuleFieldConstraint(
                required=False,
                value_specs=(RuleValueSpec(kind="block", raw="{...}", primitive=None, argument=None),),
            ),
        }
    }
    assert constraints == expected


def test_hoi4_schema_graph_loads_cross_file_categories() -> None:
    schema = load_hoi4_schema_graph()

    assert isinstance(schema, RuleSchemaGraph)
    assert schema.source_root.endswith("references/hoi4-rules/Config")
    assert "type" in schema.by_category
    assert "alias" in schema.by_category
    assert "section" in schema.by_category
    assert "technology" in schema.types_by_key
    assert any(name.startswith("effect:") for name in schema.aliases_by_key)


def test_hoi4_required_fields_are_derived_from_cross_file_schema() -> None:
    required = load_hoi4_required_fields(include_implicit_required=False)

    # `style` lives in `common/national_focus.cwt`, not technologies.cwt.
    assert "style" in required
    assert "name" in required["style"]


def test_hoi4_enum_values_and_type_keys_load_from_schema_graph() -> None:
    enum_values = load_hoi4_enum_values()
    type_keys = load_hoi4_type_keys()

    assert "add_factor" in enum_values
    assert "add" in enum_values["add_factor"]
    assert "spriteType" in type_keys


def test_hoi4_known_scopes_load_from_schema_graph() -> None:
    scopes = load_hoi4_known_scopes()

    assert "country" in scopes
    assert "state" in scopes


def test_single_alias_references_are_expanded_in_field_constraints() -> None:
    source = """single_alias[test_clause] = { value = int }
technology = {
    clause = single_alias_right[test_clause]
}
"""
    parsed = parse_rules_text(source, source_path="inline-single-alias.cwt")
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    schema = build_schema_graph(source_root="inline", ruleset=ruleset)

    expanded = build_expanded_field_constraints(schema).by_object
    clause = expanded["technology"]["clause"]
    assert clause.value_specs == (
        RuleValueSpec(kind="block", raw="{...}", primitive=None, argument=None),
    )


def test_alias_memberships_are_grouped_by_family() -> None:
    source = """alias[effect:add_stability] = int
alias[effect:add_war_support] = int
alias[trigger:has_government] = bool
"""
    parsed = parse_rules_text(source, source_path="inline-alias-members.cwt")
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    schema = build_schema_graph(source_root="inline", ruleset=ruleset)

    memberships = build_alias_members_by_family(schema)
    assert memberships["effect"] == frozenset({"add_stability", "add_war_support"})
    assert memberships["trigger"] == frozenset({"has_government"})


def test_subtype_matchers_are_extracted_from_type_definitions() -> None:
    source = """types = {
    type[ship_size] = {
        subtype[starbase] = { class = shipclass_starbase }
        subtype[ship] = { class = shipclass_military }
    }
}
"""
    parsed = parse_rules_text(source, source_path="inline-subtype-matchers.cwt")
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    schema = build_schema_graph(source_root="inline", ruleset=ruleset)

    matchers = build_subtype_matchers_by_object(schema)
    assert tuple(m.subtype_name for m in matchers["ship_size"]) == ("starbase", "ship")
    assert matchers["ship_size"][0].expected_field_values == (("class", "shipclass_starbase"),)
    assert matchers["ship_size"][1].expected_field_values == (("class", "shipclass_military"),)


def test_subtype_field_constraints_are_extracted_from_object_rules() -> None:
    source = """ship_size = {
    subtype[starbase] = {
        max_wings = int
    }
    subtype[ship] = {
        combat_disengage_chance = float
    }
}
"""
    parsed = parse_rules_text(source, source_path="inline-subtype-fields.cwt")
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    schema = build_schema_graph(source_root="inline", ruleset=ruleset)

    constraints = build_subtype_field_constraints_by_object(schema)
    assert constraints["ship_size"]["starbase"]["max_wings"] == RuleFieldConstraint(
        required=False,
        value_specs=(RuleValueSpec(kind="primitive", raw="int", primitive="int", argument=None),),
    )
    assert constraints["ship_size"]["ship"]["combat_disengage_chance"] == RuleFieldConstraint(
        required=False,
        value_specs=(RuleValueSpec(kind="primitive", raw="float", primitive="float", argument=None),),
    )
