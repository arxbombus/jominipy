"""Token source that hides trivia and records it separately."""

from dataclasses import dataclass

from jominipy.diagnostics import Diagnostic
from jominipy.lexer import BufferedLexer, LexContext, LexerCheckpoint
from jominipy.lexer.tokens import (
    TokenFlags,
    TokenKind,
    Trivia,
    TriviaKind,
    trivia_kind_from_token_kind,
)
from jominipy.text import TextRange, TextSize


@dataclass(frozen=True, slots=True)
class TokenSourceCheckpoint:
    lexer_checkpoint: LexerCheckpoint
    trivia_len: int

    @property
    def current_start(self) -> TextSize:
        return self.lexer_checkpoint.current_start

    @property
    def trivia_position(self) -> int:
        return self.trivia_len


class TokenSource:
    """Bridge between lexer and parser that strips trivia but records ownership."""

    def __init__(self, lexer: BufferedLexer) -> None:
        self._lexer = lexer
        self._trivia: list[Trivia] = []
        self._current_kind: TokenKind = TokenKind.EOF
        self._current_range: TextRange = TextRange.empty(TextSize.from_int(0))
        self._preceding_line_break = False
        self._current_has_preceding_trivia = False
        self._next_non_trivia_token(first_token=True)

    @property
    def current(self) -> TokenKind:
        return self._current_kind

    @property
    def current_range(self) -> TextRange:
        return self._current_range

    @property
    def text(self) -> str:
        return self._lexer.source

    @property
    def position(self) -> TextSize:
        return self._current_range.start

    @property
    def has_preceding_line_break(self) -> bool:
        return self._preceding_line_break

    @property
    def trivia(self) -> list[Trivia]:
        return self._trivia

    @property
    def checkpoint(self) -> TokenSourceCheckpoint:
        return TokenSourceCheckpoint(self._lexer.checkpoint, len(self._trivia))

    @property
    def has_preceding_trivia(self) -> bool:
        return self._current_has_preceding_trivia

    def bump(self) -> None:
        if self._current_kind != TokenKind.EOF:
            self._next_non_trivia_token(first_token=False)

    def bump_with_context(self, context: LexContext) -> None:
        if self._current_kind != TokenKind.EOF:
            self._next_non_trivia_token(first_token=False, context=context)

    def skip_as_trivia(self) -> None:
        self._skip_as_trivia(context=None)

    def skip_as_trivia_with_context(self, context: LexContext) -> None:
        self._skip_as_trivia(context=context)

    def _skip_as_trivia(self, context: LexContext | None) -> None:
        if self._current_kind == TokenKind.EOF:
            return
        self._trivia.append(Trivia(TriviaKind.SKIPPED, self._current_range, False))
        self._next_non_trivia_token(first_token=False, context=context)

    def nth(self, n: int) -> TokenKind:
        if n == 0:
            return self._current_kind
        lookahead = self._lexer.nth_non_trivia(n)
        return lookahead.kind if lookahead is not None else TokenKind.EOF

    def nth_range(self, n: int) -> TextRange:
        if n == 0:
            return self._current_range
        lookahead = self._lexer.nth_non_trivia(n)
        if lookahead is not None:
            return lookahead.range
        return TextRange.empty(self._current_range.end)

    def has_nth_preceding_line_break(self, n: int) -> bool:
        if n == 0:
            return self._preceding_line_break
        lookahead = self._lexer.nth_non_trivia(n)
        return lookahead.has_preceding_line_break() if lookahead is not None else False

    def has_nth_preceding_trivia(self, n: int) -> bool:
        if n == 0:
            return self.has_preceding_trivia
        next_range = self.nth_range(n)
        if n == 1:
            prev_range = self._current_range
        else:
            prev_range = self.nth_range(n - 1)
        return next_range.start > prev_range.end

    def rewind(self, checkpoint: TokenSourceCheckpoint) -> None:
        self._lexer.rewind(checkpoint.lexer_checkpoint)
        if len(self._trivia) > checkpoint.trivia_len:
            self._trivia = self._trivia[: checkpoint.trivia_len]

        ck = checkpoint.lexer_checkpoint
        self._current_kind = ck.current_kind
        self._current_range = TextRange.new(ck.current_start, TextSize.from_int(ck.position))
        self._preceding_line_break = bool(ck.current_flags & TokenFlags.PRECEDING_LINE_BREAK)
        self._current_has_preceding_trivia = False

    def finish(self) -> tuple[list[Trivia], list[Diagnostic]]:
        return (self._trivia, self._lexer.finish())

    def _next_non_trivia_token(self, first_token: bool, context: LexContext | None = None) -> None:
        trailing = not first_token
        self._preceding_line_break = False
        saw_trivia = False

        while True:
            kind = self._lexer.next_token(context)
            token_range = self._lexer.current_range

            if kind.is_trivia:
                saw_trivia = True
                trivia_kind = trivia_kind_from_token_kind(kind)
                if trivia_kind == TriviaKind.NEWLINE:
                    trailing = False
                    self._preceding_line_break = True
                self._trivia.append(Trivia(trivia_kind, token_range, trailing))
                continue

            self._current_kind = kind
            self._current_range = token_range
            self._current_has_preceding_trivia = saw_trivia
            if self._lexer.current_flags & TokenFlags.PRECEDING_LINE_BREAK:
                self._preceding_line_break = True
            break
