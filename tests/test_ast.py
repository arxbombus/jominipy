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


def test_ast_block_shape_classification_helpers() -> None:
    ast = parse_to_ast("obj={a=1 b=2}\narr={1 2}\nmixed={1 a=2}\nempty={}\n")
    top_level = {statement.key.raw_text: statement for statement in ast.statements if isinstance(statement, AstKeyValue)}

    obj_stmt = top_level["obj"]
    arr_stmt = top_level["arr"]
    mixed_stmt = top_level["mixed"]
    empty_stmt = top_level["empty"]

    assert isinstance(obj_stmt.value, AstBlock)
    assert obj_stmt.value.is_object_like is True
    assert obj_stmt.value.is_array_like is False
    assert obj_stmt.value.is_mixed is False
    assert obj_stmt.value.is_empty_ambiguous is False

    assert isinstance(arr_stmt.value, AstBlock)
    assert arr_stmt.value.is_object_like is False
    assert arr_stmt.value.is_array_like is True
    assert arr_stmt.value.is_mixed is False
    assert arr_stmt.value.is_empty_ambiguous is False

    assert isinstance(mixed_stmt.value, AstBlock)
    assert mixed_stmt.value.is_object_like is False
    assert mixed_stmt.value.is_array_like is False
    assert mixed_stmt.value.is_mixed is True
    assert mixed_stmt.value.is_empty_ambiguous is False

    assert isinstance(empty_stmt.value, AstBlock)
    assert empty_stmt.value.is_object_like is False
    assert empty_stmt.value.is_array_like is False
    assert empty_stmt.value.is_mixed is False
    assert empty_stmt.value.is_empty_ambiguous is True


def test_ast_block_to_object_repeated_key_default_and_multimap() -> None:
    ast = parse_to_ast(
        "stats={modifier={country_revolt_factor=0.5} modifier={country_pop_unrest=0.25}}\n"
    )
    statement = ast.statements[0]
    assert isinstance(statement, AstKeyValue)
    assert isinstance(statement.value, AstBlock)

    block = statement.value
    assert len(block.statements) == 2
    assert all(isinstance(item, AstKeyValue) for item in block.statements)
    assert all(item.key.raw_text == "modifier" for item in block.statements if isinstance(item, AstKeyValue))

    default_object = block.to_object()
    assert set(default_object.keys()) == {"modifier"}
    latest = default_object["modifier"]
    assert isinstance(latest, AstBlock)
    assert len(latest.statements) == 1
    latest_entry = latest.statements[0]
    assert isinstance(latest_entry, AstKeyValue)
    assert latest_entry.key.raw_text == "country_pop_unrest"

    multimap_object = block.to_object(multimap=True)
    assert set(multimap_object.keys()) == {"modifier"}
    modifiers = multimap_object["modifier"]
    assert len(modifiers) == 2
    assert all(isinstance(item, AstBlock) for item in modifiers)
    first_block = modifiers[0]
    second_block = modifiers[1]
    assert isinstance(first_block, AstBlock)
    assert isinstance(second_block, AstBlock)
    first_entry = first_block.statements[0]
    second_entry = second_block.statements[0]
    assert isinstance(first_entry, AstKeyValue)
    assert isinstance(second_entry, AstKeyValue)
    assert first_entry.key.raw_text == "country_revolt_factor"
    assert second_entry.key.raw_text == "country_pop_unrest"


def test_ast_block_coercion_helpers_array_mixed_and_empty_behavior() -> None:
    ast = parse_to_ast("arr={1 2 3}\nmixed={1 a=2}\nempty={}\n")
    top_level = {statement.key.raw_text: statement for statement in ast.statements if isinstance(statement, AstKeyValue)}

    arr_stmt = top_level["arr"]
    mixed_stmt = top_level["mixed"]
    empty_stmt = top_level["empty"]

    assert isinstance(arr_stmt.value, AstBlock)
    array_values = arr_stmt.value.to_array()
    assert [value.raw_text for value in array_values if isinstance(value, AstScalar)] == ["1", "2", "3"]
    with pytest.raises(ValueError, match="object-like"):
        _ = arr_stmt.value.to_object()

    assert isinstance(mixed_stmt.value, AstBlock)
    with pytest.raises(ValueError, match="object-like"):
        _ = mixed_stmt.value.to_object()
    with pytest.raises(ValueError, match="array-like"):
        _ = mixed_stmt.value.to_array()

    assert isinstance(empty_stmt.value, AstBlock)
    assert empty_stmt.value.to_object() == {}
    assert empty_stmt.value.to_object(multimap=True) == {}
    assert empty_stmt.value.to_array() == []


@pytest.mark.parametrize("case", ALL_JOMINI_CASES, ids=case_id)
def test_ast_lowers_all_central_cases(case: JominiCase) -> None:
    parsed = parse_jomini(case.source)
    ast = lower_tree(parsed.root)

    debug_dump_cst(f"ast_case::{case.name}", case.source, parsed.root)
    debug_dump_diagnostics(f"ast_case::{case.name}", parsed.diagnostics, source=case.source)
    debug_dump_ast(f"ast_case::{case.name}", ast, source=case.source)

    assert isinstance(ast.statements, tuple)
