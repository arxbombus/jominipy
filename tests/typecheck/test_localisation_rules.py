from pathlib import Path

from jominipy.localisation import (
    build_localisation_key_provider,
    parse_localisation_text,
)
from jominipy.pipeline import run_typecheck
from jominipy.rules import (
    LocalisationCommandDefinition,
    RuleFieldConstraint,
    RuleValueSpec,
    SubtypeMatcher,
    TypeLocalisationTemplate,
)
from jominipy.rules.semantics import RuleFieldScopeConstraint
from jominipy.typecheck.rules import (
    ErrorIfOnlyMatchRule,
    LocalisationCommandScopeRule,
    LocalisationKeyExistenceRule,
    TypeLocalisationRequirementRule,
)
from jominipy.typecheck.services import (
    TypecheckPolicy,
    build_typecheck_services_from_file_texts,
    build_typecheck_services_from_project_root,
)


def test_typecheck_localisation_command_scope_allows_matching_scope() -> None:
    source = 'technology={ desc = "[ROOT.GetWing]" }\n'
    custom_rule = LocalisationCommandScopeRule(
        field_constraints_by_object={
            "technology": {
                "desc": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="localisation", primitive="localisation", argument=None),
                    ),
                ),
            }
        },
        localisation_command_definitions_by_name={
            "GetWing": LocalisationCommandDefinition(name="GetWing", supported_scopes=("air",))
        },
        field_scope_constraints_by_object={"technology": {(): RuleFieldScopeConstraint(push_scope=("air",))}},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_localisation_command_scope_rejects_mismatched_scope() -> None:
    source = 'technology={ desc = "[ROOT.GetWing]" }\n'
    custom_rule = LocalisationCommandScopeRule(
        field_constraints_by_object={
            "technology": {
                "desc": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="localisation", primitive="localisation", argument=None),
                    ),
                ),
            }
        },
        localisation_command_definitions_by_name={
            "GetWing": LocalisationCommandDefinition(name="GetWing", supported_scopes=("air",))
        },
        field_scope_constraints_by_object={"technology": {(): RuleFieldScopeConstraint(push_scope=("country",))}},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_localisation_command_scope_applies_subtype_push_scope() -> None:
    source = """ship_size = {
    class = shipclass_starbase
    desc = "[ROOT.GetWing]"
}
"""
    custom_rule = LocalisationCommandScopeRule(
        field_constraints_by_object={
            "ship_size": {
                "desc": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="localisation", primitive="localisation", argument=None),
                    ),
                ),
            }
        },
        localisation_command_definitions_by_name={
            "GetWing": LocalisationCommandDefinition(name="GetWing", supported_scopes=("air",))
        },
        subtype_matchers_by_object={
            "ship_size": (
                SubtypeMatcher(
                    subtype_name="starbase",
                    expected_field_values=(("class", "shipclass_starbase"),),
                    push_scope=("air",),
                ),
            )
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_localisation_command_scope_unresolved_command_defer_policy() -> None:
    source = 'technology={ desc = "[ROOT.GetUnknown]" }\n'
    custom_rule = LocalisationCommandScopeRule(
        field_constraints_by_object={
            "technology": {
                "desc": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="localisation", primitive="localisation", argument=None),
                    ),
                ),
            }
        },
        localisation_command_definitions_by_name={},
        field_scope_constraints_by_object={"technology": {(): RuleFieldScopeConstraint(push_scope=("country",))}},
        policy=TypecheckPolicy(unresolved_reference="defer"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_localisation_key_exists_rule_reports_missing_key() -> None:
    source = "technology={ desc = missing_loc_key }\n"
    provider = build_localisation_key_provider(
        (
            parse_localisation_text('l_english:\nknown_loc_key:0 "Known"\n'),
            parse_localisation_text('l_german:\nknown_loc_key:0 "Bekannt"\n'),
        )
    )
    custom_rule = LocalisationKeyExistenceRule(
        field_constraints_by_object={
            "technology": {
                "desc": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="localisation", primitive="localisation", argument=None),
                    ),
                ),
            }
        },
        localisation_key_provider=provider,
        policy=TypecheckPolicy(localisation_coverage="any"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]
    assert "Unknown localisation key `missing_loc_key`" in typecheck_result.diagnostics[0].message


def test_typecheck_localisation_key_exists_rule_reports_missing_locale_coverage() -> None:
    source = "technology={ desc = known_loc_key }\n"
    provider = build_localisation_key_provider(
        (
            parse_localisation_text('l_english:\nknown_loc_key:0 "Known"\n'),
            parse_localisation_text("l_german:\n"),
        )
    )
    custom_rule = LocalisationKeyExistenceRule(
        field_constraints_by_object={
            "technology": {
                "desc": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="localisation", primitive="localisation", argument=None),
                    ),
                ),
            }
        },
        localisation_key_provider=provider,
        policy=TypecheckPolicy(localisation_coverage="all"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]
    assert "missing locales: german" in typecheck_result.diagnostics[0].message


def test_typecheck_error_if_only_match_emits_custom_diagnostic_when_value_matches() -> None:
    source = "technology={ target = var:foo }\n"
    custom_rule = ErrorIfOnlyMatchRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="primitive", raw="scalar", primitive="scalar"),),
                    error_if_only_match="custom-scope-match-error",
                    comparison=True,
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_RULE_CUSTOM_ERROR"]
    assert "custom-scope-match-error" in typecheck_result.diagnostics[0].message


def test_typecheck_error_if_only_match_skips_when_value_does_not_match() -> None:
    source = "technology={ target = var:foo }\n"
    custom_rule = ErrorIfOnlyMatchRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="primitive", raw="int", primitive="int"),),
                    error_if_only_match="custom-scope-match-error",
                    comparison=True,
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_type_localisation_requirement_rule_reports_missing_required_key() -> None:
    provider = build_localisation_key_provider(
        (
            parse_localisation_text("""l_english:
ship_alpha:0 "Ship Alpha"
"""),
            parse_localisation_text("""l_german:
ship_alpha:0 "Schiff Alpha"
"""),
        )
    )
    custom_rule = TypeLocalisationRequirementRule(
        type_memberships_by_key={"ship_size": frozenset({"ship_alpha"})},
        type_localisation_templates_by_type={
            "ship_size": (
                TypeLocalisationTemplate(template="$", required=False),
                TypeLocalisationTemplate(template="$_desc", required=True),
            )
        },
        localisation_key_provider=provider,
        policy=TypecheckPolicy(localisation_coverage="any"),
    )

    typecheck_result = run_typecheck("technology={ desc = missing_loc_key }\n", rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]
    assert "Missing required localisation key `ship_alpha_desc`" in typecheck_result.diagnostics[0].message


def test_typecheck_services_include_modifier_and_localisation_providers() -> None:
    services = build_typecheck_services_from_file_texts(file_texts_by_path={})

    assert "modifier" in services.alias_memberships_by_family
    assert "annex_cost_factor" in services.alias_memberships_by_family["modifier"]
    assert services.alias_definitions_by_family
    assert any(services.alias_definitions_by_family.values())
    assert services.alias_invocations_by_object
    assert services.single_alias_definitions_by_name
    assert services.single_alias_invocations_by_object
    assert "modifier" in services.type_memberships_by_key
    assert "annex_cost_factor" in services.type_memberships_by_key["modifier"]
    assert "GetName" in services.localisation_command_definitions_by_name
    assert services.localisation_command_definitions_by_name["GetName"].supported_scopes == ("any",)
    assert services.localisation_key_provider.is_empty


def test_typecheck_services_from_project_root_include_localisation_key_provider(tmp_path: Path) -> None:
    (tmp_path / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "common" / "test.txt").write_text("technology={}\n", encoding="utf-8")
    loc_file = tmp_path / "localisation" / "english" / "test_l_english.yml"
    loc_file.parent.mkdir(parents=True, exist_ok=True)
    loc_file.write_text('\ufeffl_english:\nmy_focus_key:0 "My Focus"\n', encoding="utf-8")

    services = build_typecheck_services_from_project_root(project_root=str(tmp_path))

    assert not services.localisation_key_provider.is_empty
    assert services.localisation_key_provider.has_key("my_focus_key")
