from jominipy.ast import AstScalar
from jominipy.parser import ParseMode, parse, parse_result


def test_parse_result_exposes_green_diagnostics_and_error_state() -> None:
    result = parse_result("a=1\n")

    assert result.green_root() is result.parsed.root
    assert result.diagnostics == []
    assert result.has_errors is False


def test_parse_result_caches_syntax_and_ast() -> None:
    result = parse_result("a=1\n")

    first_syntax = result.syntax_root()
    second_syntax = result.syntax_root()
    assert first_syntax is second_syntax

    first_ast = result.ast_root()
    second_ast = result.ast_root()
    assert first_ast is second_ast


def test_parse_result_root_view_exposes_top_level_object_shape() -> None:
    result = parse_result("a=1\n")
    view = result.root_view()
    object_view = view.as_object()

    assert object_view is not None
    scalar = object_view["a"]
    assert isinstance(scalar, AstScalar)
    assert scalar.raw_text == "1"

    block_view = result.root_view()
    assert block_view is view


def test_parse_result_strict_and_permissive_match_parse_jomini_contract() -> None:
    source = 'a="x";\n'

    strict_result = parse_result(source)
    permissive_result = parse_result(source, mode=ParseMode.PERMISSIVE)

    strict_parsed = parse(source)
    permissive_parsed = parse(source, mode=ParseMode.PERMISSIVE)

    assert strict_result.diagnostics == strict_parsed.diagnostics
    assert permissive_result.diagnostics == permissive_parsed.diagnostics
    assert strict_result.has_errors is True
    assert permissive_result.has_errors is False


def test_parse_result_root_view_is_empty_for_empty_source() -> None:
    result = parse_result("")
    view = result.root_view()

    assert view.is_empty_ambiguous is True
    assert view.as_object() == {}
    assert view.as_multimap() == {}
    assert view.as_array() == []
