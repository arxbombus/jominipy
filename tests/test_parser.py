import pytest

from jominipy.cst import GreenNode, GreenToken
from jominipy.diagnostics import Diagnostic
from jominipy.lexer import BufferedLexer, Lexer, TokenKind
from jominipy.parser import (
    ParseMode,
    Parser,
    ParseRecoveryTokenSet,
    ParserOptions,
    RecoveryError,
    TokenSource,
    parse_jomini,
)
from jominipy.syntax import JominiSyntaxKind
from tests._debug import debug_dump_cst, debug_dump_diagnostics
from tests._shared_cases import PARSER_CASES, JominiCase, case_id, case_source


def _debug_print_cst_if_enabled(test_name: str, source: str, root: GreenNode) -> None:
    debug_dump_cst(test_name, source, root)


def _debug_print_diagnostics_if_enabled(test_name: str, diagnostics: list[Diagnostic]) -> None:
    debug_dump_diagnostics(test_name, diagnostics)


def _collect_node_kinds(root: GreenNode) -> list[JominiSyntaxKind]:
    kinds: list[JominiSyntaxKind] = []

    def walk(node: GreenNode) -> None:
        kinds.append(node.kind)
        for child in node.children:
            if isinstance(child, GreenNode):
                walk(child)

    walk(root)
    return kinds


def _collect_tokens(root: GreenNode) -> list[GreenToken]:
    tokens: list[GreenToken] = []

    def walk(node: GreenNode) -> None:
        for child in node.children:
            if isinstance(child, GreenNode):
                walk(child)
            else:
                tokens.append(child)

    walk(root)
    return tokens


def _assert_parse_ok(name: str, source: str) -> None:
    parsed = parse_jomini(source)
    _debug_print_cst_if_enabled(name, source, parsed.root)
    _debug_print_diagnostics_if_enabled(name, parsed.diagnostics)
    assert parsed.diagnostics == []


def _assert_parse_fails(name: str, source: str) -> None:
    parsed = parse_jomini(source)
    _debug_print_cst_if_enabled(name, source, parsed.root)
    _debug_print_diagnostics_if_enabled(name, parsed.diagnostics)
    assert parsed.diagnostics != []


def test_simple_toml_like_example() -> None:
    src = case_source("simple_toml_like_example")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("simple_toml_like_example", src, parsed.root)
    assert parsed.diagnostics == []

    kinds = _collect_node_kinds(parsed.root)
    assert JominiSyntaxKind.SOURCE_FILE in kinds
    assert JominiSyntaxKind.STATEMENT_LIST in kinds
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 2


def test_token_text_excludes_leading_trivia() -> None:
    src = "# this is a comment\na = 1\n"
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("token_text_excludes_leading_trivia", src, parsed.root)
    assert parsed.diagnostics == []

    tokens = _collect_tokens(parsed.root)
    a_tokens = [t for t in tokens if t.kind == JominiSyntaxKind.IDENTIFIER and t.text == "a"]
    assert a_tokens, "Expected identifier token text to be exactly 'a'"
    for token in a_tokens:
        assert "#" not in token.text
        assert "\n" not in token.text
        assert token.text == token.text.strip()


def test_token_text_excludes_trailing_trivia() -> None:
    src = "a = 1\n"
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("token_text_excludes_trailing_trivia", src, parsed.root)
    assert parsed.diagnostics == []

    tokens = _collect_tokens(parsed.root)
    equal_tokens = [t for t in tokens if t.kind == JominiSyntaxKind.EQUAL]
    int_tokens = [t for t in tokens if t.kind == JominiSyntaxKind.INT]
    assert any(t.text == "=" for t in equal_tokens)
    assert any(t.text == "1" for t in int_tokens)


def test_repeated_key_is_valid() -> None:
    src = case_source("repeated_key_is_valid")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("repeated_key_is_valid", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 3


def test_common_scalar_examples() -> None:
    src = case_source("common_scalar_examples")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("common_scalar_examples", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 7


def test_multiple_pairs_per_line() -> None:
    src = case_source("multiple_pairs_per_line")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("multiple_pairs_per_line", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 3


def test_operator_variants() -> None:
    src = case_source("operator_variants")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("operator_variants", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 7


def test_implicit_block_assignment() -> None:
    src = case_source("implicit_block_assignment")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("implicit_block_assignment", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 2
    assert JominiSyntaxKind.BLOCK in kinds


def test_block_object_and_array_like_content() -> None:
    src = case_source("block_object_and_array_like_content")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("block_object_and_array_like_content", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert JominiSyntaxKind.BLOCK in kinds
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) >= 2


def test_dense_boundary_characters() -> None:
    src = case_source("dense_boundary_characters")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("dense_boundary_characters", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert JominiSyntaxKind.BLOCK in kinds
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 4


def test_comment_inside_quote_is_not_comment() -> None:
    src = case_source("comment_inside_quote_is_not_comment")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("comment_inside_quote_is_not_comment", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 1


def test_multiline_quoted_scalar() -> None:
    src = case_source("multiline_quoted_scalar")
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("multiline_quoted_scalar", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 1


def test_keys_are_scalars() -> None:
    src = case_source("keys_are_scalars")
    _assert_parse_ok("keys_are_scalars", src)


def test_quoted_scalar_escape_variants() -> None:
    src = case_source("quoted_scalar_escape_variants")
    _assert_parse_ok("quoted_scalar_escape_variants", src)


def test_non_ascii_quoted_scalar() -> None:
    src = case_source("non_ascii_quoted_scalar")
    _assert_parse_ok("non_ascii_quoted_scalar", src)


def test_flags_object_style_block() -> None:
    src = case_source("flags_object_style_block")
    _assert_parse_ok("flags_object_style_block", src)


def test_players_countries_array_style_block() -> None:
    src = case_source("players_countries_array_style_block")
    _assert_parse_ok("players_countries_array_style_block", src)


def test_array_of_objects_style_block() -> None:
    src = case_source("array_of_objects_style_block")
    _assert_parse_ok("array_of_objects_style_block", src)


def test_comments_anywhere_except_inside_quotes() -> None:
    src = case_source("comments_anywhere_except_inside_quotes")
    _assert_parse_ok("comments_anywhere_except_inside_quotes", src)


def test_empty_block_ambiguous_array_or_object() -> None:
    src = case_source("empty_block_ambiguous_array_or_object")
    _assert_parse_ok("empty_block_ambiguous_array_or_object", src)


def test_many_empty_blocks_with_history_entry() -> None:
    src = case_source("many_empty_blocks_with_history_entry")
    _assert_parse_ok("many_empty_blocks_with_history_entry", src)


def test_hidden_object_array_transition() -> None:
    src = case_source("hidden_object_array_transition")
    _assert_parse_ok("hidden_object_array_transition", src)


def test_non_alphanumeric_scalar_forms() -> None:
    src = case_source("non_alphanumeric_scalar_forms")
    _assert_parse_ok("non_alphanumeric_scalar_forms", src)


def test_interpolated_expression_style_value() -> None:
    src = case_source("interpolated_expression_style_value")
    _assert_parse_ok("interpolated_expression_style_value", src)


def test_large_unsigned_integer_literal() -> None:
    src = case_source("large_unsigned_integer_literal")
    _assert_parse_ok("large_unsigned_integer_literal", src)


def test_quoted_and_unquoted_distinction_is_preserved_lexically() -> None:
    src = case_source("quoted_and_unquoted_distinction_is_preserved_lexically")
    _assert_parse_ok("quoted_and_unquoted_distinction_is_preserved_lexically", src)


def test_non_ascii_unquoted_key() -> None:
    src = case_source("non_ascii_unquoted_key")
    _assert_parse_ok("non_ascii_unquoted_key", src)


def test_empty_string_scalar() -> None:
    src = case_source("empty_string_scalar")
    _assert_parse_ok("empty_string_scalar", src)


def test_externally_tagged_object_array_types() -> None:
    src = case_source("externally_tagged_object_array_types")
    _assert_parse_ok("externally_tagged_object_array_types", src)


def test_deeply_nested_objects() -> None:
    src = case_source("deeply_nested_objects")
    _assert_parse_ok("deeply_nested_objects", src)


def test_save_header_then_data() -> None:
    src = case_source("save_header_then_data")
    _assert_parse_ok("save_header_then_data", src)


def test_semicolon_after_quoted_scalar() -> None:
    src = case_source("semicolon_after_quoted_scalar")
    _assert_parse_fails("semicolon_after_quoted_scalar", src)


def test_semicolon_after_quoted_scalar_is_tolerated_in_permissive_mode() -> None:
    src = case_source("semicolon_after_quoted_scalar")
    parsed = parse_jomini(src, mode=ParseMode.PERMISSIVE)
    assert parsed.root is not None
    assert parsed.diagnostics == []


def test_edge_case_equal_as_key_fails_in_strict_mode() -> None:
    src = case_source("edge_case_equal_as_key_fails_in_strict_mode")
    _assert_parse_fails("edge_case_equal_as_key_fails_in_strict_mode", src)


def test_edge_case_extraneous_closing_brace_fails_in_strict_mode() -> None:
    src = case_source("edge_case_extraneous_closing_brace_fails_in_strict_mode")
    _assert_parse_fails("edge_case_extraneous_closing_brace_fails_in_strict_mode", src)


def test_edge_case_extraneous_closing_brace_is_tolerated_in_permissive_mode() -> None:
    src = case_source("edge_case_extraneous_closing_brace_fails_in_strict_mode")
    parsed = parse_jomini(src, mode=ParseMode.PERMISSIVE)
    assert parsed.root is not None
    assert any(d.code == "PARSER_LEGACY_EXTRA_RBRACE" for d in parsed.diagnostics)


def test_edge_case_missing_closing_brace_fails_in_strict_mode() -> None:
    src = case_source("edge_case_missing_closing_brace_fails_in_strict_mode")
    _assert_parse_fails("edge_case_missing_closing_brace_fails_in_strict_mode", src)


def test_edge_case_missing_closing_brace_is_tolerated_in_permissive_mode() -> None:
    src = case_source("edge_case_missing_closing_brace_fails_in_strict_mode")
    parsed = parse_jomini(src, mode=ParseMode.PERMISSIVE)
    assert parsed.root is not None
    assert any(d.code == "PARSER_LEGACY_MISSING_RBRACE" for d in parsed.diagnostics)


def test_edge_case_parameter_syntax_fails_for_now() -> None:
    src = case_source("edge_case_parameter_syntax_fails_for_now")
    _assert_parse_fails("edge_case_parameter_syntax_fails_for_now", src)


def test_edge_case_parameter_syntax_can_be_enabled() -> None:
    src = case_source("edge_case_parameter_syntax_fails_for_now")
    parsed = parse_jomini(src, options=ParserOptions(allow_parameter_syntax=True))
    assert parsed.diagnostics == []


def test_edge_case_unmarked_list_form_fails_for_now() -> None:
    src = case_source("edge_case_unmarked_list_form_fails_for_now")
    _assert_parse_fails("edge_case_unmarked_list_form_fails_for_now", src)


def test_edge_case_unmarked_list_form_can_be_enabled() -> None:
    src = 'pattern = list "christian_emblems_list"\n'
    parsed = parse_jomini(src, options=ParserOptions(allow_unmarked_list_form=True))
    assert parsed.diagnostics == []


def test_edge_case_alternating_value_and_key_value_is_accepted() -> None:
    src = case_source("edge_case_alternating_value_and_key_value_is_accepted")
    _assert_parse_ok("edge_case_alternating_value_and_key_value_is_accepted", src)


def test_edge_case_stray_definition_line_fails_in_strict_mode() -> None:
    src = case_source("edge_case_stray_definition_line_fails_in_strict_mode")
    _assert_parse_fails("edge_case_stray_definition_line_fails_in_strict_mode", src)


@pytest.mark.parametrize("case", PARSER_CASES, ids=case_id)
def test_parser_runs_all_central_cases(case: JominiCase) -> None:
    parsed = parse_jomini(case.source)
    _debug_print_cst_if_enabled(f"central::{case.name}", case.source, parsed.root)
    debug_dump_diagnostics(f"central::{case.name}", parsed.diagnostics, source=case.source)

    if case.strict_should_parse_cleanly:
        assert parsed.diagnostics == []
    else:
        assert parsed.diagnostics != []


def test_recovery_creates_error_node_and_continues_parsing() -> None:
    src = "a=1 ?=oops\nb=2\n"
    parsed = parse_jomini(src)
    _debug_print_diagnostics_if_enabled("recovery_creates_error_node_and_continues_parsing", parsed.diagnostics)

    kinds = _collect_node_kinds(parsed.root)
    assert parsed.diagnostics != []
    assert JominiSyntaxKind.ERROR in kinds
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 2


def test_parser_checkpoint_rewind_restores_stream_and_events() -> None:
    source = TokenSource(BufferedLexer(Lexer("foo=1")))
    parser = Parser(source)

    checkpoint = parser.checkpoint()
    parser.bump()
    parser.bump()
    parser.rewind(checkpoint)

    assert parser.current == TokenKind.IDENTIFIER
    assert len(parser.events) == 0
    assert parser.diagnostics == []


def test_recovery_is_disabled_during_speculative_parsing() -> None:
    source = TokenSource(BufferedLexer(Lexer("?=oops")))
    parser = Parser(source)
    recovery = ParseRecoveryTokenSet(
        node_kind=JominiSyntaxKind.ERROR,
        recovery_set=frozenset({TokenKind.EOF}),
    )

    with parser.speculative_parsing():
        recovered, error = recovery.recover(parser)

    assert recovered is None
    assert error == RecoveryError.RECOVERY_DISABLED
