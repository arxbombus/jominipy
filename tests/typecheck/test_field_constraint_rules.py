from jominipy.pipeline import run_typecheck
from jominipy.rules import (
    RuleFieldConstraint,
    RuleValueSpec,
)
from jominipy.typecheck.assets import SetAssetRegistry
from jominipy.typecheck.rules import (
    FieldConstraintRule,
)
from jominipy.typecheck.services import (
    TypecheckPolicy,
)


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
