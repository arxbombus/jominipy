"""Buffered lexer Lookahead and checkpoint support."""

from collections import deque
from dataclasses import dataclass
from typing import Iterator

from jominipy.lexer.lexer import Lexer, LexerCheckpoint
from jominipy.lexer.tokens import TokenFlags, TokenKind
from jominipy.text import TextRange, TextSize


@dataclass(frozen=True, slots=True)
class LexContext:
    """Lexing context.

    If not regular, the buffered lexer clears lookahead to avoid stale tokens.
    """

    _is_regular: bool = True

    @property
    def is_regular_context(self) -> bool:
        return self._is_regular


@dataclass(frozen=True, slots=True)
class LookaheadToken:
    kind: TokenKind
    flags: TokenFlags

    def has_preceding_line_break(self) -> bool:
        return bool(self.flags & TokenFlags.PRECEDING_LINE_BREAK)


class Lookahead:
    """Stores checkpoints for all and non-trivia tokens."""

    def __init__(self) -> None:
        self._all: deque[LexerCheckpoint] = deque()
        self._non_trivia: deque[LexerCheckpoint] = deque()

    @property
    def is_empty(self) -> bool:
        return not self._all

    def push_back(self, checkpoint: LexerCheckpoint) -> None:
        if not checkpoint.current_kind.is_trivia:
            self._non_trivia.append(checkpoint)
        self._all.append(checkpoint)

    def pop_front(self) -> LexerCheckpoint | None:
        if not self._all:
            return None
        checkpoint = self._all.popleft()
        if not checkpoint.current_kind.is_trivia:
            if self._non_trivia:
                self._non_trivia.popleft()
        return checkpoint

    def get_checkpoint(self, index: int) -> LexerCheckpoint | None:
        if index < 0 or index >= len(self._all):
            return None
        return self._all[index]

    def get_non_trivia_checkpoint(self, index: int) -> LexerCheckpoint | None:
        if index < 0 or index >= len(self._non_trivia):
            return None
        return self._non_trivia[index]

    def clear(self) -> None:
        self._all.clear()
        self._non_trivia.clear()

    def all_len(self) -> int:
        return len(self._all)

    def non_trivia_len(self) -> int:
        return len(self._non_trivia)


class BufferedLexer:
    """Lexer wrapper for lookahead."""

    def __init__(self, lexer: Lexer) -> None:
        self._inner = lexer
        self._current_checkpoint: LexerCheckpoint | None = None
        self._lookahead = Lookahead()

    def _reset_lookahead(self) -> None:
        if self._current_checkpoint is not None:
            self._inner.rewind(self._current_checkpoint)
            self._lookahead.clear()
            self._current_checkpoint = None

    @property
    def inner(self) -> Lexer:
        return self._inner

    @property
    def current_checkpoint(self) -> LexerCheckpoint | None:
        return self._current_checkpoint

    @current_checkpoint.setter
    def current_checkpoint(self, checkpoint: LexerCheckpoint | None) -> None:
        self._current_checkpoint = checkpoint

    @property
    def lookahead(self) -> Lookahead:
        return self._lookahead

    @lookahead.setter
    def lookahead(self, lookahead: Lookahead) -> None:
        self._lookahead = lookahead

    @property
    def next_token(self, context: LexContext | None = None) -> TokenKind:
        if context is None:
            context = LexContext()

        if not context.is_regular_context:
            self._reset_lookahead()
        elif (next_checkpoint := self.lookahead.pop_front()) is not None:
            kind = next_checkpoint.current_kind
            if self.lookahead.is_empty:
                self.current_checkpoint = None
            else:
                self.current_checkpoint = next_checkpoint
            return kind

        self.current_checkpoint = None
        token = self.inner.next_token
        return token.kind

    @property
    def current(self) -> TokenKind:
        if self.current_checkpoint is not None:
            return self.current_checkpoint.current_kind
        return self.inner.current

    @property
    def current_range(self) -> TextRange:
        if self.current_checkpoint is not None:
            return TextRange.new(
                self.current_checkpoint.current_start, TextSize.from_int(self.current_checkpoint.position)
            )
        return self.inner.current_range

    @property
    def current_flags(self) -> TokenFlags:
        if self.current_checkpoint is not None:
            return self.current_checkpoint.current_flags
        return self.inner.current_flags

    @property
    def has_preceding_line_break(self) -> bool:
        if self.current_checkpoint is not None:
            return bool(self.current_checkpoint.current_flags & TokenFlags.PRECEDING_LINE_BREAK)
        return self.inner.has_preceding_line_break

    @property
    def source(self) -> str:
        return self.inner.source

    @property
    def lookahead_iter(self) -> "LookaheadIterator":
        return LookaheadIterator(self)

    @property
    def checkpoint(self) -> LexerCheckpoint:
        if self.current_checkpoint is not None:
            return self.current_checkpoint
        return self.inner.checkpoint

    def rewind(self, checkpoint: LexerCheckpoint) -> None:
        self.inner.rewind(checkpoint)
        self.lookahead.clear()
        self.current_checkpoint = None

    def nth_non_trivia(self, n: int) -> LookaheadToken | None:
        if n <= 0:
            raise ValueError("n must be >= 1")
        checkpoint = self.lookahead.get_non_trivia_checkpoint(n - 1)
        if checkpoint is not None:
            return LookaheadToken(checkpoint.current_kind, checkpoint.current_flags)

        remaining = n - self.lookahead.non_trivia_len()
        current_length = self.lookahead.all_len()

        for item in self.lookahead_iter.skip(current_length):
            if not item.kind.is_trivia:
                remaining -= 1
                if remaining == 0:
                    return item

        return None

    def finish(self):
        return self.inner.diagnostics


class LookaheadIterator:
    def __init__(self, lexer: BufferedLexer) -> None:
        self._buffered = lexer
        self._nth = 0

    def __iter__(self) -> Iterator[LookaheadToken]:
        return self

    def __next__(self) -> LookaheadToken:
        self._nth += 1

        if (checkpoint := self._buffered.lookahead.get_checkpoint(self._nth - 1)) is not None:
            return LookaheadToken(checkpoint.current_kind, checkpoint.current_flags)

        lexer = self._buffered.inner

        if lexer.current == TokenKind.EOF:
            raise StopIteration

        if self._buffered.current_checkpoint is None:
            self._buffered.current_checkpoint = lexer.checkpoint

        token = lexer.next_token
        self._buffered.lookahead.push_back(lexer.checkpoint)
        return LookaheadToken(token.kind, lexer.current_flags)

    def skip(self, count: int) -> "LookaheadIterator":
        for _ in range(count):
            try:
                next(self)
            except StopIteration:
                break
        return self
