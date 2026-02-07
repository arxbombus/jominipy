"""Unified syntax kinds for parser and CST."""

from enum import IntEnum

from jominipy.lexer import TokenKind


class JominiSyntaxKind(IntEnum):
    """Language syntax vocabulary (tokens + nodes)."""

    TOMBSTONE = 0
    EOF = 1

    # Trivia tokens
    WHITESPACE = 10
    NEWLINE = 11
    COMMENT = 12
    SKIPPED = 13

    # Lexical tokens
    IDENTIFIER = 20
    STRING = 21
    INT = 22
    FLOAT = 23

    EQUAL = 30
    EQUAL_EQUAL = 31
    NOT_EQUAL = 32
    LESS_THAN_OR_EQUAL = 33
    GREATER_THAN_OR_EQUAL = 34
    LESS_THAN = 35
    GREATER_THAN = 36
    QUESTION_EQUAL = 37

    COLON = 40
    SEMICOLON = 41
    COMMA = 42
    DOT = 43
    SLASH = 44
    BACKSLASH = 45
    AT = 46

    PLUS = 50
    MINUS = 51
    STAR = 52
    PERCENT = 53
    CARET = 54
    PIPE = 55
    AMP = 56
    QUESTION = 57
    BANG = 58

    LBRACE = 60
    RBRACE = 61
    LBRACKET = 62
    RBRACKET = 63
    LPAREN = 64
    RPAREN = 65

    # Node kinds
    ROOT = 1000
    ERROR = 1001
    SOURCE_FILE = 1002
    STATEMENT_LIST = 1003
    KEY_VALUE = 1004
    BLOCK = 1005
    SCALAR = 1006
    TAGGED_BLOCK_VALUE = 1007

    @property
    def is_trivia(self) -> bool:
        return self in (
            JominiSyntaxKind.WHITESPACE,
            JominiSyntaxKind.NEWLINE,
            JominiSyntaxKind.COMMENT,
            JominiSyntaxKind.SKIPPED,
        )

    @property
    def is_token(self) -> bool:
        return self != JominiSyntaxKind.TOMBSTONE and self.value < JominiSyntaxKind.ROOT.value

    @property
    def is_node(self) -> bool:
        return self.value >= JominiSyntaxKind.ROOT.value

    @staticmethod
    def from_token_kind(kind: TokenKind) -> "JominiSyntaxKind":
        match kind:
            case TokenKind.EOF:
                return JominiSyntaxKind.EOF
            case TokenKind.WHITESPACE:
                return JominiSyntaxKind.WHITESPACE
            case TokenKind.NEWLINE:
                return JominiSyntaxKind.NEWLINE
            case TokenKind.COMMENT:
                return JominiSyntaxKind.COMMENT
            case TokenKind.SKIPPED:
                return JominiSyntaxKind.SKIPPED
            case TokenKind.IDENTIFIER:
                return JominiSyntaxKind.IDENTIFIER
            case TokenKind.STRING:
                return JominiSyntaxKind.STRING
            case TokenKind.INT:
                return JominiSyntaxKind.INT
            case TokenKind.FLOAT:
                return JominiSyntaxKind.FLOAT
            case TokenKind.EQUAL:
                return JominiSyntaxKind.EQUAL
            case TokenKind.EQUAL_EQUAL:
                return JominiSyntaxKind.EQUAL_EQUAL
            case TokenKind.NOT_EQUAL:
                return JominiSyntaxKind.NOT_EQUAL
            case TokenKind.LESS_THAN_OR_EQUAL:
                return JominiSyntaxKind.LESS_THAN_OR_EQUAL
            case TokenKind.GREATER_THAN_OR_EQUAL:
                return JominiSyntaxKind.GREATER_THAN_OR_EQUAL
            case TokenKind.LESS_THAN:
                return JominiSyntaxKind.LESS_THAN
            case TokenKind.GREATER_THAN:
                return JominiSyntaxKind.GREATER_THAN
            case TokenKind.QUESTION_EQUAL:
                return JominiSyntaxKind.QUESTION_EQUAL
            case TokenKind.COLON:
                return JominiSyntaxKind.COLON
            case TokenKind.SEMICOLON:
                return JominiSyntaxKind.SEMICOLON
            case TokenKind.COMMA:
                return JominiSyntaxKind.COMMA
            case TokenKind.DOT:
                return JominiSyntaxKind.DOT
            case TokenKind.SLASH:
                return JominiSyntaxKind.SLASH
            case TokenKind.BACKSLASH:
                return JominiSyntaxKind.BACKSLASH
            case TokenKind.AT:
                return JominiSyntaxKind.AT
            case TokenKind.PLUS:
                return JominiSyntaxKind.PLUS
            case TokenKind.MINUS:
                return JominiSyntaxKind.MINUS
            case TokenKind.STAR:
                return JominiSyntaxKind.STAR
            case TokenKind.PERCENT:
                return JominiSyntaxKind.PERCENT
            case TokenKind.CARET:
                return JominiSyntaxKind.CARET
            case TokenKind.PIPE:
                return JominiSyntaxKind.PIPE
            case TokenKind.AMP:
                return JominiSyntaxKind.AMP
            case TokenKind.QUESTION:
                return JominiSyntaxKind.QUESTION
            case TokenKind.BANG:
                return JominiSyntaxKind.BANG
            case TokenKind.LBRACE:
                return JominiSyntaxKind.LBRACE
            case TokenKind.RBRACE:
                return JominiSyntaxKind.RBRACE
            case TokenKind.LBRACKET:
                return JominiSyntaxKind.LBRACKET
            case TokenKind.RBRACKET:
                return JominiSyntaxKind.RBRACKET
            case TokenKind.LPAREN:
                return JominiSyntaxKind.LPAREN
            case TokenKind.RPAREN:
                return JominiSyntaxKind.RPAREN
            case _:
                raise ValueError(f"Unsupported TokenKind mapping: {kind!r}")
