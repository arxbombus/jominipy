"""Centralized Jomini source cases used across lexer/parser/ast tests."""

from __future__ import annotations

from dataclasses import dataclass
import textwrap
from typing import Literal, cast


@dataclass(frozen=True, slots=True)
class JominiCase:
    name: str
    source: str
    strict_should_parse_cleanly: bool = True


def _dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip()


PARSER_CASES: tuple[JominiCase, ...] = (
    JominiCase(
        name="simple_toml_like_example",
        source=_dedent(
            """
            # this is a comment
            a = 1
            b = "hello" # inline comment
            # comment block start
            # comment block end
            """
        ),
    ),
    JominiCase(name="repeated_key_is_valid", source='a = 1\nb = "hello"\na = 2\n'),
    JominiCase(
        name="common_scalar_examples",
        source=_dedent(
            """
            aaa=foo
            bbb=-1
            ccc=1.000
            ddd=yes
            eee=no
            fff="foo"
            ggg=1821.1.1
            """
        ),
    ),
    JominiCase(name="multiple_pairs_per_line", source="a=1 b=2 c=3\n"),
    JominiCase(
        name="operator_variants",
        source=_dedent(
            """
            intrigue >= high_skill_rating
            age > 16
            count < 2
            scope:attacker.primary_title.tier <= tier_county
            a != b
            start_date == 1066.9.15
            c:RUS ?= this
            """
        ),
    ),
    JominiCase(name="implicit_block_assignment", source="foo{bar=qux}\n"),
    JominiCase(
        name="block_object_and_array_like_content",
        source=_dedent(
            """
            brittany_area = {
                color = { 118 99 151 }
                169 170 171 172 4384
            }
            """
        ),
    ),
    JominiCase(name="dense_boundary_characters", source='a={b="1"c=d}foo=bar#good\n'),
    JominiCase(name="comment_inside_quote_is_not_comment", source='a = "not # a comment"\n'),
    JominiCase(name="multiline_quoted_scalar", source='ooo="hello\n     world"\n'),
    JominiCase(
        name="keys_are_scalars",
        source=_dedent(
            """
            -1=aaa
            "1821.1.1"=bbb
            @my_var="ccc"
            """
        ),
    ),
    JominiCase(
        name="quoted_scalar_escape_variants",
        source=_dedent(
            r"""
            hhh="a\"b"
            iii="\\"
            mmm="\\\""
            nnn="ab <0x15>D ( ID: 691 )<0x15>!"
            """
        ),
    ),
    JominiCase(name="non_ascii_quoted_scalar", source='meta_title_name="Chiefdom of Jåhkåmåhkke"\n'),
    JominiCase(
        name="flags_object_style_block",
        source=_dedent(
            """
            flags={
                schools_initiated=1444.11.11
                mol_polish_march=1444.12.4
            }
            """
        ),
    ),
    JominiCase(
        name="players_countries_array_style_block",
        source=_dedent(
            """
            players_countries={
                "Player"
                "ENG"
            }
            """
        ),
    ),
    JominiCase(
        name="array_of_objects_style_block",
        source=_dedent(
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
        ),
    ),
    JominiCase(
        name="comments_anywhere_except_inside_quotes",
        source=_dedent(
            """
            my_obj = # this is going to be great
            { # my_key = prev_value
                my_key = value # better_value
                a = "not # a comment"
            } # the end
            """
        ),
    ),
    JominiCase(name="empty_block_ambiguous_array_or_object", source="discovered_by={}\n"),
    JominiCase(name="many_empty_blocks_with_history_entry", source="history={{} {} 1629.11.10={core=AAA}}\n"),
    JominiCase(name="hidden_object_array_transition", source="levels={ 10 0=2 1=2 }\n"),
    JominiCase(
        name="non_alphanumeric_scalar_forms",
        source=_dedent(
            """
            flavor_tur.8=yes
            dashed-identifier=yes
            province_id=event_target:agenda_province
            @planet_standard_scale=11
            """
        ),
    ),
    JominiCase(name="interpolated_expression_style_value", source="position_x=@[1-leo_x]\n"),
    JominiCase(name="large_unsigned_integer_literal", source="identity=18446744073709547616\n"),
    JominiCase(
        name="quoted_and_unquoted_distinction_is_preserved_lexically",
        source=_dedent(
            """
            unit_type="western"
            unit_type=western
            """
        ),
    ),
    JominiCase(name="non_ascii_unquoted_key", source="jean_jaurès = { }\n"),
    JominiCase(name="empty_string_scalar", source='name=""\n'),
    JominiCase(
        name="externally_tagged_object_array_types",
        source=_dedent(
            """
            color = rgb { 100 200 150 }
            color = hsv { 0.43 0.86 0.61 }
            color = hsv360{ 25 75 63 }
            color = hex { aabbccdd }
            mild_winter = LIST { 3700 3701 }
            """
        ),
    ),
    JominiCase(name="deeply_nested_objects", source="a={b={c={a={b={c=1}}}}}\n"),
    JominiCase(name="save_header_then_data", source="EU4txt\ndate=1444.12.4\n"),
    JominiCase(
        name="semicolon_after_quoted_scalar",
        source='textureFile3 = "gfx//mapitems//trade_terrain.dds";\n',
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_equal_as_key_fails_in_strict_mode",
        source='=="bar"\n',
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_extraneous_closing_brace_fails_in_strict_mode",
        source="a = { 1 }\n}\nb = 2\n",
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_missing_closing_brace_fails_in_strict_mode",
        source="a = { b=c\n",
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_parameter_syntax_fails_for_now",
        source=_dedent(
            """
            generate_advisor = {
              [[scaled_skill]
                $scaled_skill$
              ]
              [[!skill] if = {} ]
            }
            """
        ),
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_unmarked_list_form_fails_for_now",
        source=_dedent(
            """
            simple_cross_flag = {
              pattern = list "christian_emblems_list"
              color1 = list "normal_colors"
            }
            """
        ),
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_alternating_value_and_key_value_is_accepted",
        source=_dedent(
            """
            on_actions = {
              faith_holy_order_land_acquisition_pulse
              delay = { days = { 5 10 }}
              faith_heresy_events_pulse
              delay = { days = { 15 20 }}
              faith_fervor_events_pulse
            }
            """
        ),
    ),
    JominiCase(
        name="edge_case_stray_definition_line_fails_in_strict_mode",
        source=_dedent(
            """
            pride_of_the_fleet = yes
            definition
            definition = heavy_cruiser
            """
        ),
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_recovery_between_valid_statements",
        source="a=1 ?=oops\nb=2\n",
        strict_should_parse_cleanly=False,
    ),
    JominiCase(
        name="edge_case_missing_value_then_invalid_operator",
        source="a=\n?=oops\nb=2\n",
        strict_should_parse_cleanly=False,
    ),
)

LEXER_CUSTOM_CASES: tuple[JominiCase, ...] = (
    JominiCase(
        name="campaign_stats_minimal_block",
        source=_dedent(
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
        ),
    ),
    JominiCase(
        name="meta_data_core_fields_lex_correctly",
        source=_dedent(
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
            """
        ),
    ),
    JominiCase(
        name="eu4_header_and_campaign_stats",
        source=_dedent(
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
                    modifier={
                        country_revolt_factor = 0.5
                    }
                    modifier = {
                        country_pop_unrest=0.25
                    }
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
        ),
    ),
    JominiCase(
        name="dense_inline_numeric_boolean_block",
        source="868416617618464 = { 11777 4108 { 5632 4187=1089 10={ no true 45056 { 0=true } } 0=1089 } }",
    ),
    JominiCase(
        name="savegame_version_block",
        source=_dedent(
            """
            savegame_version={
                first=1
                second=29
                third=5
                forth=0
                name="Manchu"
            }
            """
        ),
    ),
    JominiCase(
        name="ck3_style_gene_block_structure",
        source=_dedent(
            """
            genes={
                hair_color={ 14 246 14 246 }
                skin_color={ 24 89 24 89 }
                gene_chin_forward={ "chin_forward_pos" 147 "chin_forward_pos" 147 }
                gene_eye_angle={ "eye_angle_pos" 129 "eye_angle_pos" 129 }
            }
            """
        ),
    ),
    JominiCase(
        name="unary_and_binary_plus_minus_operators",
        source=_dedent(
            """
            value=-5
            bonus=+3
            sum=1+2
            diff=10-4
            """
        ),
    ),
    JominiCase(
        name="multi_char_comparison_operators",
        source=_dedent(
            """
            a>=10
            b<=5
            c!=3
            d==4
            e?=7
            """
        ),
    ),
    JominiCase(name="newline_flag_on_next_token", source="a=1\r\nb=2\nc=3\r\nd=4"),
    JominiCase(
        name="comments_are_tokens",
        source=_dedent(
            """
            # full line comment
            x=1 # trailing comment
            # another
            y = 2
            """
        ),
    ),
    JominiCase(
        name="dotted_identifiers_and_filenames",
        source=_dedent(
            """
            file_name="savegame_1444.11.11.eu4"
            scope_name=my_country.tag
            texture="ce_pagan_gironny_03.dds"
            """
        ),
    ),
    JominiCase(name="numeric_sequence_with_multiple_dots", source="meta_date=1066.9.15"),
    JominiCase(
        name="complex_quoted_strings_with_formatting",
        source=_dedent(
            r"""
            description="§GThis is a green §!description with (parentheses), punctuation, and 1.23 numbers.§!"
            leader_name="§GRichard Plantagenet§! ( 2 / 4 / 3 / 0 )"
            """
        ),
    ),
    JominiCase(
        name="dump_tokens_smoke",
        source='a=1\n# comment\nb="hi\\"there\nhello = world # inline comment\n# comment 2 # I wonder what this does\n# multiline\n# comment"',
    ),
)

ALL_JOMINI_CASES: tuple[JominiCase, ...] = PARSER_CASES + LEXER_CUSTOM_CASES

type CaseName = Literal[
    "simple_toml_like_example",
    "repeated_key_is_valid",
    "common_scalar_examples",
    "multiple_pairs_per_line",
    "operator_variants",
    "implicit_block_assignment",
    "block_object_and_array_like_content",
    "dense_boundary_characters",
    "comment_inside_quote_is_not_comment",
    "multiline_quoted_scalar",
    "keys_are_scalars",
    "quoted_scalar_escape_variants",
    "non_ascii_quoted_scalar",
    "flags_object_style_block",
    "players_countries_array_style_block",
    "array_of_objects_style_block",
    "comments_anywhere_except_inside_quotes",
    "empty_block_ambiguous_array_or_object",
    "many_empty_blocks_with_history_entry",
    "hidden_object_array_transition",
    "non_alphanumeric_scalar_forms",
    "interpolated_expression_style_value",
    "large_unsigned_integer_literal",
    "quoted_and_unquoted_distinction_is_preserved_lexically",
    "non_ascii_unquoted_key",
    "empty_string_scalar",
    "externally_tagged_object_array_types",
    "deeply_nested_objects",
    "save_header_then_data",
    "semicolon_after_quoted_scalar",
    "edge_case_equal_as_key_fails_in_strict_mode",
    "edge_case_extraneous_closing_brace_fails_in_strict_mode",
    "edge_case_missing_closing_brace_fails_in_strict_mode",
    "edge_case_parameter_syntax_fails_for_now",
    "edge_case_unmarked_list_form_fails_for_now",
    "edge_case_alternating_value_and_key_value_is_accepted",
    "edge_case_stray_definition_line_fails_in_strict_mode",
    "edge_case_recovery_between_valid_statements",
    "edge_case_missing_value_then_invalid_operator",
    "campaign_stats_minimal_block",
    "meta_data_core_fields_lex_correctly",
    "eu4_header_and_campaign_stats",
    "dense_inline_numeric_boolean_block",
    "savegame_version_block",
    "ck3_style_gene_block_structure",
    "unary_and_binary_plus_minus_operators",
    "multi_char_comparison_operators",
    "newline_flag_on_next_token",
    "comments_are_tokens",
    "dotted_identifiers_and_filenames",
    "numeric_sequence_with_multiple_dots",
    "complex_quoted_strings_with_formatting",
    "dump_tokens_smoke",
]

CASE_BY_NAME: dict[CaseName, JominiCase] = cast(
    dict[CaseName, JominiCase],
    {case.name: case for case in ALL_JOMINI_CASES},
)


def case_source(name: CaseName) -> str:
    return CASE_BY_NAME[name].source


def case_id(case: JominiCase) -> str:
    return case.name
