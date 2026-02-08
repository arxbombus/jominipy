from typing import cast

from jominipy.analysis import AnalysisFacts
from jominipy.diagnostics import Diagnostic
from jominipy.lint.rules import (
    LintConfidence,
    LintDomain,
    SemanticInvalidFieldTypeRule,
    SemanticMissingRequiredFieldRule,
)
from jominipy.parser import parse_result
from jominipy.pipeline import run_lint, run_typecheck
from jominipy.rules import RuleFieldConstraint, RuleValueSpec
from jominipy.typecheck.rules import TypecheckFacts, TypecheckRule


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


def test_lint_cwtools_type_rule_with_custom_schema() -> None:
    source = "technology={ level = yes }\n"
    custom_rule = SemanticInvalidFieldTypeRule(
        field_constraints_by_object={
            "technology": {
                "level": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="primitive", raw="int", primitive="int", argument=None),),
                )
            }
        },
    )

    lint_result = run_lint(source, rules=(custom_rule,))
    codes = [diagnostic.code for diagnostic in lint_result.diagnostics]

    assert codes == ["LINT_SEMANTIC_INVALID_FIELD_TYPE"]
    assert "technology.level" in lint_result.diagnostics[0].message
