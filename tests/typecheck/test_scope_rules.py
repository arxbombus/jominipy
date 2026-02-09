from jominipy.pipeline import run_typecheck
from jominipy.rules import (
    RuleFieldConstraint,
    RuleValueSpec,
)
from jominipy.rules.ir import RuleScopeReplacement
from jominipy.rules.semantics import RuleFieldScopeConstraint
from jominipy.typecheck.rules import (
    FieldReferenceConstraintRule,
    FieldScopeContextRule,
)
from jominipy.typecheck.services import (
    TypecheckPolicy,
)


def test_typecheck_scope_context_rule_uses_push_scope_for_nested_fields() -> None:
    source = "technology={ wrapper={ target = TAG } }\n"
    custom_rule = FieldScopeContextRule(
        field_scope_constraints_by_object={
            "technology": {
                ("wrapper",): RuleFieldScopeConstraint(push_scope=("country",)),
                ("wrapper", "target"): RuleFieldScopeConstraint(required_scope=("country",)),
            }
        }
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_context_rule_reports_missing_scope_transition() -> None:
    source = "technology={ wrapper={ target = TAG } }\n"
    custom_rule = FieldScopeContextRule(
        field_scope_constraints_by_object={
            "technology": {
                ("wrapper", "target"): RuleFieldScopeConstraint(required_scope=("country",)),
            }
        }
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_SCOPE_CONTEXT"]


def test_typecheck_scope_ref_resolves_this_alias_from_push_scope_context() -> None:
    source = "technology={ who = this }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country",)),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_from_alias_after_nested_push_scope() -> None:
    source = "technology={ who = from }\n"
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
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country", "state")),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_alias_from_replace_scope_mapping() -> None:
    source = "technology={ who = from }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    replace_scope=(RuleScopeReplacement(source="from", target="country"),),
                ),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_prev_alias_after_push_scope() -> None:
    source = "technology={ who = prev }\n"
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
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country", "state")),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_prevprev_alias_after_three_pushes() -> None:
    source = "technology={ who = prevprev }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "state", "province"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country", "state", "province")),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_resolves_prev_alias_from_replace_scope_mapping() -> None:
    source = "technology={ who = prev }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    replace_scope=(RuleScopeReplacement(source="prev", target="country"),),
                ),
            }
        },
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_does_not_leak_push_scope_from_sibling_branch() -> None:
    source = "technology={ branch_b = this }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "branch_b": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country"}),
        field_scope_constraints_by_object={
            "technology": {
                ("branch_a",): RuleFieldScopeConstraint(push_scope=("country",)),
                ("branch_b",): RuleFieldScopeConstraint(required_scope=("country",)),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_scope_ref_applies_replace_scope_for_from_alias() -> None:
    source = "technology={ wrapper={ who = from } }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country"}),
        field_scope_constraints_by_object={
            "technology": {
                ("wrapper",): RuleFieldScopeConstraint(
                    replace_scope=(RuleScopeReplacement(source="from", target="country"),),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_nested_replace_scope_overrides_chain_alias() -> None:
    source = "technology={ wrapper={ who = from } }\n"
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
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country", "state")),
                ("wrapper",): RuleFieldScopeConstraint(
                    replace_scope=(RuleScopeReplacement(source="from", target="country"),),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_reports_ambiguous_replace_scope_alias_mapping() -> None:
    source = "technology={ who = from }\n"
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
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    replace_scope=(
                        RuleScopeReplacement(source="from", target="country"),
                        RuleScopeReplacement(source="from", target="state"),
                    ),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT"]


def test_typecheck_scope_ref_push_scope_takes_precedence_over_replace_scope_same_path() -> None:
    source = "technology={ who = from }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[country]", argument="country"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "planet", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    push_scope=("country", "state"),
                    replace_scope=(RuleScopeReplacement(source="from", target="planet"),),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_ref_push_scope_precedence_ignores_replace_scope_override() -> None:
    source = "technology={ who = from }\n"
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "who": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="scope_ref", raw="scope[planet]", argument="planet"),),
                ),
            }
        },
        known_scopes=frozenset({"country", "planet", "state"}),
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    push_scope=("country", "state"),
                    replace_scope=(RuleScopeReplacement(source="from", target="planet"),),
                ),
            }
        },
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_scope_context_push_scope_precedence_skips_replace_scope_ambiguity() -> None:
    source = "technology={ who = TAG }\n"
    custom_rule = FieldScopeContextRule(
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    push_scope=("country",),
                    replace_scope=(
                        RuleScopeReplacement(source="from", target="country"),
                        RuleScopeReplacement(source="from", target="state"),
                    ),
                ),
                ("who",): RuleFieldScopeConstraint(required_scope=("country",)),
            }
        }
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert typecheck_result.diagnostics == []


def test_typecheck_scope_context_reports_ambiguous_replace_scope_alias_mapping() -> None:
    source = "technology={ who = TAG }\n"
    custom_rule = FieldScopeContextRule(
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(
                    replace_scope=(
                        RuleScopeReplacement(source="from", target="country"),
                        RuleScopeReplacement(source="from", target="state"),
                    ),
                ),
                ("who",): RuleFieldScopeConstraint(required_scope=("country",)),
            }
        }
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT"]


def test_typecheck_scope_context_does_not_leak_between_top_level_objects() -> None:
    source = "technology={ who = TAG }\nfocus={ who = TAG }\n"
    custom_rule = FieldScopeContextRule(
        field_scope_constraints_by_object={
            "technology": {
                (): RuleFieldScopeConstraint(push_scope=("country",)),
                ("who",): RuleFieldScopeConstraint(required_scope=("country",)),
            },
            "focus": {
                ("who",): RuleFieldScopeConstraint(required_scope=("country",)),
            },
        }
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,))
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == ["TYPECHECK_INVALID_SCOPE_CONTEXT"]
