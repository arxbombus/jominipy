from jominipy.parser import ParseMode, parse_result
from jominipy.pipeline import run_check, run_format, run_lint


def test_run_lint_reuses_provided_parse_result() -> None:
    source = "a=1\n"
    parsed = parse_result(source)

    result = run_lint("ignored", parse=parsed)

    assert result.parse is parsed
    assert result.diagnostics == parsed.diagnostics


def test_run_lint_rejects_parse_with_mode_or_options() -> None:
    parsed = parse_result("a=1\n")

    try:
        run_lint("a=1\n", parse=parsed, mode=ParseMode.PERMISSIVE)
    except ValueError as exc:
        assert "Pass either parse or options/mode, not both" in str(exc)
    else:
        raise AssertionError("Expected ValueError when passing parse and mode together")


def test_run_format_scaffold_returns_original_source() -> None:
    source = "a=1\n"

    result = run_format(source)

    assert result.formatted_text == source
    assert result.changed is False
    assert result.diagnostics == []


def test_run_check_reports_parse_errors_through_lint_pipeline() -> None:
    source = 'a="x";\n'

    result = run_check(source)

    assert result.parse.source_text == source
    assert result.has_errors is True
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "PARSER_UNEXPECTED_TOKEN"
