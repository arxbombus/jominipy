import pytest

from jominipy.lexer import Lexer, Token, TokenFlags, TokenKind, token_text
from tests._debug import debug_dump_diagnostics, debug_dump_tokens
from tests._shared_cases import (
    ALL_JOMINI_CASES,
    JominiCase,
    case_id,
    case_source,
)


def lex(text: str) -> list[Token]:
    lexer = Lexer(text)
    return lexer.lex()


# 1) Simple campaign_stats block
def test_campaign_stats_minimal_block():
    src = case_source("campaign_stats_minimal_block")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # campaign_stats = { { id = 0 } { id = 1 } }
    kinds = [t.kind for t in non_trivia]
    assert kinds[:14] == [
        TokenKind.IDENTIFIER,
        TokenKind.EQUAL,
        TokenKind.LBRACE,
        TokenKind.LBRACE,
        TokenKind.IDENTIFIER,
        TokenKind.EQUAL,
        TokenKind.INT,
        TokenKind.RBRACE,
        TokenKind.LBRACE,
        TokenKind.IDENTIFIER,
        TokenKind.EQUAL,
        TokenKind.INT,
        TokenKind.RBRACE,
        TokenKind.RBRACE,
    ]

    # Verify identifier text and int values
    assert token_text(src, non_trivia[0]) == "campaign_stats"
    assert token_text(src, non_trivia[4]) == "id"
    assert token_text(src, non_trivia[6]) == "0"
    assert token_text(src, non_trivia[9]) == "id"
    assert token_text(src, non_trivia[11]) == "1"


# 2) CK3 meta_data blob
def test_meta_data_core_fields_lex_correctly():
    src = case_source("meta_data_core_fields_lex_correctly")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # meta_data = {
    assert non_trivia[0].kind == TokenKind.IDENTIFIER
    assert token_text(src, non_trivia[0]) == "meta_data"
    assert non_trivia[1].kind == TokenKind.EQUAL
    assert non_trivia[2].kind == TokenKind.LBRACE

    # meta_player_name="Chieftain Botulf"
    idx = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "meta_player_name")
    assert non_trivia[idx + 1].kind == TokenKind.EQUAL

    name_tok = non_trivia[idx + 2]
    assert name_tok.kind == TokenKind.STRING
    assert name_tok.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, name_tok) == '"Chieftain Botulf"'

    # meta_date=1066.9.15 → FLOAT(1066.9), DOT, INT(15)
    idx_date = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "meta_date")
    assert non_trivia[idx_date + 1].kind == TokenKind.EQUAL

    float_tok = non_trivia[idx_date + 2]
    dot_tok = non_trivia[idx_date + 3]
    int_tok = non_trivia[idx_date + 4]

    assert float_tok.kind == TokenKind.FLOAT
    assert token_text(src, float_tok) == "1066.9"
    assert dot_tok.kind == TokenKind.DOT
    assert int_tok.kind == TokenKind.INT
    assert token_text(src, int_tok) == "15"


# 3) EU4-style CWT save header + campaign_stats
def test_eu4_header_and_campaign_stats():
    src = case_source("eu4_header_and_campaign_stats")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # First token should be EU4txt (bare identifier)
    assert non_trivia[0].kind == TokenKind.IDENTIFIER
    assert token_text(src, non_trivia[0]) == "EU4txt"

    # date=1444.11.11 → "date", "=", FLOAT(1444.11), DOT, INT(11)
    idx_date = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "date")
    assert non_trivia[idx_date + 1].kind == TokenKind.EQUAL

    float_tok = non_trivia[idx_date + 2]
    dot_tok = non_trivia[idx_date + 3]
    int_tok = non_trivia[idx_date + 4]

    assert float_tok.kind == TokenKind.FLOAT
    assert token_text(src, float_tok) == "1444.11"
    assert dot_tok.kind == TokenKind.DOT
    assert int_tok.kind == TokenKind.INT
    assert token_text(src, int_tok) == "11"

    # save_game=".eu4"
    idx_save = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "save_game")
    assert non_trivia[idx_save + 1].kind == TokenKind.EQUAL
    sg_tok = non_trivia[idx_save + 2]
    assert sg_tok.kind == TokenKind.STRING
    assert sg_tok.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, sg_tok) == '".eu4"'

    # One of the campaign_stats entries: id=0 … key="game_country"
    idx_cs = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "campaign_stats")
    assert non_trivia[idx_cs + 1].kind == TokenKind.EQUAL
    assert non_trivia[idx_cs + 2].kind == TokenKind.LBRACE

    # Somewhere after that, we should see key="game_country"
    idx_key = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "key")
    assert non_trivia[idx_key + 1].kind == TokenKind.EQUAL
    key_value_tok = non_trivia[idx_key + 2]
    assert key_value_tok.kind == TokenKind.STRING
    assert key_value_tok.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, key_value_tok) == '"game_country"'


# 4) Dense inline numeric/boolean block
def test_dense_inline_numeric_boolean_block():
    src = case_source("dense_inline_numeric_boolean_block")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # First token: big int key
    assert non_trivia[0].kind == TokenKind.INT
    assert token_text(src, non_trivia[0]) == "868416617618464"

    # '=' operator
    assert non_trivia[1].kind == TokenKind.EQUAL

    # '{'
    assert non_trivia[2].kind == TokenKind.LBRACE

    # 11777, 4108
    assert non_trivia[3].kind == TokenKind.INT
    assert token_text(src, non_trivia[3]) == "11777"
    assert non_trivia[4].kind == TokenKind.INT
    assert token_text(src, non_trivia[4]) == "4108"

    # nested '{'
    assert non_trivia[5].kind == TokenKind.LBRACE

    # "no" and "true" are identifiers
    texts = [token_text(src, t) for t in non_trivia if t.kind == TokenKind.IDENTIFIER]
    assert "no" in texts
    assert "true" in texts


# 5) savegame_version block
def test_savegame_version_block():
    src = case_source("savegame_version_block")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # savegame_version = {
    assert non_trivia[0].kind == TokenKind.IDENTIFIER
    assert token_text(src, non_trivia[0]) == "savegame_version"
    assert non_trivia[1].kind == TokenKind.EQUAL
    assert non_trivia[2].kind == TokenKind.LBRACE

    # name="Manchu"
    idx_name = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "name")
    assert non_trivia[idx_name + 1].kind == TokenKind.EQUAL
    name_tok = non_trivia[idx_name + 2]
    assert name_tok.kind == TokenKind.STRING
    assert name_tok.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, name_tok) == '"Manchu"'


def test_ck3_style_gene_block_structure():
    src = case_source("ck3_style_gene_block_structure")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # genes = {
    assert non_trivia[0].kind == TokenKind.IDENTIFIER
    assert token_text(src, non_trivia[0]) == "genes"
    assert non_trivia[1].kind == TokenKind.EQUAL
    assert non_trivia[2].kind == TokenKind.LBRACE

    # hair_color={ 14 246 14 246 }
    idx_hair = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "hair_color")
    assert non_trivia[idx_hair + 1].kind == TokenKind.EQUAL
    assert non_trivia[idx_hair + 2].kind == TokenKind.LBRACE

    ints = [token_text(src, t) for t in non_trivia[idx_hair + 3 : idx_hair + 7] if t.kind == TokenKind.INT]
    assert ints == ["14", "246", "14", "246"]
    assert non_trivia[idx_hair + 7].kind == TokenKind.RBRACE

    # gene_chin_forward has quoted strings + ints inside a brace
    idx_chin = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "gene_chin_forward")
    assert non_trivia[idx_chin + 2].kind == TokenKind.LBRACE
    inner = non_trivia[idx_chin + 3 :]

    # First inner token is quoted "chin_forward_pos"
    inner_str = inner[0]
    assert inner_str.kind == TokenKind.STRING
    assert inner_str.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, inner_str) == '"chin_forward_pos"'

    # Followed by an int, another quoted string, and another int
    assert inner[1].kind == TokenKind.INT
    assert inner[2].kind == TokenKind.STRING
    assert inner[2].flags & TokenFlags.WAS_QUOTED
    assert inner[3].kind == TokenKind.INT


def test_unary_and_binary_plus_minus_operators():
    src = case_source("unary_and_binary_plus_minus_operators")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    def find(name: str) -> int:
        return next(
            i for i, t in enumerate(non_trivia) if t.kind == TokenKind.IDENTIFIER and token_text(src, t) == name
        )

    # value=-5 -> "value", "=", "-", 5
    idx_val = find("value")
    assert non_trivia[idx_val + 1].kind == TokenKind.EQUAL
    assert non_trivia[idx_val + 2].kind == TokenKind.MINUS
    assert non_trivia[idx_val + 3].kind == TokenKind.INT
    assert token_text(src, non_trivia[idx_val + 3]) == "5"

    # bonus=+3 -> PLUS as operator, 3 as int
    idx_bonus = find("bonus")
    assert non_trivia[idx_bonus + 2].kind == TokenKind.PLUS
    assert non_trivia[idx_bonus + 3].kind == TokenKind.INT
    assert token_text(src, non_trivia[idx_bonus + 3]) == "3"

    # sum=1+2 -> INT, PLUS, INT
    idx_sum = find("sum")
    assert non_trivia[idx_sum + 2].kind == TokenKind.INT
    assert non_trivia[idx_sum + 3].kind == TokenKind.PLUS
    assert non_trivia[idx_sum + 4].kind == TokenKind.INT

    # diff=10-4 -> INT, MINUS, INT
    idx_diff = find("diff")
    assert non_trivia[idx_diff + 2].kind == TokenKind.INT
    assert non_trivia[idx_diff + 3].kind == TokenKind.MINUS
    assert non_trivia[idx_diff + 4].kind == TokenKind.INT


def test_multi_char_comparison_operators():
    src = case_source("multi_char_comparison_operators")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    def pair(name: str):
        idx = next(i for i, t in enumerate(non_trivia) if t.kind == TokenKind.IDENTIFIER and token_text(src, t) == name)
        return non_trivia[idx + 1], non_trivia[idx + 2]

    op_a, rhs_a = pair("a")
    assert op_a.kind == TokenKind.GREATER_THAN_OR_EQUAL
    assert rhs_a.kind == TokenKind.INT
    assert token_text(src, rhs_a) == "10"

    op_b, rhs_b = pair("b")
    assert op_b.kind == TokenKind.LESS_THAN_OR_EQUAL
    assert rhs_b.kind == TokenKind.INT
    assert token_text(src, rhs_b) == "5"

    op_c, rhs_c = pair("c")
    assert op_c.kind == TokenKind.NOT_EQUAL
    assert rhs_c.kind == TokenKind.INT
    assert token_text(src, rhs_c) == "3"

    op_d, rhs_d = pair("d")
    assert op_d.kind == TokenKind.EQUAL_EQUAL
    assert rhs_d.kind == TokenKind.INT
    assert token_text(src, rhs_d) == "4"

    op_e, rhs_e = pair("e")
    assert op_e.kind == TokenKind.QUESTION_EQUAL
    assert rhs_e.kind == TokenKind.INT
    assert token_text(src, rhs_e) == "7"


def test_newline_flag_on_next_token():
    src = case_source("newline_flag_on_next_token")
    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # We expect 4 name identifiers: a, b, c, d
    names = [token_text(src, t) for t in non_trivia if t.kind == TokenKind.IDENTIFIER]
    assert names == ["a", "b", "c", "d"]

    # Tokens for b, c, d should have the preceding line break flag
    b_tok = next(t for t in non_trivia if token_text(src, t) == "b")
    c_tok = next(t for t in non_trivia if token_text(src, t) == "c")
    d_tok = next(t for t in non_trivia if token_text(src, t) == "d")

    assert b_tok.flags & TokenFlags.PRECEDING_LINE_BREAK
    assert c_tok.flags & TokenFlags.PRECEDING_LINE_BREAK
    assert d_tok.flags & TokenFlags.PRECEDING_LINE_BREAK


def test_comments_are_tokens():
    src = case_source("comments_are_tokens")

    tokens = lex(src)

    # We expect comment tokens
    comment_tokens = [t for t in tokens if t.kind == TokenKind.COMMENT]
    assert len(comment_tokens) >= 2
    assert token_text(src, comment_tokens[0]).strip().startswith("#")


def test_dotted_identifiers_and_filenames():
    src = case_source("dotted_identifiers_and_filenames")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # file_name key and quoted value with dots
    idx_file = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "file_name")
    val = non_trivia[idx_file + 2]
    assert val.kind == TokenKind.STRING
    assert val.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, val) == '"savegame_1444.11.11.eu4"'

    # scope_name = my_country . tag
    idx_scope = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "scope_name")
    rhs1 = non_trivia[idx_scope + 2]
    rhs2 = non_trivia[idx_scope + 3]
    rhs3 = non_trivia[idx_scope + 4]

    assert rhs1.kind == TokenKind.IDENTIFIER
    assert rhs2.kind == TokenKind.DOT
    assert rhs3.kind == TokenKind.IDENTIFIER

    # texture with file extension
    idx_tex = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "texture")
    tex_val = non_trivia[idx_tex + 2]
    assert tex_val.kind == TokenKind.STRING
    assert tex_val.flags & TokenFlags.WAS_QUOTED
    assert token_text(src, tex_val) == '"ce_pagan_gironny_03.dds"'


def test_numeric_sequence_with_multiple_dots():
    src = case_source("numeric_sequence_with_multiple_dots")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    # meta_date = FLOAT(1066.9), DOT, INT(15)
    assert non_trivia[0].kind == TokenKind.IDENTIFIER
    assert token_text(src, non_trivia[0]) == "meta_date"

    assert non_trivia[1].kind == TokenKind.EQUAL

    float_tok = non_trivia[2]
    dot_tok = non_trivia[3]
    int_tok = non_trivia[4]

    assert float_tok.kind == TokenKind.FLOAT
    assert token_text(src, float_tok) == "1066.9"

    assert dot_tok.kind == TokenKind.DOT
    assert int_tok.kind == TokenKind.INT
    assert token_text(src, int_tok) == "15"


def test_complex_quoted_strings_with_formatting():
    src = case_source("complex_quoted_strings_with_formatting")

    tokens = lex(src)
    non_trivia = [t for t in tokens if not t.kind.is_trivia]

    idx_desc = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "description")
    desc_val = non_trivia[idx_desc + 2]
    assert desc_val.kind == TokenKind.STRING
    assert desc_val.flags & TokenFlags.WAS_QUOTED
    assert "§GThis is a green §!description" in token_text(src, desc_val)
    assert "1.23" in token_text(src, desc_val)

    idx_leader = next(i for i, t in enumerate(non_trivia) if token_text(src, t) == "leader_name")
    leader_val = non_trivia[idx_leader + 2]
    assert leader_val.kind == TokenKind.STRING
    assert leader_val.flags & TokenFlags.WAS_QUOTED
    assert "§GRichard Plantagenet§!" in token_text(src, leader_val)
    assert "( 2 / 4 / 3 / 0 )" in token_text(src, leader_val)


def test_dump_tokens_smoke():
    src = case_source("dump_tokens_smoke")
    lexer = Lexer(src)
    tokens = lexer.lex()
    debug_dump_tokens("dump_tokens_smoke", src, tokens)
    debug_dump_diagnostics("dump_tokens_smoke", lexer.diagnostics, source=src)
    assert tokens[-1].kind == TokenKind.EOF


@pytest.mark.parametrize("case", ALL_JOMINI_CASES, ids=case_id)
def test_lexer_runs_all_central_cases(case: JominiCase) -> None:
    lexer = Lexer(case.source)
    tokens = lexer.lex()
    debug_dump_tokens(f"central::{case.name}", case.source, tokens)
    debug_dump_diagnostics(f"central::{case.name}", lexer.diagnostics, source=case.source)

    assert tokens
    assert tokens[-1].kind == TokenKind.EOF
