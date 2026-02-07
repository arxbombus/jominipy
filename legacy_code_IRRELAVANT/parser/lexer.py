from pathlib import Path
from typing import Callable, Iterable, overload

from jominipy.parser.tokens import (
    AT,
    CARRIAGE_RETURN,
    COLON,
    CRLF,
    DOT,
    LBRACE,
    LBRACKET,
    LINE_FEED,
    LPAREN,
    NULL_CHAR,
    RBRACE,
    RBRACKET,
    RPAREN,
    FloatLiteralToken,
    IntLiteralToken,
    OperatorKind,
    OperatorToken,
    StrLiteralToken,
    Token,
    TokenKind,
    TokenType,
    Trivia,
    TriviaKind,
    create_token,
    operator_symbols,
)
from jominipy.types import Span


class Lexer:
    def __init__(self, text: str, *, source: Path | None = None) -> None:
        self.text = text
        self._source = source
        self._length = len(text)
        self._index = 0
        self._line = 1
        self._column = 1
        self._tokens: list[TokenType] = []

    @property
    def _is_eof(self) -> bool:
        return self._index >= self._length

    @property
    def _current_char(self) -> str:
        if self._is_eof:
            return NULL_CHAR
        return self.text[self._index]

    def _peek(self, offset: int = 1) -> str:
        idx = self._index + offset
        if idx >= self._length:
            return NULL_CHAR
        return self.text[idx]

    @overload
    def _advance(self) -> None: ...

    @overload
    def _advance(self, *, increment_steps: int, increment_line: int, column: int) -> None: ...

    def _advance(
        self, *, increment_steps: int | None = None, increment_line: int | None = None, column: int | None = None
    ) -> None:
        # Ensure all-or-nothing: either all three are provided or none
        if increment_steps is not None or increment_line is not None or column is not None:
            if increment_steps is None or increment_line is None or column is None:
                raise TypeError("Must provide all of steps, line, and column, or none of them")
            self._index += increment_steps
            self._line += increment_line
            self._column = column
            return
        char = self._current_char
        self._index += 1
        if Trivia.is_newline(char):
            self._line += 1
            self._column = 1
        else:
            self._column += 1

    def _consume_sequence(self, should_continue: Callable[[str, list[str]], bool]) -> tuple[str, int, int]:
        start_idx = self._index
        buffer: list[str] = []
        while not self._is_eof and should_continue(self._current_char, buffer):
            buffer.append(self._current_char)
            self._advance()
        lexeme = "".join(buffer)
        end_idx = self._index
        return lexeme, start_idx, end_idx

    def tokenize(self) -> list[TokenType]:
        tokens: list[TokenType] = []
        while not self._is_eof:
            leading_trivia = self._consume_trivia()
            if self._is_eof:
                break
            if OperatorKind.is_operator_start(self._current_char):
                tokens.append(self._emit_operator(leading_trivia))
            elif self._current_char == COLON:
                tokens.append(self._emit_single_token(TokenKind.COLON, leading_trivia))
            elif self._current_char == AT:
                tokens.append(self._emit_single_token(TokenKind.AT, leading_trivia))
            elif self._current_char == LBRACE:
                tokens.append(self._emit_single_token(TokenKind.LBRACE, leading_trivia))
            elif self._current_char == RBRACE:
                tokens.append(self._emit_single_token(TokenKind.RBRACE, leading_trivia))
            elif self._current_char == LBRACKET:
                tokens.append(self._emit_single_token(TokenKind.LBRACKET, leading_trivia))
            elif self._current_char == RBRACKET:
                tokens.append(self._emit_single_token(TokenKind.RBRACKET, leading_trivia))
            elif self._current_char == LPAREN:
                tokens.append(self._emit_single_token(TokenKind.LPAREN, leading_trivia))
            elif self._current_char == RPAREN:
                tokens.append(self._emit_single_token(TokenKind.RPAREN, leading_trivia))
            elif self._current_char == DOT:
                tokens.append(self._emit_single_token(TokenKind.DOT, leading_trivia))
            elif self._current_char.isdigit():
                tokens.append(self._emit_number(leading_trivia))
            elif self._current_char == '"':
                tokens.append(self._emit_str(leading_trivia, is_quoted=True))
            elif self._current_char.isalpha() or self._current_char == "_":
                tokens.append(self._emit_str(leading_trivia))
            else:
                print(
                    f"Unrecognized character during lexing: {self._current_char!r} at line {self._line}, column {self._column}"
                )  # should use our own error framework in the future instead
                self._advance()
        # create and append EOF token
        eof_token = create_token(
            kind=TokenKind.EOF,
            lexeme=NULL_CHAR,
            span=Span(start=max(self._index, self._length), end=max(self._index, self._length)),
            leading_trivia=tokens[-1].trailing_trivia,
            trailing_trivia=[],
        )
        tokens.append(eof_token)
        self._tokens = tokens
        return tokens

    def _consume_trivia(self) -> list[Trivia]:
        trivias: list[Trivia] = []
        while not self._is_eof:
            if Trivia.is_newline(self._current_char):
                if self._current_char == CARRIAGE_RETURN and self._peek() == LINE_FEED:
                    trivias.append(
                        Trivia(kind=TriviaKind.NEWLINE, lexeme=CRLF, span=Span(start=self._index, end=self._index + 2))
                    )
                    self._advance(increment_steps=2, increment_line=1, column=1)
                elif self._current_char == LINE_FEED:
                    trivias.append(
                        Trivia(
                            kind=TriviaKind.NEWLINE, lexeme=LINE_FEED, span=Span(start=self._index, end=self._index + 1)
                        )
                    )
                    self._advance(increment_steps=1, increment_line=1, column=1)
                else:
                    trivias.append(
                        Trivia(
                            kind=TriviaKind.NEWLINE,
                            lexeme=CARRIAGE_RETURN,
                            span=Span(start=self._index, end=self._index + 1),
                        )
                    )
                    self._advance(increment_steps=1, increment_line=1, column=1)
            elif Trivia.is_whitespace(self._current_char):
                lexeme, start_idx, end_idx = self._consume_sequence(lambda c, _: Trivia.is_whitespace(c))
                trivias.append(
                    Trivia(kind=TriviaKind.WHITESPACE, lexeme=lexeme, span=Span(start=start_idx, end=end_idx))
                )
            elif Trivia.is_comment_start(self._current_char):
                lexeme, start_idx, end_idx = self._consume_sequence(lambda c, _: not Trivia.is_newline(c))
                trivias.append(Trivia(kind=TriviaKind.COMMENT, lexeme=lexeme, span=Span(start=start_idx, end=end_idx)))
            else:
                break
        return trivias

    def _emit_single_token(self, kind: TokenKind, leading_trivia: Iterable[Trivia]) -> Token:
        start_idx = self._index
        self._advance()
        end_idx = self._index
        lexeme = self.text[start_idx:end_idx]
        trailing_trivia = self._consume_trivia()
        return create_token(
            kind=kind,
            lexeme=lexeme,
            span=Span(start=start_idx, end=end_idx),
            leading_trivia=leading_trivia,
            trailing_trivia=trailing_trivia,
        )

    def _emit_operator(self, leading_trivia: Iterable[Trivia]) -> OperatorToken:
        lexeme, start_idx, end_idx = self._consume_sequence(
            lambda c, b: any(symbol.startswith("".join(b) + c) for symbol in operator_symbols.keys())
        )
        if not OperatorKind.is_operator_symbol(lexeme):
            print(f"Unrecognized operator during lexing: {lexeme!r} at line {self._line}, column {self._column}")
        trailing_trivia = self._consume_trivia()
        return create_token(
            kind=TokenKind.OPERATOR,
            lexeme=lexeme,
            span=Span(start=start_idx, end=end_idx),
            operator_kind=OperatorKind.from_symbol(lexeme),
            leading_trivia=leading_trivia,
            trailing_trivia=trailing_trivia,
        )

    def _emit_number(self, leading_trivia: Iterable[Trivia]) -> IntLiteralToken | FloatLiteralToken:
        lexeme, start_idx, end_idx = self._consume_sequence(
            lambda c, b: c.isdigit() or (c == "." and "." not in (b or []))
        )
        is_float = "." in lexeme
        trailing_trivia = self._consume_trivia()
        if is_float:
            float_value = float(lexeme)
            return create_token(
                kind=TokenKind.FLOAT_LITERAL,
                lexeme=lexeme,
                span=Span(start=start_idx, end=end_idx),
                float_value=float_value,
                leading_trivia=leading_trivia,
                trailing_trivia=trailing_trivia,
            )
        else:
            int_value = int(lexeme)
            return create_token(
                kind=TokenKind.INT_LITERAL,
                lexeme=lexeme,
                span=Span(start=start_idx, end=end_idx),
                int_value=int_value,
                leading_trivia=leading_trivia,
                trailing_trivia=trailing_trivia,
            )

    def _emit_str(self, leading_trivia: Iterable[Trivia], is_quoted: bool = False) -> StrLiteralToken:
        if is_quoted:
            start_idx = self._index
            self._advance()
            inner_start = self._index
            while not self._is_eof and self._current_char != '"':
                self._advance()
            inner_end = self._index
            if self._current_char == '"':
                self._advance()
            end_idx = self._index
            lexeme = self.text[start_idx:end_idx]
            str_value = self.text[inner_start:inner_end]
        else:
            start_idx = self._index
            lexeme, _, end_idx = self._consume_sequence(lambda c, _: c.isalnum() or c == "_")
            str_value = lexeme
        trailing_trivia = self._consume_trivia()
        return create_token(
            kind=TokenKind.STRING_LITERAL,
            lexeme=lexeme,
            span=Span(start=start_idx, end=end_idx),
            str_value=str_value,
            is_quoted=is_quoted,
            leading_trivia=leading_trivia,
            trailing_trivia=trailing_trivia,
        )


class TokenStream:
    def __init__(self, tokens: list[TokenType]) -> None:
        pass

    def _ensure_eof(self) -> None: ...

    @property
    def index(self) -> int: ...

    @property
    def is_eof(self) -> bool: ...
