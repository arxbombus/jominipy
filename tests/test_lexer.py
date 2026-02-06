import textwrap

from jominipy.parser.lexer import Lexer
from jominipy.parser.tokens import (
    FloatLiteralToken,
    IntLiteralToken,
    OperatorKind,
    OperatorToken,
    StrLiteralToken,
    TokenKind,
    TokenType,
    Trivia,
    TriviaKind,
)


def lex(text: str):
    lexer = Lexer(text)
    return lexer.tokenize()


def expect_operator(tok: TokenType, op_kind: OperatorKind) -> OperatorToken:
    assert isinstance(tok, OperatorToken)
    assert tok.operator == op_kind
    return tok


# 1) Simple campaign_stats block
def test_campaign_stats_minimal_block():
    src = textwrap.dedent(
        """
        campaign_stats={
        {
                id=0
            }
        {
                id=1
            }
        }
        """
    ).lstrip()

    tokens = lex(src)

    # campaign_stats = {
    assert isinstance(tokens[0], StrLiteralToken)
    assert tokens[0].str_value == "campaign_stats"
    assert tokens[0].kind == TokenKind.STRING_LITERAL
    assert not tokens[0].is_quoted

    expect_operator(tokens[1], OperatorKind.EQUALS)

    assert tokens[2].kind == TokenKind.LBRACE

    # then we expect an inner "{ id = 0 }"
    assert tokens[3].kind == TokenKind.LBRACE
    assert isinstance(tokens[4], StrLiteralToken)
    assert tokens[4].str_value == "id"
    expect_operator(tokens[5], OperatorKind.EQUALS)
    assert isinstance(tokens[6], IntLiteralToken)
    assert tokens[6].int_value == 0
    assert tokens[7].kind == TokenKind.RBRACE

    # and then a second "{ id = 1 }"
    assert tokens[8].kind == TokenKind.LBRACE
    assert isinstance(tokens[9], StrLiteralToken)
    assert tokens[9].str_value == "id"
    expect_operator(tokens[10], OperatorKind.EQUALS)
    assert isinstance(tokens[11], IntLiteralToken)
    assert tokens[11].int_value == 1
    assert tokens[12].kind == TokenKind.RBRACE

    # final closing brace
    assert tokens[13].kind == TokenKind.RBRACE


# 2) CK3 meta_data blob
def test_meta_data_core_fields_lex_correctly():
    src = textwrap.dedent(
        """
        meta_data={
            save_game_version=3
            version="1.0.3"
            portraits_version=3
            meta_date=1066.9.15
            meta_player_name="Chieftain Botulf"
            meta_title_name="Chiefdom of Jåhkåmåhkke"
            meta_coat_of_arms={
                pattern="pattern_solid.dds"
                color1=yellow
                color2=black
            }
            meta_number_of_players=1
        }
        my_scripted_effect = {
            GLOBAL = {
                set_global_variable = {
                    name = my_variable
                    value = 1
                }
                GER = {
                    add_prestige = 50
                    some_other_scripted_effect = yes
                }
            }
        }
        """
    ).lstrip()

    tokens = lex(src)

    # meta_data = {
    assert isinstance(tokens[0], StrLiteralToken)
    assert tokens[0].str_value == "meta_data"
    expect_operator(tokens[1], OperatorKind.EQUALS)
    assert tokens[2].kind == TokenKind.LBRACE

    # meta_player_name="Chieftain Botulf"
    idx = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "meta_player_name")
    meta_player_name = tokens[idx]
    assert isinstance(meta_player_name, StrLiteralToken)
    assert not meta_player_name.is_quoted

    expect_operator(tokens[idx + 1], OperatorKind.EQUALS)

    name_tok = tokens[idx + 2]
    assert isinstance(name_tok, StrLiteralToken)
    assert name_tok.is_quoted
    assert name_tok.str_value == "Chieftain Botulf"

    # meta_date=1066.9.15 → FLOAT(1066.9), DOT, INT(15)
    idx_date = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "meta_date")
    expect_operator(tokens[idx_date + 1], OperatorKind.EQUALS)

    float_tok = tokens[idx_date + 2]
    assert isinstance(float_tok, FloatLiteralToken)
    # our lexer should read "1066.9" as one float
    assert float_tok.lexeme == "1066.9"
    assert float_tok.float_value == float("1066.9")

    dot_tok = tokens[idx_date + 3]
    assert dot_tok.kind == TokenKind.DOT
    assert dot_tok.lexeme == "."

    int_tok = tokens[idx_date + 4]
    assert isinstance(int_tok, IntLiteralToken)
    assert int_tok.int_value == 15


# 3) EU4-style CWT save header + campaign_stats
def test_eu4_header_and_campaign_stats():
    src = textwrap.dedent(
        """
        EU4txt
        date=1444.11.11
        save_game=".eu4"
        player="ENG"
        displayed_country_name="England"
        save_game_version={
            first=1
            second=28
            third=3
            forth=0
            name="Spain"
        }
        campaign_stats={
        {
                id=0
                comparison=1
                key="game_country"
                selector="ENG"
                localization="England"
            }
        {
                id=12
                comparison=0
                key="best_leader"
                localization="§GRichard Plantagenet§! ( 2 / 4 / 3 / 0 )"
                value=15.000
            }
        }
        checksum="e6b8bef618f45668d6d0165df3fcd089"
        """
    ).lstrip()

    tokens = lex(src)

    # First token should be EU4txt (bare identifier)
    assert isinstance(tokens[0], StrLiteralToken)
    assert tokens[0].str_value == "EU4txt"
    assert not tokens[0].is_quoted

    # date=1444.11.11 → "date", "=", FLOAT(1444.11), DOT, INT(11)
    idx_date = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "date")
    expect_operator(tokens[idx_date + 1], OperatorKind.EQUALS)

    float_tok = tokens[idx_date + 2]
    assert isinstance(float_tok, FloatLiteralToken)
    assert float_tok.lexeme == "1444.11"
    assert float_tok.float_value == float("1444.11")

    dot_tok = tokens[idx_date + 3]
    assert dot_tok.kind == TokenKind.DOT
    assert dot_tok.lexeme == "."

    int_tok = tokens[idx_date + 4]
    assert isinstance(int_tok, IntLiteralToken)
    assert int_tok.int_value == 11

    # save_game=".eu4"
    idx_save = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "save_game")
    expect_operator(tokens[idx_save + 1], OperatorKind.EQUALS)
    sg_tok = tokens[idx_save + 2]
    assert isinstance(sg_tok, StrLiteralToken)
    assert sg_tok.is_quoted
    assert sg_tok.str_value == ".eu4"

    # One of the campaign_stats entries: id=0 … key="game_country"
    idx_cs = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "campaign_stats")
    expect_operator(tokens[idx_cs + 1], OperatorKind.EQUALS)
    assert tokens[idx_cs + 2].kind == TokenKind.LBRACE

    # Somewhere after that, we should see key="game_country"
    idx_key = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "key")
    expect_operator(tokens[idx_key + 1], OperatorKind.EQUALS)
    key_value_tok = tokens[idx_key + 2]
    assert isinstance(key_value_tok, StrLiteralToken)
    assert key_value_tok.is_quoted
    assert key_value_tok.str_value == "game_country"


# 4) Dense inline numeric/boolean block
def test_dense_inline_numeric_boolean_block():
    src = "868416617618464 = { 11777 4108 { 5632 4187=1089 10={ no true 45056 { 0=true } } 0=1089 } }"

    tokens = lex(src)

    # First token: big int key
    assert isinstance(tokens[0], IntLiteralToken)
    assert tokens[0].int_value == 868416617618464

    # '=' operator
    expect_operator(tokens[1], OperatorKind.EQUALS)

    # '{'
    assert tokens[2].kind == TokenKind.LBRACE

    # 11777, 4108
    assert isinstance(tokens[3], IntLiteralToken)
    assert tokens[3].int_value == 11777
    assert isinstance(tokens[4], IntLiteralToken)
    assert tokens[4].int_value == 4108

    # nested '{'
    assert tokens[5].kind == TokenKind.LBRACE

    # "no" and "true" are unquoted strings
    # Just sanity check they appear somewhere
    str_values = [t.str_value for t in tokens if isinstance(t, StrLiteralToken)]
    assert "no" in str_values
    assert "true" in str_values


# 5) savegame_version block
def test_savegame_version_block():
    src = textwrap.dedent(
        """
        savegame_version={
            first=1
            second=29
            third=5
            forth=0
            name="Manchu"
        }
        """
    ).lstrip()

    tokens = lex(src)

    # savegame_version = {
    assert isinstance(tokens[0], StrLiteralToken)
    assert tokens[0].str_value == "savegame_version"
    expect_operator(tokens[1], OperatorKind.EQUALS)
    assert tokens[2].kind == TokenKind.LBRACE

    # name="Manchu"
    idx_name = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "name")
    expect_operator(tokens[idx_name + 1], OperatorKind.EQUALS)
    name_tok = tokens[idx_name + 2]
    assert isinstance(name_tok, StrLiteralToken)
    assert name_tok.is_quoted
    assert name_tok.str_value == "Manchu"


def test_ck3_style_gene_block_structure():
    src = """
    genes={
        hair_color={ 14 246 14 246 }
        skin_color={ 24 89 24 89 }
        gene_chin_forward={ "chin_forward_pos" 147 "chin_forward_pos" 147 }
        gene_eye_angle={ "eye_angle_pos" 129 "eye_angle_pos" 129 }
    }
    """.lstrip()

    tokens = lex(src)

    # genes = {
    assert isinstance(tokens[0], StrLiteralToken)
    assert tokens[0].str_value == "genes"
    expect_operator(tokens[1], OperatorKind.EQUALS)
    assert tokens[2].kind == TokenKind.LBRACE

    # hair_color={ 14 246 14 246 }
    idx_hair = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "hair_color")
    expect_operator(tokens[idx_hair + 1], OperatorKind.EQUALS)
    assert tokens[idx_hair + 2].kind == TokenKind.LBRACE

    ints = [t.int_value for t in tokens[idx_hair + 3 : idx_hair + 7] if isinstance(t, IntLiteralToken)]
    assert ints == [14, 246, 14, 246]
    assert tokens[idx_hair + 7].kind == TokenKind.RBRACE

    # gene_chin_forward has quoted strings + ints inside a brace
    idx_chin = next(
        i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "gene_chin_forward"
    )
    assert tokens[idx_chin + 2].kind == TokenKind.LBRACE
    inner_tokens = tokens[idx_chin + 3 :]

    # First inner token is quoted "chin_forward_pos"
    inner_str = inner_tokens[0]
    assert isinstance(inner_str, StrLiteralToken)
    assert inner_str.is_quoted
    assert inner_str.str_value == "chin_forward_pos"

    # Followed by an int, another quoted string, and another int
    assert isinstance(inner_tokens[1], IntLiteralToken)
    assert isinstance(inner_tokens[2], StrLiteralToken)
    assert inner_tokens[2].is_quoted
    assert isinstance(inner_tokens[3], IntLiteralToken)


def test_unary_and_binary_plus_minus_operators():
    src = """
    value=-5
    bonus=+3
    sum=1+2
    diff=10-4
    """.lstrip()

    tokens = lex(src)

    def find(name: str) -> int:
        return next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == name)

    # value=-5 -> "value", "=", "-", 5
    idx_val = find("value")
    expect_operator(tokens[idx_val + 1], OperatorKind.EQUALS)

    expect_operator(tokens[idx_val + 2], OperatorKind.MINUS)
    int_tok = tokens[idx_val + 3]
    assert isinstance(int_tok, IntLiteralToken)
    assert int_tok.int_value == 5

    # bonus=+3 -> PLUS as operator, 3 as int
    idx_bonus = find("bonus")
    expect_operator(tokens[idx_bonus + 2], OperatorKind.PLUS)
    plus_int = tokens[idx_bonus + 3]
    assert isinstance(plus_int, IntLiteralToken)
    assert plus_int.int_value == 3

    # sum=1+2 -> INT, PLUS, INT
    idx_sum = find("sum")
    lhs = tokens[idx_sum + 2]
    op = tokens[idx_sum + 3]
    rhs = tokens[idx_sum + 4]
    assert isinstance(lhs, IntLiteralToken)
    assert lhs.int_value == 1
    expect_operator(op, OperatorKind.PLUS)
    assert isinstance(rhs, IntLiteralToken)
    assert rhs.int_value == 2

    # diff=10-4 -> INT, MINUS, INT
    idx_diff = find("diff")
    lhs = tokens[idx_diff + 2]
    op = tokens[idx_diff + 3]
    rhs = tokens[idx_diff + 4]
    assert isinstance(lhs, IntLiteralToken)
    assert lhs.int_value == 10
    expect_operator(op, OperatorKind.MINUS)
    assert isinstance(rhs, IntLiteralToken)
    assert rhs.int_value == 4


def test_multi_char_comparison_operators():
    src = """
    a>=10
    b<=5
    c!=3
    d==4
    e?=7
    """.lstrip()

    tokens = lex(src)

    def pair(name: str):
        idx = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == name)
        return tokens[idx + 1], tokens[idx + 2]

    op_a, rhs_a = pair("a")
    expect_operator(op_a, OperatorKind.GREATER_THAN_OR_EQUAL)
    assert isinstance(rhs_a, IntLiteralToken)
    assert rhs_a.int_value == 10

    op_b, rhs_b = pair("b")
    expect_operator(op_b, OperatorKind.LESS_THAN_OR_EQUAL)
    assert isinstance(rhs_b, IntLiteralToken)
    assert rhs_b.int_value == 5

    op_c, rhs_c = pair("c")
    expect_operator(op_c, OperatorKind.NOT_EQUALS)
    assert isinstance(rhs_c, IntLiteralToken)
    assert rhs_c.int_value == 3

    op_d, rhs_d = pair("d")
    expect_operator(op_d, OperatorKind.EQUAL_EQUAL)
    assert isinstance(rhs_d, IntLiteralToken)
    assert rhs_d.int_value == 4

    op_e, rhs_e = pair("e")
    expect_operator(op_e, OperatorKind.QUESTION_EQUAL)
    assert isinstance(rhs_e, IntLiteralToken)
    assert rhs_e.int_value == 7


def test_newline_trivia_crlf_and_lf():
    src = "a=1\r\nb=2\nc=3\r\nd=4"
    tokens = lex(src)

    # We expect 4 name identifiers: a, b, c, d
    names = [t.str_value for t in tokens if isinstance(t, StrLiteralToken)]
    assert names == ["a", "b", "c", "d"]

    # Check that at least one CRLF newline trivia exists
    newline_trivia: list[Trivia] = []
    for tok in tokens:
        newline_trivia.extend([tr for tr in tok.leading_trivia if tr.kind == TriviaKind.NEWLINE])
        newline_trivia.extend([tr for tr in tok.trailing_trivia if tr.kind == TriviaKind.NEWLINE])
    # We can't guarantee exact distribution, but we should see both "\r\n" and "\n"
    lexemes = {t.lexeme for t in newline_trivia}
    assert "\r\n" in lexemes or "\r\n" in "".join(lexemes)
    assert "\n" in lexemes or "\n" in "".join(lexemes)


def test_comments_are_trivia_not_tokens():
    src = """
    # full line comment
    x=1 # trailing comment
    # another
    y = 2
    """.lstrip()

    tokens = lex(src)

    # Only 2 identifiers: x, y
    names = [t.str_value for t in tokens if isinstance(t, StrLiteralToken)]
    assert names == ["x", "y"]

    # No token should have kind COMMENT (since comments are trivia, not tokens)
    assert all(not isinstance(t, StrLiteralToken) or t.str_value != "#" for t in tokens)

    # Comments should appear in trivia
    comment_trivia: list[Trivia] = []
    for tok in tokens:
        comment_trivia.extend([tr for tr in tok.leading_trivia if tr.kind == TriviaKind.COMMENT])
        comment_trivia.extend([tr for tr in tok.trailing_trivia if tr.kind == TriviaKind.COMMENT])
    assert len(comment_trivia) >= 2
    assert any(tr.lexeme.strip().startswith("#") for tr in comment_trivia)


def test_dotted_identifiers_and_filenames():
    src = """
    file_name="savegame_1444.11.11.eu4"
    scope_name=my_country.tag
    texture="ce_pagan_gironny_03.dds"
    """.lstrip()

    tokens = lex(src)

    # file_name key and quoted value with dots
    idx_file = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "file_name")
    val = tokens[idx_file + 2]
    assert isinstance(val, StrLiteralToken)
    assert val.is_quoted
    assert val.str_value == "savegame_1444.11.11.eu4"

    # scope_name = my_country . tag (depending on your unquoted rules)
    idx_scope = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "scope_name")
    rhs1 = tokens[idx_scope + 2]
    rhs2 = tokens[idx_scope + 3]
    rhs3 = tokens[idx_scope + 4]

    # At minimum we expect: identifier, DOT, identifier
    assert isinstance(rhs1, StrLiteralToken)
    assert rhs2.kind == TokenKind.DOT
    assert isinstance(rhs3, StrLiteralToken)

    # texture with file extension
    idx_tex = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "texture")
    tex_val = tokens[idx_tex + 2]
    assert isinstance(tex_val, StrLiteralToken)
    assert tex_val.is_quoted
    assert tex_val.str_value == "ce_pagan_gironny_03.dds"


def test_numeric_sequence_with_multiple_dots():
    src = "meta_date=1066.9.15"

    tokens = lex(src)

    # meta_date = FLOAT(1066.9), DOT, INT(15)
    assert isinstance(tokens[0], StrLiteralToken)
    assert tokens[0].str_value == "meta_date"

    expect_operator(tokens[1], OperatorKind.EQUALS)

    float_tok = tokens[2]
    dot_tok = tokens[3]
    int_tok = tokens[4]

    assert isinstance(float_tok, FloatLiteralToken)
    assert float_tok.lexeme == "1066.9"
    assert float_tok.float_value == float("1066.9")

    assert dot_tok.kind == TokenKind.DOT
    assert isinstance(int_tok, IntLiteralToken)
    assert int_tok.int_value == 15


def test_complex_quoted_strings_with_formatting():
    src = r"""
    description="§GThis is a green §!description with (parentheses), punctuation, and 1.23 numbers.§!"
    leader_name="§GRichard Plantagenet§! ( 2 / 4 / 3 / 0 )"
    """.lstrip()

    tokens = lex(src)

    idx_desc = next(i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "description")
    desc_val = tokens[idx_desc + 2]
    assert isinstance(desc_val, StrLiteralToken)
    assert desc_val.is_quoted
    assert "§GThis is a green §!description" in desc_val.str_value
    assert "1.23" in desc_val.str_value

    idx_leader = next(
        i for i, t in enumerate(tokens) if isinstance(t, StrLiteralToken) and t.str_value == "leader_name"
    )
    leader_val = tokens[idx_leader + 2]
    assert isinstance(leader_val, StrLiteralToken)
    assert leader_val.is_quoted
    assert "§GRichard Plantagenet§!" in leader_val.str_value
    assert "( 2 / 4 / 3 / 0 )" in leader_val.str_value
