"""Biome-style reusable node-list parse loop helpers."""

from collections.abc import Callable
from dataclasses import dataclass

from jominipy.lexer import TokenKind
from jominipy.parser.parsed_syntax import ParsedSyntax
from jominipy.parser.parser import Parser, ParserProgress
from jominipy.syntax import JominiSyntaxKind


@dataclass(slots=True)
class ParseNodeList:
    """Reusable non-separated list parser with progress and recovery hooks."""

    list_kind: JominiSyntaxKind
    is_at_list_end: Callable[[Parser], bool]
    parse_element: Callable[[Parser], ParsedSyntax]
    recover: Callable[[Parser, ParsedSyntax], bool]

    def parse_list(self, parser: Parser) -> "CompletedMarker":
        marker = parser.start()
        progress = ParserProgress()

        while not parser.at(TokenKind.EOF) and not self.is_at_list_end(parser):
            progress.assert_progressing(parser)
            parsed_element = self.parse_element(parser)
            if not self.recover(parser, parsed_element):
                break

        return marker.complete(parser, self.list_kind)


from jominipy.parser.marker import CompletedMarker
