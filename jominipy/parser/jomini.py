"""High-level parse entrypoint for Jomini source text."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jominipy.diagnostics import collect_diagnostics
from jominipy.lexer import BufferedLexer, Lexer
from jominipy.parser.grammar import parse_source_file
from jominipy.parser.options import ParseMode, ParserOptions
from jominipy.parser.parse import build_lossless_tree
from jominipy.parser.parser import Parser
from jominipy.parser.token_source import TokenSource
from jominipy.parser.tree_sink import ParsedGreenTree

if TYPE_CHECKING:
    from jominipy.pipeline import JominiParseResult


def _resolve_options(
    options: ParserOptions | None,
    mode: ParseMode | None,
) -> ParserOptions:
    if mode is not None and options is not None:
        raise ValueError("Pass either options or mode, not both")

    if options is not None:
        return options

    if mode is not None:
        return ParserOptions.for_mode(mode)

    return ParserOptions()


def parse(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
) -> ParsedGreenTree:
    resolved_options = _resolve_options(options=options, mode=mode)

    lexer = Lexer(text)
    buffered = BufferedLexer(lexer)
    source = TokenSource(buffered)
    parser = Parser(source, options=resolved_options)

    parse_source_file(parser)
    events, parser_diagnostics = parser.finish()
    trivia, lexer_diagnostics = source.finish()
    diagnostics = collect_diagnostics(lexer_diagnostics, parser_diagnostics)

    return build_lossless_tree(
        text=text,
        events=events,
        trivia=trivia,
        diagnostics=diagnostics,
    )


def parse_result(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
) -> JominiParseResult:
    from jominipy.pipeline import JominiParseResult

    resolved_options = _resolve_options(options=options, mode=mode)
    parsed = parse(text, options=resolved_options)
    return JominiParseResult(
        source_text=text,
        parsed=parsed,
        options=resolved_options,
    )
