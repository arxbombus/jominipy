"""High-level parse entrypoint for Jomini source text."""

from jominipy.diagnostics import collect_diagnostics
from jominipy.lexer import BufferedLexer, Lexer
from jominipy.parser.grammar import parse_source_file
from jominipy.parser.options import ParseMode, ParserOptions
from jominipy.parser.parse import build_lossless_tree
from jominipy.parser.parser import Parser
from jominipy.parser.token_source import TokenSource
from jominipy.parser.tree_sink import ParsedGreenTree


def parse_jomini(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
) -> ParsedGreenTree:
    if mode is not None and options is not None:
        raise ValueError("Pass either options or mode, not both")

    resolved_options = options or (
        ParserOptions.for_mode(mode) if mode is not None else ParserOptions()
    )

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
