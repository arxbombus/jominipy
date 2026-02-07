"""Parser infrastructure (token source + event-based parser + tree sink)."""

from jominipy.parser.event import (
    Event,
    FinishEvent,
    StartEvent,
    TokenEvent,
    process_events,
)
from jominipy.parser.grammar import parse_source_file, parse_statement_list
from jominipy.parser.jomini import parse, parse_result
from jominipy.parser.marker import CompletedMarker, Marker
from jominipy.parser.options import ParseMode, ParserOptions
from jominipy.parser.parse import build_lossless_tree
from jominipy.parser.parse_lists import ParseNodeList
from jominipy.parser.parse_recovery import ParseRecoveryTokenSet, RecoveryError
from jominipy.parser.parsed_syntax import ParsedSyntax
from jominipy.parser.parser import Parser, ParserCheckpoint, ParserProgress
from jominipy.parser.token_source import TokenSource, TokenSourceCheckpoint
from jominipy.parser.tree_sink import LosslessTreeSink, ParsedGreenTree

__all__ = [
    "CompletedMarker",
    "Event",
    "FinishEvent",
    "LosslessTreeSink",
    "Marker",
    "ParseMode",
    "ParseNodeList",
    "ParseRecoveryTokenSet",
    "ParsedGreenTree",
    "ParsedSyntax",
    "Parser",
    "ParserCheckpoint",
    "ParserOptions",
    "ParserProgress",
    "RecoveryError",
    "StartEvent",
    "TokenEvent",
    "TokenSource",
    "TokenSourceCheckpoint",
    "build_lossless_tree",
    "parse",
    "parse_result",
    "parse_source_file",
    "parse_statement_list",
    "process_events",
]
