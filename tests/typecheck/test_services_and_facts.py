from jominipy.parser import parse_result
from jominipy.typecheck.rules import (
    FieldConstraintRule,
    default_typecheck_rules,
)
from jominipy.typecheck.services import (
    TypecheckPolicy,
    TypecheckServices,
)


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
