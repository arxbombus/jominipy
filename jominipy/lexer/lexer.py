"""Lexer."""

from dataclasses import dataclass

from jominipy.diagnostics import Diagnostic
from jominipy.diagnostics.codes import LEXER_UNTERMINATED_STRING
from jominipy.lexer.tokens import Token, TokenFlags, TokenKind
from jominipy.text import TextRange, TextSize, slice_text_range


@dataclass(frozen=True, slots=True)
class LexerCheckpoint:
    """Lexer checkpoint."""

    position: int
    current_start: TextSize
    current_kind: TokenKind
    current_flags: TokenFlags
    after_newline: bool
    eof_emitted: bool
    diagnostics_position: int


class Lexer:
    """Lossless lexer that emits trivia and non-trivia tokens."""

    def __init__(self, source: str, *, allow_multiline_strings: bool = False) -> None:
        self._source = source
        self._position = 0
        self._after_newline = False
        self._current_start = TextSize.from_int(0)
        self._current_kind = TokenKind.EOF
        self._current_flags = TokenFlags.NONE
        self._eof_emitted = False
        self._allow_multiline_strings = allow_multiline_strings
        self._diagnostics: list[Diagnostic] = []

    @property
    def source(self) -> str:
        """Original source text."""
        return self._source

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """List of diagnostics emitted during lexing."""
        return self._diagnostics

    @property
    def current(self) -> TokenKind:
        return self._current_kind

    @property
    def current_start(self) -> TextSize:
        return self._current_start

    @property
    def current_range(self) -> TextRange:
        return TextRange.new(self._current_start, TextSize.from_int(self._position))

    @property
    def current_flags(self) -> TokenFlags:
        return self._current_flags

    @property
    def position(self) -> int:
        return self._position

    @property
    def is_eof(self) -> bool:
        return self._position >= len(self._source)

    @property
    def next_token(self) -> Token:
        self._current_start = TextSize.from_int(self._position)
        self._current_flags = TokenFlags.NONE

        if self.is_eof:
            if self._eof_emitted:
                return Token(TokenKind.EOF, TextRange.empty(self._current_start), self._current_flags)
            self._eof_emitted = True
            self._current_kind = TokenKind.EOF
            return Token(TokenKind.EOF, TextRange.empty(self._current_start), self._current_flags)

        kind = self._lex_token()
        self._current_flags |= TokenFlags.PRECEDING_LINE_BREAK if self._after_newline else TokenFlags.NONE
        self._current_kind = kind

        if not kind.is_trivia:
            self._after_newline = False

        return Token(kind, self.current_range, self._current_flags)

    @property
    def has_preceding_line_break(self) -> bool:
        return bool(self._current_flags & TokenFlags.PRECEDING_LINE_BREAK)

    @property
    def checkpoint(self) -> LexerCheckpoint:
        return LexerCheckpoint(
            position=self._position,
            current_start=self._current_start,
            current_kind=self._current_kind,
            current_flags=self._current_flags,
            after_newline=self._after_newline,
            eof_emitted=self._eof_emitted,
            diagnostics_position=len(self._diagnostics),
        )

    def rewind(self, checkpoint: LexerCheckpoint) -> None:
        self._position = checkpoint.position
        self._current_start = checkpoint.current_start
        self._current_kind = checkpoint.current_kind
        self._current_flags = checkpoint.current_flags
        self._after_newline = checkpoint.after_newline
        self._eof_emitted = checkpoint.eof_emitted
        if len(self._diagnostics) > checkpoint.diagnostics_position:
            self._diagnostics = self._diagnostics[: checkpoint.diagnostics_position]

    def lex(self) -> list[Token]:

        tokens: list[Token] = []
        while True:
            token = self.next_token
            tokens.append(token)
            if token.kind == TokenKind.EOF:
                break
        return tokens

    def _lex_token(self) -> TokenKind:
        ch = self._current_char()
        if ch == "\0":
            return TokenKind.EOF

        if ch == "\r" or ch == "\n" or ch == "\t" or ch == " ":
            return self._consume_newline_or_whitespaces()

        if ch == "#":
            return self._lex_comment()

        if ch == '"':
            return self._lex_string()

        if ch.isdigit():
            return self._lex_number()

        if ch.isalpha() or ch == "_":
            return self._lex_identifier()

        # Two-character operators
        if ch == "=" and self._peek_char() == "=":
            self._advance(2)
            return TokenKind.EQUAL_EQUAL
        if ch == "!" and self._peek_char() == "=":
            self._advance(2)
            return TokenKind.NOT_EQUAL
        if ch == "<" and self._peek_char() == "=":
            self._advance(2)
            return TokenKind.LESS_THAN_OR_EQUAL
        if ch == ">" and self._peek_char() == "=":
            self._advance(2)
            return TokenKind.GREATER_THAN_OR_EQUAL
        if ch == "?" and self._peek_char() == "=":
            self._advance(2)
            return TokenKind.QUESTION_EQUAL

        # Single-character operators
        if ch == "=":
            self._advance(1)
            return TokenKind.EQUAL
        if ch == "<":
            self._advance(1)
            return TokenKind.LESS_THAN
        if ch == ">":
            self._advance(1)
            return TokenKind.GREATER_THAN
        if ch == "+":
            self._advance(1)
            return TokenKind.PLUS
        if ch == "-":
            self._advance(1)
            return TokenKind.MINUS
        if ch == "*":
            self._advance(1)
            return TokenKind.STAR
        if ch == "%":
            self._advance(1)
            return TokenKind.PERCENT
        if ch == "^":
            self._advance(1)
            return TokenKind.CARET
        if ch == "|":
            self._advance(1)
            return TokenKind.PIPE
        if ch == "&":
            self._advance(1)
            return TokenKind.AMP
        if ch == "?":
            self._advance(1)
            return TokenKind.QUESTION
        if ch == "!":
            self._advance(1)
            return TokenKind.BANG

        # Punctuation
        if ch == ":":
            self._advance(1)
            return TokenKind.COLON
        if ch == ";":
            self._advance(1)
            return TokenKind.SEMICOLON
        if ch == ",":
            self._advance(1)
            return TokenKind.COMMA
        if ch == ".":
            self._advance(1)
            return TokenKind.DOT
        if ch == "/":
            self._advance(1)
            return TokenKind.SLASH
        if ch == "\\":
            self._advance(1)
            return TokenKind.BACKSLASH
        if ch == "@":
            self._advance(1)
            return TokenKind.AT
        if ch == "{":
            self._advance(1)
            return TokenKind.LBRACE
        if ch == "}":
            self._advance(1)
            return TokenKind.RBRACE
        if ch == "[":
            self._advance(1)
            return TokenKind.LBRACKET
        if ch == "]":
            self._advance(1)
            return TokenKind.RBRACKET
        if ch == "(":
            self._advance(1)
            return TokenKind.LPAREN
        if ch == ")":
            self._advance(1)
            return TokenKind.RPAREN

        # Fallback: preserve bytes as SKIPPED for recovery.
        self._advance(1)
        return TokenKind.SKIPPED

    def _lex_comment(self) -> TokenKind:
        # Consume until end of line, do not consume the newline itself.
        self._advance(1)
        while not self.is_eof:
            ch = self._current_char()
            if ch == "\n" or ch == "\r":
                break
            self._advance(1)
        return TokenKind.COMMENT

    def _lex_string(self) -> TokenKind:
        # Consume opening quote
        self._advance(1)
        self._current_flags |= TokenFlags.WAS_QUOTED
        escaped = False
        closed = False

        while not self.is_eof:
            ch = self._current_char()
            if ch == '"':
                self._advance(1)
                closed = True
                break
            if ch == "\\":
                escaped = True
                self._advance(1)
                if not self.is_eof:
                    self._advance(1)
                continue
            if ch == "\n" or ch == "\r":
                if not self._allow_multiline_strings:
                    break
            self._advance(1)

        if escaped:
            self._current_flags |= TokenFlags.HAS_ESCAPE

        if not closed:
            spec = LEXER_UNTERMINATED_STRING
            self._diagnostics.append(
                Diagnostic(
                    code=spec.code,
                    message=spec.message,
                    range=TextRange.new(self._current_start, TextSize.from_int(self._position)),
                    severity=spec.severity,
                    hint=spec.hint,
                    category=spec.category,
                )
            )

        return TokenKind.STRING

    def _lex_number(self) -> TokenKind:
        saw_dot = False
        while not self.is_eof:
            ch = self._current_char()
            if ch.isdigit():
                self._advance(1)
                continue
            if ch == "." and not saw_dot and self._peek_char().isdigit():
                saw_dot = True
                self._advance(1)
                continue
            break
        return TokenKind.FLOAT if saw_dot else TokenKind.INT

    def _lex_identifier(self) -> TokenKind:
        self._advance(1)
        while not self.is_eof:
            ch = self._current_char()
            if ch.isalnum() or ch == "_":
                self._advance(1)
                continue
            break
        return TokenKind.IDENTIFIER

    def _consume_newline_or_whitespaces(self) -> TokenKind:
        if self._consume_newline():
            self._after_newline = True
            return TokenKind.NEWLINE
        self._consume_whitespaces()
        return TokenKind.WHITESPACE

    def _consume_whitespaces(self) -> None:
        while not self.is_eof:
            ch = self._current_char()
            if ch == " " or ch == "\t":
                self._advance(1)
                continue
            break

    def _consume_newline(self) -> bool:
        if self._current_char() == "\n":
            self._advance(1)
            return True
        if self._current_char() == "\r":
            if self._peek_char() == "\n":
                self._advance(2)
            else:
                self._advance(1)
            return True
        return False

    def _current_char(self) -> str:
        if self.is_eof:
            return "\0"
        return self._source[self._position]

    def _peek_char(self, ahead: int = 1) -> str:
        index = self._position + ahead
        if index >= len(self._source):
            return "\0"
        return self._source[index]

    def _advance(self, steps: int) -> None:
        self._position += steps


def token_text(
    source: str,
    token: Token,
    null_char_on_eof: bool = False,
) -> str:
    """Get the text of a token from the source string based on its range."""
    if token.kind == TokenKind.EOF:
        return "\0" if null_char_on_eof else ""
    return slice_text_range(source, token.range)


def dump_tokens(tokens: list[Token], source: str, diagnostics: list[Diagnostic] | None = None) -> None:
    """Print token list with kind, range, flags, and text for debugging."""
    for i, tok in enumerate(tokens):
        text = token_text(source, tok)
        print(f"{i:03d} {tok.kind.name:<18} range={tok.range.as_tuple()} flags={tok.flags} text={text!r}")

    if diagnostics is not None:
        print("\nDiagnostics:")
        for d in diagnostics:
            print(f"- {d.severity.upper()} {d.code} range={d.range.as_tuple()} message={d.message}")
