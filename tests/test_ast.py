import pytest

from jominipy.ast import (
    AstBlock,
    AstError,
    AstKeyValue,
    AstScalar,
    AstTaggedBlockValue,
    ScalarKind,
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
    assert interpreted.kind == ScalarKind.UNKNOWN
    assert interpreted.is_unknown is True
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


@pytest.mark.parametrize(
    ("text", "expected_kind", "expected_value"),
    [
        ("yes", ScalarKind.BOOL, True),
        ("no", ScalarKind.BOOL, False),
        ("1821.1.1", ScalarKind.DATE_LIKE, (1821, 1, 1)),
        ("-5", ScalarKind.NUMBER, -5),
        ("+3", ScalarKind.NUMBER, 3),
        ("1.000", ScalarKind.NUMBER, 1.0),
        ("18446744073709547616", ScalarKind.NUMBER, 18446744073709547616),
        ("foo", ScalarKind.UNKNOWN, None),
    ],
)
def test_interpret_scalar_table_driven_unquoted_cases(
    text: str,
    expected_kind: ScalarKind,
    expected_value: bool | int | float | tuple[int, int, int] | None,
) -> None:
    interpreted = interpret_scalar(text)
    assert interpreted.kind == expected_kind
    assert interpreted.value == expected_value


def test_interpret_scalar_quoted_default_and_opt_in_behavior() -> None:
    quoted_default = interpret_scalar("yes", was_quoted=True)
    assert quoted_default.kind == ScalarKind.UNKNOWN
    assert quoted_default.value is None
    assert quoted_default.bool_value is None

    quoted_opt_in = interpret_scalar("yes", was_quoted=True, allow_quoted=True)
    assert quoted_opt_in.kind == ScalarKind.BOOL
    assert quoted_opt_in.value is True
    assert quoted_opt_in.bool_value is True

    quoted_date_default = interpret_scalar("1821.1.1", was_quoted=True)
    assert quoted_date_default.kind == ScalarKind.UNKNOWN
    assert quoted_date_default.date_value is None

    quoted_date_opt_in = interpret_scalar(
        "1821.1.1",
        was_quoted=True,
        allow_quoted=True,
    )
    assert quoted_date_opt_in.kind == ScalarKind.DATE_LIKE
    assert quoted_date_opt_in.value == (1821, 1, 1)
    assert quoted_date_opt_in.date_value == (1821, 1, 1)


@pytest.mark.parametrize("case", ALL_JOMINI_CASES, ids=case_id)
def test_ast_lowers_all_central_cases(case: JominiCase) -> None:
    parsed = parse_jomini(case.source)
    ast = lower_tree(parsed.root)

    debug_dump_cst(f"ast_case::{case.name}", case.source, parsed.root)
    debug_dump_diagnostics(f"ast_case::{case.name}", parsed.diagnostics, source=case.source)
    debug_dump_ast(f"ast_case::{case.name}", ast, source=case.source)

    assert isinstance(ast.statements, tuple)
