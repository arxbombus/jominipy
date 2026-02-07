import os
import textwrap

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

PRINT_CST = os.getenv("PRINT_CST", "0").lower() in {"1", "true", "yes", "on"}
PRINT_DIAGNOSTICS = os.getenv("PRINT_DIAGNOSTICS", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _dump_cst(node: GreenNode) -> str:
    lines: list[str] = []

    def walk_node(current: GreenNode, depth: int) -> None:
        indent = "  " * depth
        lines.append(f"{indent}{current.kind.name}")
        for child in current.children:
            if isinstance(child, GreenNode):
                walk_node(child, depth + 1)
            else:
                walk_token(child, depth + 1)

    def walk_token(token: GreenToken, depth: int) -> None:
        indent = "  " * depth
        text = token.text.replace("\n", "\\n").replace("\r", "\\r")
        lines.append(
            f"{indent}{token.kind.name} text={text!r} "
            f"leading={len(token.leading_trivia)} trailing={len(token.trailing_trivia)}"
        )

    walk_node(node, 0)
    return "\n".join(lines)


def _debug_print_cst_if_enabled(test_name: str, source: str, root: GreenNode) -> None:
    if not PRINT_CST:
        return
    print(f"\n===== {test_name} SOURCE =====")
    print(source)
    print(f"===== {test_name} CST =====")
    print(_dump_cst(root))


def _debug_print_diagnostics_if_enabled(test_name: str, diagnostics: list[Diagnostic]) -> None:
    if not PRINT_DIAGNOSTICS:
        return
    print(f"===== {test_name} DIAGNOSTICS =====")
    if not diagnostics:
        print("(none)")
        return
    for diagnostic in diagnostics:
        print(diagnostic)


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
    src = textwrap.dedent(
        """
        # this is a comment
        a = 1
        b = "hello" # inline comment
        # comment block start
        # comment block end
        """
    ).lstrip()
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
    src = 'a = 1\nb = "hello"\na = 2\n'
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("repeated_key_is_valid", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 3


def test_common_scalar_examples() -> None:
    src = textwrap.dedent(
        """
        aaa=foo
        bbb=-1
        ccc=1.000
        ddd=yes
        eee=no
        fff="foo"
        ggg=1821.1.1
        """
    ).lstrip()
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("common_scalar_examples", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 7


def test_multiple_pairs_per_line() -> None:
    src = "a=1 b=2 c=3\n"
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("multiple_pairs_per_line", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 3


def test_operator_variants() -> None:
    src = textwrap.dedent(
        """
        intrigue >= high_skill_rating
        age > 16
        count < 2
        scope:attacker.primary_title.tier <= tier_county
        a != b
        start_date == 1066.9.15
        c:RUS ?= this
        """
    ).lstrip()
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("operator_variants", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 7


def test_implicit_block_assignment() -> None:
    src = "foo{bar=qux}\n"
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("implicit_block_assignment", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 2
    assert JominiSyntaxKind.BLOCK in kinds


def test_block_object_and_array_like_content() -> None:
    src = textwrap.dedent(
        """
        brittany_area = {
            color = { 118 99 151 }
            169 170 171 172 4384
        }
        """
    ).lstrip()
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("block_object_and_array_like_content", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert JominiSyntaxKind.BLOCK in kinds
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) >= 2


def test_dense_boundary_characters() -> None:
    src = 'a={b="1"c=d}foo=bar#good\n'
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("dense_boundary_characters", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert JominiSyntaxKind.BLOCK in kinds
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 4


def test_comment_inside_quote_is_not_comment() -> None:
    src = 'a = "not # a comment"\n'
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("comment_inside_quote_is_not_comment", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 1


def test_multiline_quoted_scalar() -> None:
    src = 'ooo="hello\n     world"\n'
    parsed = parse_jomini(src)
    _debug_print_cst_if_enabled("multiline_quoted_scalar", src, parsed.root)
    assert parsed.diagnostics == []
    kinds = _collect_node_kinds(parsed.root)
    assert kinds.count(JominiSyntaxKind.KEY_VALUE) == 1


def test_keys_are_scalars() -> None:
    src = textwrap.dedent(
        """
        -1=aaa
        "1821.1.1"=bbb
        @my_var="ccc"
        """
    ).lstrip()
    _assert_parse_ok("keys_are_scalars", src)


def test_quoted_scalar_escape_variants() -> None:
    src = textwrap.dedent(
        r"""
        hhh="a\"b"
        iii="\\"
        mmm="\\\""
        nnn="ab <0x15>D ( ID: 691 )<0x15>!"
        """
    ).lstrip()
    _assert_parse_ok("quoted_scalar_escape_variants", src)


def test_non_ascii_quoted_scalar() -> None:
    src = 'meta_title_name="Chiefdom of Jåhkåmåhkke"\n'
    _assert_parse_ok("non_ascii_quoted_scalar", src)


def test_flags_object_style_block() -> None:
    src = textwrap.dedent(
        """
        flags={
            schools_initiated=1444.11.11
            mol_polish_march=1444.12.4
        }
        """
    ).lstrip()
    _assert_parse_ok("flags_object_style_block", src)


def test_players_countries_array_style_block() -> None:
    src = textwrap.dedent(
        """
        players_countries={
            "Player"
            "ENG"
        }
        """
    ).lstrip()
    _assert_parse_ok("players_countries_array_style_block", src)


def test_array_of_objects_style_block() -> None:
    src = textwrap.dedent(
        """
        campaign_stats={ {
            id=0
            comparison=1
            key="game_country"
            selector="ENG"
            localization="England"
        } {
            id=1
            comparison=2
            key="longest_reign"
            localization="Henry VI"
        } }
        """
    ).lstrip()
    _assert_parse_ok("array_of_objects_style_block", src)


def test_comments_anywhere_except_inside_quotes() -> None:
    src = textwrap.dedent(
        """
        my_obj = # this is going to be great
        { # my_key = prev_value
            my_key = value # better_value
            a = "not # a comment"
        } # the end
        """
    ).lstrip()
    _assert_parse_ok("comments_anywhere_except_inside_quotes", src)


def test_empty_block_ambiguous_array_or_object() -> None:
    src = "discovered_by={}\n"
    _assert_parse_ok("empty_block_ambiguous_array_or_object", src)


def test_many_empty_blocks_with_history_entry() -> None:
    src = "history={{} {} 1629.11.10={core=AAA}}\n"
    _assert_parse_ok("many_empty_blocks_with_history_entry", src)


def test_hidden_object_array_transition() -> None:
    src = "levels={ 10 0=2 1=2 }\n"
    _assert_parse_ok("hidden_object_array_transition", src)


def test_non_alphanumeric_scalar_forms() -> None:
    src = textwrap.dedent(
        """
        flavor_tur.8=yes
        dashed-identifier=yes
        province_id=event_target:agenda_province
        @planet_standard_scale=11
        """
    ).lstrip()
    _assert_parse_ok("non_alphanumeric_scalar_forms", src)


def test_interpolated_expression_style_value() -> None:
    src = "position_x=@[1-leo_x]\n"
    _assert_parse_ok("interpolated_expression_style_value", src)


def test_large_unsigned_integer_literal() -> None:
    src = "identity=18446744073709547616\n"
    _assert_parse_ok("large_unsigned_integer_literal", src)


def test_quoted_and_unquoted_distinction_is_preserved_lexically() -> None:
    src = textwrap.dedent(
        """
        unit_type="western"
        unit_type=western
        """
    ).lstrip()
    _assert_parse_ok("quoted_and_unquoted_distinction_is_preserved_lexically", src)


def test_non_ascii_unquoted_key() -> None:
    src = "jean_jaurès = { }\n"
    _assert_parse_ok("non_ascii_unquoted_key", src)


def test_empty_string_scalar() -> None:
    src = 'name=""\n'
    _assert_parse_ok("empty_string_scalar", src)


def test_externally_tagged_object_array_types() -> None:
    src = textwrap.dedent(
        """
        color = rgb { 100 200 150 }
        color = hsv { 0.43 0.86 0.61 }
        color = hsv360{ 25 75 63 }
        color = hex { aabbccdd }
        mild_winter = LIST { 3700 3701 }
        """
    ).lstrip()
    _assert_parse_ok("externally_tagged_object_array_types", src)


def test_deeply_nested_objects() -> None:
    src = "a={b={c={a={b={c=1}}}}}\n"
    _assert_parse_ok("deeply_nested_objects", src)


def test_save_header_then_data() -> None:
    src = "EU4txt\ndate=1444.12.4\n"
    _assert_parse_ok("save_header_then_data", src)


def test_semicolon_after_quoted_scalar() -> None:
    src = 'textureFile3 = "gfx//mapitems//trade_terrain.dds";\n'
    _assert_parse_fails("semicolon_after_quoted_scalar", src)


def test_semicolon_after_quoted_scalar_is_tolerated_in_permissive_mode() -> None:
    src = 'textureFile3 = "gfx//mapitems//trade_terrain.dds";\n'
    parsed = parse_jomini(src, mode=ParseMode.PERMISSIVE)
    assert parsed.root is not None
    assert parsed.diagnostics == []


def test_edge_case_equal_as_key_fails_in_strict_mode() -> None:
    src = '=="bar"\n'
    _assert_parse_fails("edge_case_equal_as_key_fails_in_strict_mode", src)


def test_edge_case_extraneous_closing_brace_fails_in_strict_mode() -> None:
    src = "a = { 1 }\n}\nb = 2\n"
    _assert_parse_fails("edge_case_extraneous_closing_brace_fails_in_strict_mode", src)


def test_edge_case_extraneous_closing_brace_is_tolerated_in_permissive_mode() -> None:
    src = "a = { 1 }\n}\nb = 2\n"
    parsed = parse_jomini(src, mode=ParseMode.PERMISSIVE)
    assert parsed.root is not None
    assert any(d.code == "PARSER_LEGACY_EXTRA_RBRACE" for d in parsed.diagnostics)


def test_edge_case_missing_closing_brace_fails_in_strict_mode() -> None:
    src = "a = { b=c\n"
    _assert_parse_fails("edge_case_missing_closing_brace_fails_in_strict_mode", src)


def test_edge_case_missing_closing_brace_is_tolerated_in_permissive_mode() -> None:
    src = "a = { b=c\n"
    parsed = parse_jomini(src, mode=ParseMode.PERMISSIVE)
    assert parsed.root is not None
    assert any(d.code == "PARSER_LEGACY_MISSING_RBRACE" for d in parsed.diagnostics)


def test_edge_case_parameter_syntax_fails_for_now() -> None:
    src = textwrap.dedent(
        """
        generate_advisor = {
          [[scaled_skill]
            $scaled_skill$
          ]
          [[!skill] if = {} ]
        }
        """
    ).lstrip()
    _assert_parse_fails("edge_case_parameter_syntax_fails_for_now", src)


def test_edge_case_parameter_syntax_can_be_enabled() -> None:
    src = textwrap.dedent(
        """
        generate_advisor = {
          [[scaled_skill]
            $scaled_skill$
          ]
          [[!skill] if = {} ]
        }
        """
    ).lstrip()
    parsed = parse_jomini(src, options=ParserOptions(allow_parameter_syntax=True))
    assert parsed.diagnostics == []


def test_edge_case_unmarked_list_form_fails_for_now() -> None:
    src = textwrap.dedent(
        """
        simple_cross_flag = {
          pattern = list "christian_emblems_list"
          color1 = list "normal_colors"
        }
        """
    ).lstrip()
    _assert_parse_fails("edge_case_unmarked_list_form_fails_for_now", src)


def test_edge_case_unmarked_list_form_can_be_enabled() -> None:
    src = 'pattern = list "christian_emblems_list"\n'
    parsed = parse_jomini(src, options=ParserOptions(allow_unmarked_list_form=True))
    assert parsed.diagnostics == []


def test_edge_case_alternating_value_and_key_value_is_accepted() -> None:
    src = textwrap.dedent(
        """
        on_actions = {
          faith_holy_order_land_acquisition_pulse
          delay = { days = { 5 10 }}
          faith_heresy_events_pulse
          delay = { days = { 15 20 }}
          faith_fervor_events_pulse
        }
        """
    ).lstrip()
    _assert_parse_ok("edge_case_alternating_value_and_key_value_is_accepted", src)


def test_edge_case_stray_definition_line_fails_in_strict_mode() -> None:
    src = textwrap.dedent(
        """
        pride_of_the_fleet = yes
        definition
        definition = heavy_cruiser
        """
    ).lstrip()
    _assert_parse_fails("edge_case_stray_definition_line_fails_in_strict_mode", src)


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
