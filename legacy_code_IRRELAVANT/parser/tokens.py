from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Literal, overload

from jominipy.types import Span

CARRIAGE_RETURN = "\r"
LINE_FEED = "\n"
CRLF = CARRIAGE_RETURN + LINE_FEED
NEWLINE_CHARS = (CARRIAGE_RETURN, LINE_FEED, CRLF)
NULL_CHAR = "\0"
COMMENT_START = "#"
COLON = ":"
AT = "@"
DOT = "."
LBRACE = "{"
RBRACE = "}"
LBRACKET = "["
RBRACKET = "]"
LPAREN = "("
RPAREN = ")"
PERCENTAGE = "%"

OperatorSymbol = Literal["=", ">", "<", ">=", "<=", "!=", "==", "?=", "+", "-"]

operator_symbols = {
    "=": "EQUALS",
    ">": "GREATER_THAN",
    "<": "LESS_THAN",
    ">=": "GREATER_THAN_OR_EQUAL",
    "<=": "LESS_THAN_OR_EQUAL",
    "!=": "NOT_EQUALS",
    "==": "EQUAL_EQUAL",
    "?=": "QUESTION_EQUAL",
    "+": "PLUS",
    "-": "MINUS",
}


class OperatorKind(Enum):
    EQUALS = auto()
    GREATER_THAN = auto()  # >
    LESS_THAN = auto()  # <
    GREATER_THAN_OR_EQUAL = auto()
    LESS_THAN_OR_EQUAL = auto()
    NOT_EQUALS = auto()
    EQUAL_EQUAL = auto()
    QUESTION_EQUAL = auto()
    PLUS = auto()
    MINUS = auto()

    @classmethod
    def is_operator_symbol(cls, symbol: str) -> bool:
        return symbol in operator_symbols

    @classmethod
    def is_operator_start(cls, char: str) -> bool:
        return any(symbol.startswith(char) for symbol in operator_symbols)

    def to_symbol(self) -> OperatorSymbol:
        match self:
            case OperatorKind.EQUALS:
                return "="
            case OperatorKind.GREATER_THAN:
                return ">"
            case OperatorKind.LESS_THAN:
                return "<"
            case OperatorKind.GREATER_THAN_OR_EQUAL:
                return ">="
            case OperatorKind.LESS_THAN_OR_EQUAL:
                return "<="
            case OperatorKind.NOT_EQUALS:
                return "!="
            case OperatorKind.EQUAL_EQUAL:
                return "=="
            case OperatorKind.QUESTION_EQUAL:
                return "?="
            case OperatorKind.PLUS:
                return "+"
            case OperatorKind.MINUS:
                return "-"
            case _:
                raise ValueError(f"Unknown operator: {self}")

    @classmethod
    def from_symbol(cls, symbol: str) -> "OperatorKind":
        match symbol:
            case "=":
                return cls.EQUALS
            case ">":
                return cls.GREATER_THAN
            case "<":
                return cls.LESS_THAN
            case ">=":
                return cls.GREATER_THAN_OR_EQUAL
            case "<=":
                return cls.LESS_THAN_OR_EQUAL
            case "!=":
                return cls.NOT_EQUALS
            case "==":
                return cls.EQUAL_EQUAL
            case "?=":
                return cls.QUESTION_EQUAL
            case "+":
                return cls.PLUS
            case "-":
                return cls.MINUS
            case _:
                raise ValueError(f"Unknown operator symbol: {symbol}")


class TokenKind(Enum):
    STRING_LITERAL = auto()
    INT_LITERAL = auto()
    FLOAT_LITERAL = auto()
    OPERATOR = auto()
    # Don't think there's single quote usage, and we're just going to move double quotes logic to use `is_quoted` flag in `StringLiteralToken`
    # SINGLE_QUOTE = auto()  # not sure if needed, don't think single quotes are used in jomini scripts
    # DOUBLE_QUOTE = auto()  # not sure if needed, but there is a clear distinction between string literals and strings that are quoted. In a lot of places they are interchangeable but in some edge cases they are syntactically different
    COLON = auto()
    AT = auto()  # @ symbol
    DOT = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()


class TriviaKind(Enum):
    WHITESPACE = auto()
    NEWLINE = auto()
    COMMENT = auto()


@dataclass(frozen=True)
class Trivia:
    kind: TriviaKind
    lexeme: str
    span: Span

    @classmethod
    def is_trivia_start(cls, char: str) -> bool:
        return char.isspace() or char == COMMENT_START

    @classmethod
    def is_trivia_end(cls, char: str, in_comment: bool) -> bool:
        if in_comment:
            return char in NEWLINE_CHARS
        return not char.isspace() and char != COMMENT_START

    @classmethod
    def is_newline(cls, char: str) -> bool:
        return char in NEWLINE_CHARS

    @classmethod
    def is_whitespace(cls, char: str) -> bool:
        return char.isspace() and char not in NEWLINE_CHARS

    @classmethod
    def is_comment_start(cls, char: str) -> bool:
        return char == COMMENT_START


@dataclass(frozen=True, kw_only=True)
class Token:
    kind: TokenKind
    lexeme: str
    span: Span
    leading_trivia: tuple[Trivia, ...]
    trailing_trivia: tuple[Trivia, ...]


@dataclass(frozen=True, kw_only=True)
class OperatorToken(Token):
    kind: TokenKind = TokenKind.OPERATOR
    operator: OperatorKind


@dataclass(frozen=True, kw_only=True)
class IntLiteralToken(Token):
    kind: TokenKind = TokenKind.INT_LITERAL
    int_value: int


@dataclass(frozen=True, kw_only=True)
class FloatLiteralToken(Token):
    kind: TokenKind = TokenKind.FLOAT_LITERAL
    float_value: float


@dataclass(frozen=True, kw_only=True)
class StrLiteralToken(Token):
    kind: TokenKind = TokenKind.STRING_LITERAL
    str_value: str
    is_quoted: bool = False


TokenType = Token | OperatorToken | IntLiteralToken | FloatLiteralToken | StrLiteralToken


@overload
def create_token(
    kind: Literal[TokenKind.OPERATOR],
    lexeme: str,
    span: Span,
    *,
    leading_trivia: Iterable[Trivia] | None = None,
    trailing_trivia: Iterable[Trivia] | None = None,
    operator_kind: OperatorKind = ...,
) -> OperatorToken: ...


@overload
def create_token(
    kind: Literal[TokenKind.INT_LITERAL],
    lexeme: str,
    span: Span,
    *,
    leading_trivia: Iterable[Trivia] | None = None,
    trailing_trivia: Iterable[Trivia] | None = None,
    int_value: int = ...,
) -> IntLiteralToken: ...


@overload
def create_token(
    kind: Literal[TokenKind.FLOAT_LITERAL],
    lexeme: str,
    span: Span,
    *,
    leading_trivia: Iterable[Trivia] | None = None,
    trailing_trivia: Iterable[Trivia] | None = None,
    float_value: float = ...,
) -> FloatLiteralToken: ...


@overload
def create_token(
    kind: Literal[TokenKind.STRING_LITERAL],
    lexeme: str,
    span: Span,
    *,
    leading_trivia: Iterable[Trivia] | None = None,
    trailing_trivia: Iterable[Trivia] | None = None,
    str_value: str = ...,
    is_quoted: bool = ...,
) -> StrLiteralToken: ...


@overload
def create_token(
    kind: TokenKind,
    lexeme: str,
    span: Span,
    *,
    leading_trivia: Iterable[Trivia] | None = None,
    trailing_trivia: Iterable[Trivia] | None = None,
) -> Token: ...


def create_token(
    kind: TokenKind,
    lexeme: str,
    span: Span,
    *,
    leading_trivia: Iterable[Trivia] | None = None,
    trailing_trivia: Iterable[Trivia] | None = None,
    operator_kind: OperatorKind | None = None,
    int_value: int | None = None,
    float_value: float | None = None,
    str_value: str | None = None,
    is_quoted: bool = False,
) -> TokenType:
    leading = tuple(leading_trivia or ())
    trailing = tuple(trailing_trivia or ())

    if kind == TokenKind.OPERATOR:
        if operator_kind is None:
            raise ValueError("OperatorToken requires an operator")
        if any(v is not None for v in (int_value, float_value, str_value)):
            raise ValueError("OperatorToken cannot have literal values")
        return OperatorToken(
            lexeme=lexeme,
            span=span,
            leading_trivia=leading,
            trailing_trivia=trailing,
            operator=operator_kind,
        )

    if kind == TokenKind.INT_LITERAL:
        if int_value is None:
            raise ValueError("IntLiteralToken requires an int_value")
        if any(v is not None for v in (operator_kind, float_value, str_value)):
            raise ValueError("IntLiteralToken cannot have operator, float_value, or str_value")
        return IntLiteralToken(
            lexeme=lexeme,
            span=span,
            leading_trivia=leading,
            trailing_trivia=trailing,
            int_value=int_value,
        )

    if kind == TokenKind.FLOAT_LITERAL:
        if float_value is None:
            raise ValueError("FloatLiteralToken requires a float_value")
        if any(v is not None for v in (operator_kind, int_value, str_value)):
            raise ValueError("FloatLiteralToken cannot have operator, int_value, or str_value")
        return FloatLiteralToken(
            lexeme=lexeme,
            span=span,
            leading_trivia=leading,
            trailing_trivia=trailing,
            float_value=float_value,
        )

    if kind == TokenKind.STRING_LITERAL:
        if str_value is None:
            raise ValueError("StringLiteralToken requires a str_value")
        if any(v is not None for v in (operator_kind, int_value, float_value)):
            raise ValueError("StringLiteralToken cannot have operator, int_value, or float_value")
        return StrLiteralToken(
            lexeme=lexeme,
            span=span,
            leading_trivia=leading,
            trailing_trivia=trailing,
            str_value=str_value,
            is_quoted=is_quoted,
        )

    if any(v is not None for v in (operator_kind, int_value, float_value, str_value)):
        raise ValueError(f"{kind} tokens cannot have operator or literal values")

    return Token(
        kind=kind,
        lexeme=lexeme,
        span=span,
        leading_trivia=leading,
        trailing_trivia=trailing,
    )
