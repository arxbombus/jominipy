from dataclasses import replace
from pathlib import Path

from jominipy.pipeline import run_typecheck
from jominipy.rules import (
    RuleFieldConstraint,
    build_complex_enum_definitions,
    build_complex_enum_values_from_file_texts,
    build_field_constraints_by_object,
    build_schema_graph,
    parse_rules_text,
    to_file_ir,
)
from jominipy.rules.normalize import normalize_ruleset
from jominipy.typecheck.rules import (
    FieldReferenceConstraintRule,
    default_typecheck_rules,
)
from jominipy.typecheck.services import TypecheckPolicy, TypecheckServices


def _build_constraints_and_enum_memberships(
    *,
    rules_source: str,
    file_texts_by_path: dict[str, str],
    source_path: str,
) -> tuple[dict[str, dict[str, RuleFieldConstraint]], dict[str, frozenset[str]]]:
    parsed = parse_rules_text(rules_source, source_path=source_path)
    file_ir = to_file_ir(parsed)
    ruleset = normalize_ruleset((file_ir,))
    schema = build_schema_graph(source_root="inline", ruleset=ruleset)
    definitions = build_complex_enum_definitions(schema)
    enum_memberships = build_complex_enum_values_from_file_texts(
        file_texts_by_path=file_texts_by_path,
        definitions_by_key=definitions,
    )
    field_constraints = build_field_constraints_by_object(schema.top_level_rule_statements)
    return field_constraints, enum_memberships


def _load_stl_enum_fixture() -> tuple[dict[str, dict[str, RuleFieldConstraint]], dict[str, frozenset[str]]]:
    fixture_root = (
        Path(__file__).resolve().parents[2]
        / "references/cwtools/CWToolsTests/testfiles/configtests/rulestests/STL/enums"
    )
    rules_source = (fixture_root / "rules.cwt").read_text(encoding="utf-8")
    file_texts_by_path = {
        path.relative_to(fixture_root).as_posix(): path.read_text(encoding="utf-8")
        for path in (fixture_root / "common").rglob("*.txt")
    }
    return _build_constraints_and_enum_memberships(
        rules_source=rules_source,
        file_texts_by_path=file_texts_by_path,
        source_path="stl-enums-rules.cwt",
    )


def test_typecheck_complex_enum_fixture_valid_cases_pass() -> None:
    field_constraints, enum_memberships = _load_stl_enum_fixture()
    source = """event = {
    singlefile = one
    singlefile = two
    top_leaf = one
    top_leaf = two
    complex_path = test1
    complex_path = test2
    complex_path = test3
    complex_path = test4
    complex_path = test5
    specific_path = stest1
    specific_path = stest2
    specific_path = stest4
}
"""
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object=field_constraints,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,), services=services)
    assert typecheck_result.diagnostics == []


def test_typecheck_complex_enum_fixture_valid_quoted_enum_cases_pass() -> None:
    field_constraints, enum_memberships = _load_stl_enum_fixture()
    source = """event = {
    quoted_singlefile = "one"
    quoted_singlefile = "two"
}
"""
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object=field_constraints,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,), services=services)
    assert typecheck_result.diagnostics == []


def test_typecheck_complex_enum_fixture_invalid_cases_fail() -> None:
    field_constraints, enum_memberships = _load_stl_enum_fixture()
    source = """event = {
    singlefile = three
    top_leaf = three
    complex_path = test6
    specific_path = stest3
    specific_path = stest5
}
"""
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object=field_constraints,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,), services=services)

    assert len(typecheck_result.diagnostics) == 5
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == [
        "TYPECHECK_INVALID_FIELD_REFERENCE",
        "TYPECHECK_INVALID_FIELD_REFERENCE",
        "TYPECHECK_INVALID_FIELD_REFERENCE",
        "TYPECHECK_INVALID_FIELD_REFERENCE",
        "TYPECHECK_INVALID_FIELD_REFERENCE",
    ]
    assert any("`event.singlefile`" in diagnostic.message for diagnostic in typecheck_result.diagnostics)
    assert any("`event.top_leaf`" in diagnostic.message for diagnostic in typecheck_result.diagnostics)
    assert any("`event.complex_path`" in diagnostic.message for diagnostic in typecheck_result.diagnostics)
    assert any("`event.specific_path`" in diagnostic.message for diagnostic in typecheck_result.diagnostics)


def test_typecheck_complex_enum_fixture_invalid_quoted_enum_cases_fail() -> None:
    field_constraints, enum_memberships = _load_stl_enum_fixture()
    source = """event = {
    quoted_singlefile = "three"
    quoted_singlefile = one
}
"""
    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object=field_constraints,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    typecheck_result = run_typecheck(source, rules=(custom_rule,), services=services)
    assert [diagnostic.code for diagnostic in typecheck_result.diagnostics] == [
        "TYPECHECK_INVALID_FIELD_REFERENCE",
        "TYPECHECK_INVALID_FIELD_REFERENCE",
    ]
    assert all(
        "`event.quoted_singlefile`" in diagnostic.message
        for diagnostic in typecheck_result.diagnostics
    )


def test_typecheck_complex_enum_path_strict_and_extension_filters() -> None:
    rules_source = """enums = {
    complex_enum[strict_ext] = {
        path = "common/targets"
        path_strict = yes
        path_extension = .txt
        start_from_root = yes
        name = {
            enum_name = scalar
        }
    }
}
event = {
    strict_field = enum[strict_ext]
}
"""
    field_constraints, enum_memberships = _build_constraints_and_enum_memberships(
        rules_source=rules_source,
        source_path="inline-strict-ext.cwt",
        file_texts_by_path={
            "common/targets/ok.txt": "alpha = yes\n",
            "common/targets/sub/skip.txt": "beta = yes\n",
            "common/targets/wrong.yml": "gamma = yes\n",
            "common/other/nope.txt": "delta = yes\n",
        },
    )

    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object=field_constraints,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    valid_result = run_typecheck("event={ strict_field = alpha }\n", rules=(custom_rule,), services=services)
    invalid_result = run_typecheck("event={ strict_field = beta }\n", rules=(custom_rule,), services=services)

    assert valid_result.diagnostics == []
    assert [diagnostic.code for diagnostic in invalid_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_complex_enum_path_filters_are_case_insensitive() -> None:
    rules_source = """enums = {
    complex_enum[case_enum] = {
        path = "game/common/targets"
        path_file = "TARGETS.TXT"
        path_extension = .TXT
        start_from_root = yes
        name = {
            enum_name = scalar
        }
    }
}
event = {
    field = enum[case_enum]
}
"""
    field_constraints, enum_memberships = _build_constraints_and_enum_memberships(
        rules_source=rules_source,
        source_path="inline-case-insensitive.cwt",
        file_texts_by_path={
            "COMMON/TARGETS/targets.txt": "alpha = yes\n",
            "common/targets/other.txt": "beta = yes\n",
        },
    )

    custom_rule = FieldReferenceConstraintRule(
        field_constraints_by_object=field_constraints,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )

    valid_result = run_typecheck("event={ field = alpha }\n", rules=(custom_rule,), services=services)
    invalid_result = run_typecheck("event={ field = beta }\n", rules=(custom_rule,), services=services)

    assert valid_result.diagnostics == []
    assert [diagnostic.code for diagnostic in invalid_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_typecheck_complex_enum_reference_with_default_rule_stack() -> None:
    field_constraints, enum_memberships = _load_stl_enum_fixture()
    services = TypecheckServices(
        enum_memberships_by_key=enum_memberships,
        policy=TypecheckPolicy(unresolved_reference="error"),
    )
    default_rules = default_typecheck_rules(services=services)
    rules = tuple(
        replace(rule, field_constraints_by_object=field_constraints)
        if isinstance(rule, FieldReferenceConstraintRule)
        else rule
        for rule in default_rules
    )

    valid_result = run_typecheck("event={ singlefile = one }\n", rules=rules, services=services)
    invalid_result = run_typecheck("event={ singlefile = three }\n", rules=rules, services=services)

    assert valid_result.diagnostics == []
    assert [diagnostic.code for diagnostic in invalid_result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]
