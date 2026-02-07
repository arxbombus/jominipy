"""Event-based parser core."""

from contextlib import contextmanager
from dataclasses import dataclass

from jominipy.diagnostics import Diagnostic
from jominipy.lexer import TokenKind
from jominipy.parser.event import Event, StartEvent, TokenEvent
from jominipy.parser.marker import Marker
from jominipy.parser.options import ParserOptions
from jominipy.parser.parsed_syntax import ParsedSyntax
from jominipy.parser.token_source import TokenSource, TokenSourceCheckpoint
from jominipy.syntax import JominiSyntaxKind
from jominipy.text import TextRange, TextSize


@dataclass(slots=True)
class ParserContext:
    source: TokenSource
    events: list[Event]
    diagnostics: list[Diagnostic]


@dataclass(frozen=True, slots=True)
class ParserCheckpoint:
    source_checkpoint: TokenSourceCheckpoint
    events_len: int
    diagnostics_len: int
    speculative_depth: int


@dataclass(slots=True)
class ParserProgress:
    """Detect parser stalls inside list-style loops."""

    _position: TextSize | None = None

    def has_progressed(self, parser: "Parser") -> bool:
        has_progressed = self._position is None or self._position < parser.position
        self._position = parser.position
        return has_progressed

    def assert_progressing(self, parser: "Parser") -> None:
        if not self.has_progressed(parser):
            raise RuntimeError(f"Parser stopped making progress at {parser.current.name} {parser.current_range}")


class Parser:
    """Event-based parser."""

    def __init__(self, source: TokenSource, options: ParserOptions | None = None) -> None:
        self._source = source
        self._options = options or ParserOptions()
        self._events: list[Event] = []
        self._diagnostics: list[Diagnostic] = []
        self._speculative_depth = 0

    @property
    def source(self) -> TokenSource:
        return self._source

    @property
    def options(self) -> ParserOptions:
        return self._options

    @property
    def events(self) -> list[Event]:
        return self._events

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return self._diagnostics

    @property
    def current(self) -> TokenKind:
        return self._source.current

    @property
    def current_range(self) -> TextRange:
        return self._source.current_range

    @property
    def position(self) -> TextSize:
        return self._source.position

    @property
    def has_preceding_line_break(self) -> bool:
        return self._source.has_preceding_line_break

    @property
    def has_preceding_trivia(self) -> bool:
        return self._source.has_preceding_trivia

    def at(self, kind: TokenKind) -> bool:
        return self.current == kind

    def at_set(self, kinds: frozenset[TokenKind] | set[TokenKind]) -> bool:
        return self.current in kinds

    def nth(self, n: int) -> TokenKind:
        return self._source.nth(n)

    def nth_range(self, n: int) -> TextRange:
        return self._source.nth_range(n)

    def has_nth_preceding_line_break(self, n: int) -> bool:
        return self._source.has_nth_preceding_line_break(n)

    def has_nth_preceding_trivia(self, n: int) -> bool:
        return self._source.has_nth_preceding_trivia(n)

    def start(self) -> Marker:
        pos = len(self._events)
        self._events.append(StartEvent.tombstone())
        return Marker(pos=pos, start=self.position, old_start=pos)

    def checkpoint(self) -> ParserCheckpoint:
        return ParserCheckpoint(
            source_checkpoint=self._source.checkpoint,
            events_len=len(self._events),
            diagnostics_len=len(self._diagnostics),
            speculative_depth=self._speculative_depth,
        )

    def rewind(self, checkpoint: ParserCheckpoint) -> None:
        self._source.rewind(checkpoint.source_checkpoint)
        del self._events[checkpoint.events_len :]
        del self._diagnostics[checkpoint.diagnostics_len :]
        self._speculative_depth = checkpoint.speculative_depth

    @contextmanager
    def speculative_parsing(self):
        self._speculative_depth += 1
        try:
            yield
        finally:
            self._speculative_depth -= 1

    def bump(self) -> None:
        if self.current == TokenKind.EOF:
            return
        self._events.append(
            TokenEvent(
                kind=JominiSyntaxKind.from_token_kind(self.current),
                end=self.current_range.end,
            )
        )
        self._source.bump()

    def bump_any(self) -> None:
        self.bump()

    def eat(self, kind: TokenKind) -> bool:
        if self.current == kind:
            self.bump()
            return True
        return False

    def expect(self, kind: TokenKind, diagnostic: Diagnostic) -> ParsedSyntax:
        if self.eat(kind):
            return ParsedSyntax.present()
        self.error(diagnostic)
        return ParsedSyntax.absent()

    def error(self, diagnostic: Diagnostic) -> None:
        if self._diagnostics:
            previous = self._diagnostics[-1]
            if previous.range.start == diagnostic.range.start:
                return
        self._diagnostics.append(diagnostic)

    def is_speculative_parsing(self) -> bool:
        return self._speculative_depth > 0

    def finish(self) -> tuple[list[Event], list[Diagnostic]]:
        return self._events, self._diagnostics
