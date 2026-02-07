"""Helpers to build a green tree from parser events."""

from jominipy.diagnostics import Diagnostic
from jominipy.lexer import Trivia
from jominipy.parser.event import Event, process_events
from jominipy.parser.tree_sink import LosslessTreeSink, ParsedGreenTree


def build_lossless_tree(
    text: str,
    events: list[Event],
    trivia: list[Trivia],
    diagnostics: list[Diagnostic],
) -> ParsedGreenTree:
    sink = LosslessTreeSink(text=text, trivia=trivia)
    process_events(sink, events, diagnostics)
    return sink.finish()
