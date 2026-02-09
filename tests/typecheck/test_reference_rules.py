from jominipy.pipeline import run_typecheck
from jominipy.rules import (
    LinkDefinition,
    RuleFieldConstraint,
    RuleValueSpec,
    SubtypeMatcher,
)
from jominipy.rules.semantics import RuleFieldScopeConstraint
from jominipy.typecheck.rules import (
    FieldConstraintRule,
    FieldReferenceConstraintRule,
)
from jominipy.typecheck.services import (
    TypecheckPolicy,
    TypecheckServices,
)


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
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


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
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


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
    assert [diagnostic.code for diagnostic in error_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_field_reference_rule_supports_prefixed_suffixed_type_refs() -> None:
    source = "technology={ modifier = pre_my_modifier_suf }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "modifier": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="type_ref",
                            raw="pre_<opinion_modifier>_suf",
                            argument="opinion_modifier",
                        ),
                    ),
                ),
            }
        },
        known_type_keys=frozenset({"opinion_modifier"}),
        type_memberships_by_key={"opinion_modifier": frozenset({"other_modifier"})},
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_field_reference_rule_validates_scope_ref() -> None:
    source = "technology={ who = state }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_field_reference_rule_validates_alias_match_left_membership() -> None:
    source = "technology={ effect_key = add_stability }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "effect_key": RuleFieldConstraint(
                    required=False,
                    value_specs=(
                        RuleValueSpec(
                            kind="alias_match_left_ref",
                            raw="alias_match_left[effect]",
                            argument="effect",
                        ),
                    ),
                ),
            }
        },
        alias_memberships_by_family={"effect": frozenset({"add_stability"})},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_field_constraint_rule_applies_subtype_gating_per_object_occurrence() -> None:
    source = (
        "ship_size={ class=shipclass_starbase max_wings=yes }\nship_size={ class=shipclass_military max_wings=yes }\n"
    )
    custom_rule = FieldConstraintRule(
        field_constraints_by_object={"ship_size": {}},
        subtype_matchers_by_object={
            "ship_size": (
                SubtypeMatcher(subtype_name="starbase", expected_field_values=(("class", "shipclass_starbase"),)),
                SubtypeMatcher(subtype_name="ship", expected_field_values=(("class", "shipclass_military"),)),
            )
        },
        subtype_field_constraints_by_object={
            "ship_size": {
                "starbase": {
                    "max_wings": RuleFieldConstraint(
                        required=False,
                        value_specs=(RuleValueSpec(kind="primitive", raw="int", primitive="int", argument=None),),
                    ),
                },
                "ship": {
                    "max_wings": RuleFieldConstraint(
                        required=False,
                        value_specs=(RuleValueSpec(kind="primitive", raw="bool", primitive="bool", argument=None),),
                    ),
                },
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_TYPE"]


def test_typecheck_field_reference_rule_applies_subtype_gating_per_object_occurrence() -> None:
    source = "ship_size={ class=shipclass_starbase stance=defensive }\nship_size={ class=shipclass_military stance=defensive }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={"ship_size": {}},
        subtype_matchers_by_object={
            "ship_size": (
                SubtypeMatcher(subtype_name="starbase", expected_field_values=(("class", "shipclass_starbase"),)),
                SubtypeMatcher(subtype_name="ship", expected_field_values=(("class", "shipclass_military"),)),
            )
        },
        subtype_field_constraints_by_object={
            "ship_size": {
                "starbase": {
                    "stance": RuleFieldConstraint(
                        required=False,
                        value_specs=(RuleValueSpec(kind="enum_ref", raw="enum[stance]", argument="stance"),),
                    ),
                },
                "ship": {
                    "stance": RuleFieldConstraint(
                        required=False,
                        value_specs=(RuleValueSpec(kind="enum_ref", raw="enum[stance]", argument="stance"),),
                    ),
                },
            }
        },
        enum_values_by_key={"stance": frozenset({"offensive"})},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == [
        "TYPECHECK_INVALID_FIELD_REFERENCE",
        "TYPECHECK_INVALID_FIELD_REFERENCE",
    ]


def test_typecheck_runner_binds_service_enum_memberships_for_enum_refs() -> None:
    source = "technology={ stance = offensive }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "stance": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="enum_ref", raw="enum[stance]", argument="stance"),),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(enum_memberships_by_key={"stance": frozenset({"offensive"})})

    typecheck_result = run_typecheck(source, rules=(custom_rule,), services=services)
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_link_prefix_output_scope_when_input_scope_matches() -> None:
    source = "technology={ target = var:foo }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("state",)),
            }
        },
        link_definitions_by_name={
            "var": LinkDefinition(
                name="var",
                output_scope="country",
                input_scopes=("state",),
                prefix="var:",
                from_data=True,
                data_sources=("value[variable]",),
                link_type="both",
            )
        },
        value_memberships_by_key={"variable": frozenset({"foo"})},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_rejects_link_prefix_when_input_scope_mismatches() -> None:
    source = "technology={ target = var:foo }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country",)),
            }
        },
        link_definitions_by_name={
            "var": LinkDefinition(
                name="var",
                output_scope="country",
                input_scopes=("state",),
                prefix="var:",
                from_data=True,
                data_sources=("value[variable]",),
                link_type="both",
            )
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_scope_ref_rejects_link_prefix_when_data_source_value_missing() -> None:
    source = "technology={ target = var:missing }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("state",)),
            }
        },
        link_definitions_by_name={
            "var": LinkDefinition(
                name="var",
                output_scope="country",
                input_scopes=("state",),
                prefix="var:",
                from_data=True,
                data_sources=("value[variable]",),
                link_type="both",
            )
        },
        value_memberships_by_key={"variable": frozenset({"foo"})},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_scope_ref_link_data_source_unresolved_defer_policy() -> None:
    source = "technology={ target = var:foo }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("state",)),
            }
        },
        link_definitions_by_name={
            "var": LinkDefinition(
                name="var",
                output_scope="country",
                input_scopes=("state",),
                prefix="var:",
                from_data=True,
                data_sources=("value[variable]",),
                link_type="both",
            )
        },
        policy=TypecheckPolicy(unresolved_reference="defer"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_multi_segment_link_chain() -> None:
    source = "technology={ target = owner.capital }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[state]", argument="state"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("state",)),
            }
        },
        link_definitions_by_name={
            "owner": LinkDefinition(
                name="owner",
                output_scope="country",
                input_scopes=("state",),
            ),
            "capital": LinkDefinition(
                name="capital",
                output_scope="state",
                input_scopes=("country", "state"),
            ),
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_rejects_multi_segment_link_chain_on_input_scope_mismatch() -> None:
    source = "technology={ target = owner.capital }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[state]", argument="state"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country",)),
            }
        },
        link_definitions_by_name={
            "owner": LinkDefinition(
                name="owner",
                output_scope="country",
                input_scopes=("state",),
            ),
            "capital": LinkDefinition(
                name="capital",
                output_scope="state",
                input_scopes=("country", "state"),
            ),
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_scope_ref_resolves_chain_with_prefixed_link_segment() -> None:
    source = "technology={ target = owner.var:foo }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "target": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("state",)),
            }
        },
        link_definitions_by_name={
            "owner": LinkDefinition(
                name="owner",
                output_scope="country",
                input_scopes=("state",),
            ),
            "var": LinkDefinition(
                name="var",
                output_scope="country",
                input_scopes=("country",),
                prefix="var:",
                from_data=True,
                data_sources=("value[variable]",),
                link_type="both",
            ),
        },
        value_memberships_by_key={"variable": frozenset({"foo"})},
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []
