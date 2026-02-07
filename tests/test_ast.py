import pytest

from jominipy.ast import (
    AstBlock,
    AstError,
    AstKeyValue,
    AstScalar,
    AstTaggedBlockValue,
    interpret_scalar,
    lower_tree,
    parse_date_like,
    parse_to_ast,
)
from jominipy.parser import parse_jomini
from tests._debug import debug_dump_ast, debug_dump_cst, debug_dump_diagnostics
from tests._shared_cases import ALL_JOMINI_CASES, JominiCase, case_id


def test_ast_basic_key_value_shape() -> None:
    ast = parse_to_ast("aaa=foo\n")
    assert len(ast.statements) == 1

    statement = ast.statements[0]
    assert isinstance(statement, AstKeyValue)
    assert statement.key.raw_text == "aaa"
    assert statement.operator == "="
    assert isinstance(statement.value, AstScalar)
    assert statement.value.raw_text == "foo"


def test_ast_nested_blocks_shape() -> None:
    ast = parse_to_ast("a={b=2}\n")
    outer = ast.statements[0]
    assert isinstance(outer, AstKeyValue)
    assert isinstance(outer.value, AstBlock)
    assert len(outer.value.statements) == 1

    inner = outer.value.statements[0]
    assert isinstance(inner, AstKeyValue)
    assert isinstance(inner.value, AstScalar)
    assert inner.key.raw_text == "b"
    assert inner.value.raw_text == "2"


def test_ast_tagged_block_value_shape() -> None:
    ast = parse_to_ast("color = rgb { 100 200 150 }\n")
    statement = ast.statements[0]
    assert isinstance(statement, AstKeyValue)
    assert isinstance(statement.value, AstTaggedBlockValue)
    assert statement.value.tag.raw_text == "rgb"
    assert len(statement.value.block.statements) == 3
    assert all(isinstance(item, AstScalar) for item in statement.value.block.statements)


def test_ast_date_like_interpretation_is_delayed_for_quoted_scalars() -> None:
    ast = parse_to_ast('date=1821.1.1\nquoted_date="1821.1.1"\n')
    unquoted = ast.statements[0]
    quoted = ast.statements[1]

    assert isinstance(unquoted, AstKeyValue)
    assert isinstance(unquoted.value, AstScalar)
    assert parse_date_like(unquoted.value.raw_text) == (1821, 1, 1)

    assert isinstance(quoted, AstKeyValue)
    assert isinstance(quoted.value, AstScalar)
    interpreted = interpret_scalar(
        quoted.value.raw_text,
        was_quoted=quoted.value.was_quoted,
    )
    assert interpreted.date_value is None


def test_ast_preserves_quoted_vs_unquoted_scalar_distinction() -> None:
    ast = parse_to_ast('unit_type="western"\nunit_type=western\n')

    first = ast.statements[0]
    second = ast.statements[1]
    assert isinstance(first, AstKeyValue)
    assert isinstance(second, AstKeyValue)
    assert isinstance(first.value, AstScalar)
    assert isinstance(second.value, AstScalar)
    assert first.value.was_quoted is True
    assert second.value.was_quoted is False


def test_ast_lowers_partial_tree_from_recovered_parse() -> None:
    parsed = parse_jomini("a=1 ?=oops\nb=2\n")
    assert parsed.diagnostics

    ast = lower_tree(parsed.root)
    key_values = [item for item in ast.statements if isinstance(item, AstKeyValue)]
    errors = [item for item in ast.statements if isinstance(item, AstError)]

    assert len(key_values) == 2
    assert key_values[0].key.raw_text == "a"
    assert key_values[1].key.raw_text == "b"
    assert errors


@pytest.mark.parametrize("case", ALL_JOMINI_CASES, ids=case_id)
def test_ast_lowers_all_central_cases(case: JominiCase) -> None:
    parsed = parse_jomini(case.source)
    ast = lower_tree(parsed.root)

    debug_dump_cst(f"ast_case::{case.name}", case.source, parsed.root)
    debug_dump_diagnostics(f"ast_case::{case.name}", parsed.diagnostics, source=case.source)
    debug_dump_ast(f"ast_case::{case.name}", ast, source=case.source)

    assert isinstance(ast.statements, tuple)
