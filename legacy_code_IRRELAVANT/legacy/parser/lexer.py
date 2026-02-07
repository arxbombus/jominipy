from __future__ import annotations

from pathlib import Path

from .errors import Diagnostic
from .tokens import Token, TokenKind

IDENTIFIER_EXTRA_CHARS = {"_", ".", "-", ":", "@", "^", "?", "|", "/"}


class Lexer:
    def __init__(self, text: str, *, source: Path | None = None):
        self.text = text
        self._pos = 0
        self._line = 1
        self._column = 1
        self._source = source
        self._tokens: list[Token] = []
        self._diagnostics: list[Diagnostic] = []

    def lex(self) -> tuple[list[Token], list[Diagnostic]]:
        while not self._is_eof:
            char = self._peek()
            if char.isspace():
                self._consume_whitespace()
                continue
            if char == "#":
                self._emit_comment()
                continue
            if char == "{":
                self._emit_simple(TokenKind.LBRACE)
                continue
            if char == "}":
                self._emit_simple(TokenKind.RBRACE)
                continue
            if char == "[":
                self._emit_simple(TokenKind.LBRACKET)
                continue
            if char == "]":
                self._emit_simple(TokenKind.RBRACKET)
                continue
            if char == "<":
                self._emit_simple(TokenKind.LT)
                continue
            if char == ">":
                self._emit_simple(TokenKind.GT)
                continue
            if char == "." and self._peek(1) == ".":
                self._emit_double_dot()
                continue
            if char == "=":
                self._emit_equals()
                continue
            if char in ('"', "'"):
                self._emit_string()
                continue
            if char.isdigit() or (char == "-" and self._peek(1).isdigit()):
                self._emit_number()
                continue
            if char.isalpha() or char in IDENTIFIER_EXTRA_CHARS:
                self._emit_identifier()
                continue
            self._diagnostics.append(
                Diagnostic(f"Unexpected character '{char}'", self._line, self._column, source=self._source)
            )
            self._advance()

        self._tokens.append(Token(TokenKind.EOF, None, self._line, self._column, source=self._source))
        return self._tokens, self._diagnostics

    # Emitters ----------------------------------------------------------------
    def _emit_simple(self, kind: TokenKind) -> None:
        self._tokens.append(Token(kind, self._peek(), self._line, self._column, source=self._source))
        self._advance()

    def _emit_double_dot(self) -> None:
        self._tokens.append(Token(TokenKind.DOT_DOT, "..", self._line, self._column, source=self._source))
        self._advance()
        self._advance()

    def _emit_equals(self) -> None:
        start_col = self._column
        first = self._advance()
        if self._peek() == "=":
            self._tokens.append(Token(TokenKind.DOUBLE_EQUAL, "==", self._line, start_col, source=self._source))
            self._advance()
            return
        self._tokens.append(Token(TokenKind.EQUAL, first, self._line, start_col, source=self._source))

    def _emit_string(self) -> None:
        quote = self._advance()
        start_line, start_col = self._line, self._column - 1
        buffer: list[str] = []
        while not self._is_eof:
            ch = self._peek()
            if ch == quote:
                self._advance()
                value = "".join(buffer)
                self._tokens.append(
                    Token(TokenKind.STRING, value, start_line, start_col, raw=value, source=self._source)
                )
                return
            if ch == "\\":
                self._advance()
                buffer.append(self._peek())
                self._advance()
            else:
                buffer.append(ch)
                self._advance()
        self._diagnostics.append(Diagnostic("Unterminated string literal", start_line, start_col, source=self._source))

    def _emit_number(self) -> None:
        start_line, start_col = self._line, self._column
        buffer = [self._advance()]
        while not self._is_eof and (self._peek().isdigit() or (self._peek() == "." and self._peek(1) != ".")):
            buffer.append(self._advance())
        text = "".join(buffer)
        if text.count(".") == 1:
            try:
                value = float(text)
            except ValueError:
                value = text
        else:
            try:
                value = int(text)
            except ValueError:
                value = text
        self._tokens.append(Token(TokenKind.NUMBER, value, start_line, start_col, raw=text, source=self._source))

    def _emit_identifier(self) -> None:
        start_line, start_col = self._line, self._column
        buffer = [self._advance()]
        while not self._is_eof and (self._peek().isalnum() or self._peek() in IDENTIFIER_EXTRA_CHARS):
            buffer.append(self._advance())
        word = "".join(buffer)
        self._tokens.append(Token(TokenKind.IDENTIFIER, word, start_line, start_col, raw=word, source=self._source))

    def _emit_comment(self) -> None:
        start_line, start_col = self._line, self._column
        buffer: list[str] = [self._advance()]
        while not self._is_eof and self._peek() != "\n":
            buffer.append(self._advance())
        if not self._is_eof and self._peek() == "\n":
            self._advance()
        text = "".join(buffer)
        self._tokens.append(Token(TokenKind.COMMENT, text, start_line, start_col, raw=text, source=self._source))

    # Helpers -----------------------------------------------------------------
    def _consume_whitespace(self) -> None:
        while not self._is_eof and self._peek().isspace():
            self._advance()

    @property
    def _is_eof(self) -> bool:
        return self._pos >= len(self.text)

    def _peek(self, ahead: int = 0) -> str:
        index = self._pos + ahead
        if index >= len(self.text):
            return "\0"
        return self.text[index]

    def _advance(self) -> str:
        ch = self.text[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1
        return ch
