from typing import cast

from jominipy.lint.rules import LintRule
from jominipy.parser import parse_result
from jominipy.pipeline import run_lint, run_typecheck
from jominipy.typecheck.rules import TypecheckRule


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
        "LINT_SEMANTIC_MISSING_START_YEAR",
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

        def run(self, facts, type_facts, text):
            return []

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

        def run(self, facts, type_facts, text):
            return []

    try:
        run_typecheck(
            "a=1\n",
            rules=cast(tuple[TypecheckRule, ...], (BadTypeRule(),)),
        )
    except ValueError as exc:
        assert "invalid confidence" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid typecheck confidence")


def test_lint_rejects_correctness_domain_rule() -> None:
    class BadLintRule:
        code = "LINT_BAD_DOMAIN"
        name = "badLintDomain"
        category = "semantic"
        domain = "correctness"
        confidence = "policy"

        def run(self, facts, type_facts, text):
            return []

    try:
        run_lint("a=1\n", rules=cast(tuple[LintRule, ...], (BadLintRule(),)))
    except ValueError as exc:
        assert "invalid domain" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid lint rule domain")
