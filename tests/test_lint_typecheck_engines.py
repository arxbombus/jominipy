from jominipy.parser import parse_result
from jominipy.pipeline import run_lint, run_typecheck


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
