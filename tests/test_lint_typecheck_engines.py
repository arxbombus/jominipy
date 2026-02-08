from typing import cast

from jominipy.analysis import AnalysisFacts
from jominipy.diagnostics import Diagnostic
from jominipy.lint.rules import (
    LintConfidence,
    LintDomain,
    SemanticMissingRequiredFieldRule,
)
from jominipy.parser import parse_result
from jominipy.pipeline import run_lint, run_typecheck
from jominipy.rules import RuleFieldConstraint, RuleValueSpec
from jominipy.typecheck.assets import SetAssetRegistry
from jominipy.typecheck.rules import (
    FieldConstraintRule,
    FieldReferenceConstraintRule,
    TypecheckFacts,
    TypecheckRule,
    default_typecheck_rules,
)
from jominipy.typecheck.services import TypecheckPolicy, TypecheckServices


def test_parse_result_analysis_facts_are_cached_across_engines() -> None:
    parsed = parse_result("a=1\n")

    first = parsed.analysis_facts()
    lint_result = run_lint("ignored", parse=parsed)
    second = parsed.analysis_facts()

    assert lint_result.parse is parsed
    assert first is second
    assert lint_result.type_facts is not None


def test_typecheck_reports_inconsistent_top_level_shape() -> None:
    source = "value=1\nvalue={ a=1 }\n"

    result = run_typecheck(source)

    codes = [diagnostic.code for diagnostic in result.diagnostics]
    assert "TYPECHECK_INCONSISTENT_VALUE_SHAPE" in codes
    assert "value" in result.facts.inconsistent_top_level_shapes


def test_lint_runs_semantic_and_style_rules_deterministically() -> None:
    source = "technology={ cost=1 path=a }\nvalue=1\nvalue={ a=1 }\n"

    typecheck_result = run_typecheck(source)
    lint_result = run_lint(source, typecheck=typecheck_result, parse=typecheck_result.parse)

    codes = [diagnostic.code for diagnostic in lint_result.diagnostics]
    assert codes == [
        "LINT_STYLE_SINGLE_LINE_BLOCK",
        "LINT_SEMANTIC_INCONSISTENT_SHAPE",
        "LINT_STYLE_SINGLE_LINE_BLOCK",
    ]


def test_typecheck_rejects_non_correctness_rule_domain() -> None:
    class BadTypeRule:
        code = "TYPECHECK_BAD_DOMAIN"
        name = "badTypeDomain"
        domain = "semantic"
        confidence = "sound"

    try:
        run_typecheck(
            "a=1\n",
            rules=cast(tuple[TypecheckRule, ...], (BadTypeRule(),)),
        )
    except ValueError as exc:
        assert "invalid domain" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid typecheck rule domain")


def test_typecheck_rejects_non_sound_confidence() -> None:
    class BadTypeRule:
        code = "TYPECHECK_BAD_CONFIDENCE"
        name = "badTypeConfidence"
        domain = "correctness"
        confidence = "heuristic"

    try:
        run_typecheck(
            "a=1\n",
            rules=cast(tuple[TypecheckRule, ...], (BadTypeRule(),)),
        )
    except ValueError as exc:
        assert "invalid confidence" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid typecheck confidence")


class BadLintRule:
    code: str = "LINT_BAD_DOMAIN"
    name: str = "badLintDomain"
    category: str = "semantic"
    domain: LintDomain = "correctness"  # type: ignore
    confidence: LintConfidence = "policy"

    def run(self, facts: AnalysisFacts, type_facts: TypecheckFacts, text: str) -> list[Diagnostic]:
        return []


def test_lint_rejects_correctness_domain_rule() -> None:
    try:
        run_lint("a=1\n", rules=tuple([BadLintRule()]))
    except ValueError as exc:
        assert "invalid domain" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid lint rule domain")


def test_lint_cwtools_required_fields_rule_with_custom_schema() -> None:
    source = "technology={ cost=1 }\n"
    custom_rule = SemanticMissingRequiredFieldRule(
        required_fields_by_object={"technology": ("required_field",)},
    )

    lint_result = run_lint(source, rules=(custom_rule,))
    codes = [diagnostic.code for diagnostic in lint_result.diagnostics]

    assert codes == ["LINT_SEMANTIC_MISSING_REQUIRED_FIELD"]
    assert "required_field" in lint_result.diagnostics[0].message


def test_typecheck_cwtools_type_rule_with_custom_schema() -> None:
    source = "technology={ level = yes }\n"
    custom_rule = FieldConstraintRule(
        field_constraints_by_object={
            "technology": {
                "level": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="primitive", raw="int", primitive="int", argument=None),),
                )
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    codes = [diagnostic.code for diagnostic in typecheck_result.diagnostics]

    assert codes == ["TYPECHECK_INVALID_FIELD_TYPE"]
    assert "technology.level" in typecheck_result.diagnostics[0].message


def test_typecheck_primitive_ranges_with_custom_schema() -> None:
    source = "technology={ level = 12 ratio = 0.8 }\n"
    custom_rule = FieldConstraintRule(
        field_constraints_by_object={
            "technology": {
                "level": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="primitive", raw="int[0..10]", primitive="int", argument="0..10"),),
                ),
                "ratio": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(kind="primitive", raw="float[0.0..0.5]", primitive="float", argument="0.0..0.5"),
                    ),
                ),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    codes = [diagnostic.code for diagnostic in typecheck_result.diagnostics]
    assert codes == ["TYPECHECK_INVALID_FIELD_TYPE", "TYPECHECK_INVALID_FIELD_TYPE"]


def test_typecheck_filepath_and_icon_use_asset_registry() -> None:
    source = "technology={ texture = focus_icon badge = war_goal }\n"
    custom_rule = FieldConstraintRule(
        field_constraints_by_object={
            "technology": {
                "texture": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="primitive",
                            raw="filepath[gfx/interface/goals/,.dds]",
                            primitive="filepath",
                            argument="gfx/interface/goals/,.dds",
                        ),
                    ),
                ),
                "badge": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="primitive",
                            raw="icon[gfx/interface/goals]",
                            primitive="icon",
                            argument="gfx/interface/goals",
                        ),
                    ),
                ),
            }
        },
        asset_registry=SetAssetRegistry(
            known_paths=frozenset(
                {
                    "gfx/interface/goals/focus_icon.dds",
                }
            )
        ),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    codes = [diagnostic.code for diagnostic in typecheck_result.diagnostics]
    assert codes == ["TYPECHECK_INVALID_FIELD_TYPE"]
    assert "technology.badge" in typecheck_result.diagnostics[0].message


def test_typecheck_filepath_icon_defer_without_registry() -> None:
    source = "technology={ texture = focus_icon badge = war_goal }\n"
    custom_rule = FieldConstraintRule(
        field_constraints_by_object={
            "technology": {
                "texture": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="primitive",
                            raw="filepath[gfx/interface/goals/,.dds]",
                            primitive="filepath",
                            argument="gfx/interface/goals/,.dds",
                        ),
                    ),
                ),
                "badge": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="primitive",
                            raw="icon[gfx/interface/goals]",
                            primitive="icon",
                            argument="gfx/interface/goals",
                        ),
                    ),
                ),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_filepath_icon_unknown_policy_error_without_registry() -> None:
    source = "technology={ texture = focus_icon badge = war_goal }\n"
    custom_rule = FieldConstraintRule(
        field_constraints_by_object={
            "technology": {
                "texture": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="primitive",
                            raw="filepath[gfx/interface/goals/,.dds]",
                            primitive="filepath",
                            argument="gfx/interface/goals/,.dds",
                        ),
                    ),
                ),
                "badge": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="primitive",
                            raw="icon[gfx/interface/goals]",
                            primitive="icon",
                            argument="gfx/interface/goals",
                        ),
                    ),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_asset="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    codes = [diagnostic.code for diagnostic in typecheck_result.diagnostics]
    assert codes == ["TYPECHECK_INVALID_FIELD_TYPE", "TYPECHECK_INVALID_FIELD_TYPE"]


def test_typecheck_field_reference_rule_validates_enum_membership() -> None:
    source = "technology={ stance = defensive }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "stance": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="enum_ref", raw="enum[stance]", argument="stance"),),
                ),
            }
        },
        enum_values_by_key={"stance": frozenset({"offensive"})},
        known_type_keys=frozenset(),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == [
        "TYPECHECK_INVALID_FIELD_REFERENCE"
    ]


def test_typecheck_field_reference_rule_validates_type_membership() -> None:
    source = "technology={ icon = GFX_focus_test }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "icon": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="type_ref", raw="<spriteType>", argument="spriteType"),),
                ),
            }
        },
        known_type_keys=frozenset({"spriteType"}),
        type_memberships_by_key={"spriteType": frozenset({"GFX_focus_other"})},
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == [
        "TYPECHECK_INVALID_FIELD_REFERENCE"
    ]


def test_typecheck_field_reference_rule_unresolved_policy_controls_outcome() -> None:
    source = "technology={ icon = GFX_focus_test }\n"
    custom_rule_defer = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "icon": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="type_ref", raw="<spriteType>", argument="spriteType"),),
                ),
            }
        },
        known_type_keys=frozenset({"spriteType"}),
        policy=TypecheckPolicy(unresolved_reference="defer"),
    )
    custom_rule_error = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "icon": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="type_ref", raw="<spriteType>", argument="spriteType"),),
                ),
            }
        },
        known_type_keys=frozenset({"spriteType"}),
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    defer_result = run_typecheck(source, rules=(custom_rule_defer,))
    error_result = run_typecheck(source, rules=(custom_rule_error,))

    assert defer_result.diagnostics == []
    assert [diagnostic.code for diagnostic in error_result.diagnostics] == [
        "TYPECHECK_INVALID_FIELD_REFERENCE"
    ]


def test_default_typecheck_rules_accept_injected_services_policy() -> None:
    services = TypecheckServices(policy=TypecheckPolicy(unresolved_asset="error"))

    rules = default_typecheck_rules(services=services)
    field_rules = [rule for rule in rules if isinstance(rule, FieldConstraintRule)]

    assert len(field_rules) == 1
    assert field_rules[0].policy.unresolved_asset == "error"


def test_analysis_facts_include_nested_object_fields_with_occurrence_tracking() -> None:
    parsed = parse_result("technology={ level=1 level=2 cost=3 }\ntechnology={ level=4 }\n")
    facts = parsed.analysis_facts()

    assert "technology" in facts.object_fields
    field_facts = facts.object_fields["technology"]
    assert [(fact.path, fact.object_occurrence, fact.field_occurrence) for fact in field_facts] == [
        (("technology", "level"), 0, 0),
        (("technology", "level"), 0, 1),
        (("technology", "cost"), 0, 0),
        (("technology", "level"), 1, 0),
    ]

    by_field = facts.object_field_map["technology"]
    assert len(by_field["level"]) == 3
    assert len(by_field["cost"]) == 1
    assert len(facts.all_field_facts) == 4


def test_analysis_facts_skip_non_object_like_blocks_for_nested_field_index() -> None:
    parsed = parse_result("technology={ a=1 2 }\n")
    facts = parsed.analysis_facts()

    assert "technology" not in facts.object_fields
    assert "technology" not in facts.object_field_map
    assert facts.all_field_facts == ()
