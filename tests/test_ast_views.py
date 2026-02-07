import pytest

from jominipy.ast import (
    AstBlock,
    AstBlockView,
    AstError,
    AstKeyValue,
    AstScalar,
    AstSourceFile,
    AstTaggedBlockValue,
    ScalarKind,
    parse_to_ast,
)
from tests._debug import debug_dump_ast_block_view, debug_print_source
from tests._shared_cases import ALL_JOMINI_CASES, JominiCase, case_id


def _top_level_block(ast_source: str, key: str) -> AstBlock:
    ast = parse_to_ast(ast_source)
    top_level = {
        statement.key.raw_text: statement
        for statement in ast.statements
        if isinstance(statement, AstKeyValue)
    }
    statement = top_level[key]
    assert isinstance(statement.value, AstBlock)
    return statement.value


def test_ast_block_view_shape_selection_object_array_mixed_empty() -> None:
    obj = AstBlockView(_top_level_block("obj={a=1 b=2}\n", "obj"))
    arr = AstBlockView(_top_level_block("arr={1 2}\n", "arr"))
    mixed = AstBlockView(_top_level_block("mixed={1 a=2}\n", "mixed"))
    empty = AstBlockView(_top_level_block("empty={}\n", "empty"))

    assert obj.as_object() is not None
    assert obj.as_multimap() is not None
    assert obj.as_array() is None

    assert arr.as_array() is not None
    assert arr.as_object() is None
    assert arr.as_multimap() is None

    assert mixed.as_object() is None
    assert mixed.as_multimap() is None
    assert mixed.as_array() is None

    assert empty.as_object() == {}
    assert empty.as_multimap() == {}
    assert empty.as_array() == []


def test_ast_block_view_multimap_preserves_modifier_order() -> None:
    view = AstBlockView(
        _top_level_block(
            "stats={modifier={country_revolt_factor=0.5} modifier={country_pop_unrest=0.25}}\n",
            "stats",
        )
    )

    object_view = view.as_object()
    multimap_view = view.as_multimap()

    assert object_view is not None
    assert multimap_view is not None
    assert list(multimap_view.keys()) == ["modifier"]
    assert len(multimap_view["modifier"]) == 2

    latest = object_view["modifier"]
    assert isinstance(latest, AstBlock)
    latest_entry = latest.statements[0]
    assert isinstance(latest_entry, AstKeyValue)
    assert latest_entry.key.raw_text == "country_pop_unrest"

    first = multimap_view["modifier"][0]
    second = multimap_view["modifier"][1]
    assert isinstance(first, AstBlock)
    assert isinstance(second, AstBlock)
    first_entry = first.statements[0]
    second_entry = second.statements[0]
    assert isinstance(first_entry, AstKeyValue)
    assert isinstance(second_entry, AstKeyValue)
    assert first_entry.key.raw_text == "country_revolt_factor"
    assert second_entry.key.raw_text == "country_pop_unrest"


def test_ast_block_view_scalar_helpers_preserve_quoted_default_policy() -> None:
    view = AstBlockView(
        _top_level_block(
            'values={flag=yes quoted_flag="yes" date=1821.1.1 quoted_date="1821.1.1"}\n',
            "values",
        )
    )

    flag = view.get_scalar("flag")
    quoted_flag_default = view.get_scalar("quoted_flag")
    quoted_flag_opt_in = view.get_scalar("quoted_flag", allow_quoted=True)
    date = view.get_scalar("date")
    quoted_date_default = view.get_scalar("quoted_date")
    quoted_date_opt_in = view.get_scalar("quoted_date", allow_quoted=True)

    assert flag is not None and flag.kind == ScalarKind.BOOL and flag.value is True
    assert quoted_flag_default is not None and quoted_flag_default.kind == ScalarKind.UNKNOWN
    assert quoted_flag_opt_in is not None and quoted_flag_opt_in.kind == ScalarKind.BOOL
    assert date is not None and date.kind == ScalarKind.DATE_LIKE
    assert quoted_date_default is not None and quoted_date_default.kind == ScalarKind.UNKNOWN
    assert quoted_date_opt_in is not None and quoted_date_opt_in.kind == ScalarKind.DATE_LIKE


def test_ast_block_view_get_scalar_all_uses_multimap() -> None:
    view = AstBlockView(
        _top_level_block(
            "values={n=1 n=2 n=three tagged=rgb{1 2 3}}\n",
            "values",
        )
    )

    values = view.get_scalar_all("n")
    missing = view.get_scalar_all("missing")
    non_scalar = view.get_scalar_all("tagged")

    assert [item.kind for item in values] == [
        ScalarKind.NUMBER,
        ScalarKind.NUMBER,
        ScalarKind.UNKNOWN,
    ]
    assert [item.value for item in values] == [1, 2, None]
    assert missing == []
    assert non_scalar == []


def _collect_blocks_from_source_file(ast: AstSourceFile) -> list[tuple[str, AstBlock]]:
    blocks: list[tuple[str, AstBlock]] = []

    def visit_statement(
        statement: AstKeyValue | AstScalar | AstBlock | AstError,
        path: str,
    ) -> None:
        if isinstance(statement, AstKeyValue):
            visit_value(statement.value, f"{path}/kv:{statement.key.raw_text}")
            return
        if isinstance(statement, AstBlock):
            visit_value(statement, f"{path}/stmt_block")

    def visit_value(
        value: AstScalar | AstBlock | AstTaggedBlockValue | None,
        path: str,
    ) -> None:
        if isinstance(value, AstBlock):
            blocks.append((path, value))
            for index, child in enumerate(value.statements):
                visit_statement(child, f"{path}/s[{index}]")
            return
        if isinstance(value, AstTaggedBlockValue):
            blocks.append((f"{path}/tag:{value.tag.raw_text}", value.block))
            for index, child in enumerate(value.block.statements):
                visit_statement(child, f"{path}/tag:{value.tag.raw_text}/s[{index}]")

    for index, statement in enumerate(ast.statements):
        visit_statement(statement, f"root/s[{index}]")

    return blocks


@pytest.mark.parametrize("case", ALL_JOMINI_CASES, ids=case_id)
def test_ast_views_runs_all_central_cases(case: JominiCase) -> None:
    ast = parse_to_ast(case.source)
    blocks = _collect_blocks_from_source_file(ast)
    debug_print_source(f"central::{case.name}", case.source)

    for index, (path, block) in enumerate(blocks):
        view = AstBlockView(block)
        debug_dump_ast_block_view(
            f"central::{case.name}::block[{index}]::{path}",
            view,
        )

    assert isinstance(ast.statements, tuple)
