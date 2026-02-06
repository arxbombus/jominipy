"""Lexer tokens."""

from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Final

from jominipy.text import TextRange, TextSize


class TokenKind(IntEnum):
    # -------------------------
    # Special / sentinels
    # -------------------------
    EOF = 1

    # -------------------------
    # Trivia tokens (emitted by the lexer)
    # -------------------------
    WHITESPACE = 10
    NEWLINE = 11
    COMMENT = 12
    SKIPPED = 13  # used by recovery to preserve bytes (still trivia-like)

    # -------------------------
    # Identifiers / literals
    # -------------------------
    IDENTIFIER = 20
    STRING = 21  # quoted string
    INT = 22
    FLOAT = 23

    # -------------------------
    # Operators (multi-char included)
    # -------------------------
    EQUAL = 30  # =
    EQUAL_EQUAL = 31  # ==
    NOT_EQUAL = 32  # !=
    LESS_THAN_OR_EQUAL = 33  # <=
    GREATER_THAN_OR_EQUAL = 34  # >=
    LESS_THAN = 35  # <
    GREATER_THAN = 36  # >
    QUESTION_EQUAL = 37  # ?=

    # -------------------------
    # Punctuation / separators
    # -------------------------
    COLON = 40  # :
    SEMICOLON = 41  # ;
    COMMA = 42  # ,
    DOT = 43  # .
    SLASH = 44  # /
    BACKSLASH = 45  # \
    AT = 46  # @

    PLUS = 50  # +
    MINUS = 51  # -
    STAR = 52  # *
    PERCENT = 53  # %
    CARET = 54  # ^
    PIPE = 55  # |
    AMP = 56  # &
    QUESTION = 57  # ?
    BANG = 58  # !

    LBRACE = 60  # {
    RBRACE = 61  # }
    LBRACKET = 62  # [
    RBRACKET = 63  # ]
    LPAREN = 64  # (
    RPAREN = 65  # )

    @property
    def is_trivia(self) -> bool:
        return self in (
            TokenKind.WHITESPACE,
            TokenKind.NEWLINE,
            TokenKind.COMMENT,
            TokenKind.SKIPPED,
        )


class TriviaKind(IntEnum):
    """The trivia vocabulary (separate from TokenKind for type-safety).

    Conceptually mirrors Biome/Rowan's `TriviaPieceKind`.
    """

    WHITESPACE = 1
    NEWLINE = 2
    COMMENT = 3
    SKIPPED = 4


def trivia_kind_from_token_kind(kind: TokenKind) -> TriviaKind:
    """Map lexer trivia token kinds to TriviaKind.

    Raises if called with a non-trivia TokenKind.
    """
    match kind:
        case TokenKind.NEWLINE:
            return TriviaKind.NEWLINE
        case TokenKind.WHITESPACE:
            return TriviaKind.WHITESPACE
        case TokenKind.COMMENT:
            return TriviaKind.COMMENT
        case TokenKind.SKIPPED:
            return TriviaKind.SKIPPED
        case _:
            raise ValueError(f"Not a trivia token kind: {kind!r}")


class TokenFlags(IntFlag):
    """Token metadata flags."""

    NONE = 0
    PRECEDING_LINE_BREAK = 1 << 0  # NEWLINE before
    WAS_QUOTED = 1 << 1
    HAS_ESCAPE = 1 << 2


@dataclass(frozen=True, slots=True)
class Token:
    """A single lexed token (trivia or non-trivia)."""

    kind: TokenKind
    range: TextRange
    flags: TokenFlags = TokenFlags.NONE

    def has_preceding_line_break(self) -> bool:
        return bool(self.flags & TokenFlags.PRECEDING_LINE_BREAK)


@dataclass(frozen=True, slots=True)
class Trivia:
    """Range-based trivia recorded by the TokenSource.

    Matches Biome's parser-side trivia representation: range + trailing.
    """

    kind: TriviaKind
    range: TextRange
    trailing: bool


@dataclass(frozen=True, slots=True)
class TriviaPiece:
    """Compact trivia unit stored in the CST (kind + length).

    Matches Biome/Rowan's tree-side trivia representation.
    """

    kind: TriviaKind
    length: TextSize


# A small constant that is used everywhere.
EOF_TOKEN: Final[Token] = Token(TokenKind.EOF, TextRange.empty(TextSize.from_int(0)))
