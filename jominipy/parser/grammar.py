"""Jomini grammar routines that emit CST events."""

from dataclasses import dataclass

from jominipy.diagnostics import Diagnostic
from jominipy.diagnostics.codes import (
    PARSER_EXPECTED_TOKEN,
    PARSER_EXPECTED_VALUE,
    PARSER_LEGACY_EXTRA_RBRACE,
    PARSER_LEGACY_MISSING_RBRACE,
    PARSER_UNEXPECTED_TOKEN,
    PARSER_UNSUPPORTED_PARAMETER_SYNTAX,
    PARSER_UNSUPPORTED_UNMARKED_LIST,
)
from jominipy.lexer import TokenKind
from jominipy.parser.marker import CompletedMarker
from jominipy.parser.parse_lists import ParseNodeList
from jominipy.parser.parse_recovery import ParseRecoveryTokenSet
from jominipy.parser.parsed_syntax import ParsedSyntax
from jominipy.parser.parser import Parser
from jominipy.syntax import JominiSyntaxKind

ASSIGNMENT_OPERATORS: frozenset[TokenKind] = frozenset(
    {
        TokenKind.EQUAL,
        TokenKind.EQUAL_EQUAL,
        TokenKind.NOT_EQUAL,
        TokenKind.LESS_THAN_OR_EQUAL,
        TokenKind.GREATER_THAN_OR_EQUAL,
        TokenKind.LESS_THAN,
        TokenKind.GREATER_THAN,
        TokenKind.QUESTION_EQUAL,
    }
)


@dataclass(frozen=True, slots=True)
class StatementParseResult:
    present: bool
    is_key_value: bool = False


def parse_source_file(parser: Parser) -> None:
    root = parser.start()
    parse_statement_list(
        parser,
        stop_at=frozenset({TokenKind.EOF}),
        allow_bare_scalars=True,
        restrict_bare_scalars_after_key_value=not parser.options.allow_bare_scalar_after_key_value,
    )
    root.complete(parser, JominiSyntaxKind.SOURCE_FILE)


def parse_statement_list(
    parser: Parser,
    stop_at: frozenset[TokenKind],
    *,
    allow_bare_scalars: bool = True,
    restrict_bare_scalars_after_key_value: bool = False,
) -> CompletedMarker:
    has_seen_key_value = False

    recovery_set = set(stop_at)
    if parser.options.allow_semicolon_terminator:
        recovery_set.add(TokenKind.SEMICOLON)

    recovery = ParseRecoveryTokenSet(
        node_kind=JominiSyntaxKind.ERROR,
        recovery_set=frozenset(recovery_set),
    ).enable_recovery_on_line_break()

    def parse_element(current: Parser) -> ParsedSyntax:
        nonlocal has_seen_key_value

        if current.options.allow_semicolon_terminator and current.at(TokenKind.SEMICOLON):
            current.bump()
            return ParsedSyntax.present()

        statement_allow_bare = allow_bare_scalars and (
            not restrict_bare_scalars_after_key_value or not has_seen_key_value
        )
        parsed = parse_statement(current, allow_bare_scalars=statement_allow_bare)

        if parsed.present:
            if parsed.is_key_value:
                has_seen_key_value = True
            return ParsedSyntax.present()

        return ParsedSyntax.absent()

    def recover_element(current: Parser, parsed: ParsedSyntax) -> bool:
        if parsed.is_present():
            return True

        current.error(_unexpected_token(current))
        _, recovery_error = recovery.recover(current)
        return recovery_error is None

    return ParseNodeList(
        list_kind=JominiSyntaxKind.STATEMENT_LIST,
        is_at_list_end=lambda current: current.at_set(stop_at),
        parse_element=parse_element,
        recover=recover_element,
    ).parse_list(parser)


def parse_statement(parser: Parser, *, allow_bare_scalars: bool) -> StatementParseResult:
    if parser.at(TokenKind.RBRACE):
        if parser.options.allow_legacy_extra_rbrace:
            parser.error(_legacy_extra_closing_brace(parser))
            parser.bump()
            return StatementParseResult(present=True)
        return StatementParseResult(present=False)

    if parser.at(TokenKind.LBRACE):
        parse_block(parser)
        return StatementParseResult(present=True)

    key_or_value = parse_scalar(parser)
    if key_or_value is None:
        return StatementParseResult(present=False)

    if parser.at_set(ASSIGNMENT_OPERATORS):
        marker = key_or_value.precede(parser)
        parser.bump()
        if parser.at(TokenKind.EOF) or parser.at(TokenKind.RBRACE):
            parser.error(_expected_value(parser))
        else:
            parse_value(parser)
        marker.complete(parser, JominiSyntaxKind.KEY_VALUE)
        return StatementParseResult(present=True, is_key_value=True)

    if parser.at(TokenKind.LBRACE):
        marker = key_or_value.precede(parser)
        parse_block(parser)
        marker.complete(parser, JominiSyntaxKind.KEY_VALUE)
        return StatementParseResult(present=True, is_key_value=True)

    if allow_bare_scalars:
        scalar_text = key_or_value.text(parser)
        if _is_parameter_syntax_scalar(scalar_text) and not parser.options.allow_parameter_syntax:
            parser.error(_unsupported_parameter_syntax(parser))
        return StatementParseResult(present=True)

    return StatementParseResult(present=False)


def parse_value(parser: Parser) -> bool:
    if parser.at(TokenKind.LBRACE):
        parse_block(parser)
        return True

    scalar = parse_scalar(parser)
    if scalar is None:
        parser.error(_expected_value(parser))
        return False

    if scalar.text(parser) == "list" and parser.at(TokenKind.STRING):
        if not parser.options.allow_unmarked_list_form:
            parser.error(_unsupported_unmarked_list_form(parser))
            return False
        parse_scalar(parser)
        return True

    if parser.at(TokenKind.LBRACE):
        tagged = scalar.precede(parser)
        parse_block(parser)
        tagged.complete(parser, JominiSyntaxKind.TAGGED_BLOCK_VALUE)

    return True


def parse_block(parser: Parser) -> CompletedMarker:
    marker = parser.start()
    if not parser.at(TokenKind.LBRACE):
        parser.error(_expected_token(parser, TokenKind.LBRACE))
        return marker.complete(parser, JominiSyntaxKind.BLOCK)

    parser.bump()
    parse_statement_list(
        parser,
        stop_at=frozenset({TokenKind.RBRACE, TokenKind.EOF}),
        allow_bare_scalars=True,
        restrict_bare_scalars_after_key_value=not parser.options.allow_alternating_value_key_value,
    )

    if parser.at(TokenKind.RBRACE):
        parser.bump()
    elif parser.at(TokenKind.EOF) and parser.options.allow_legacy_missing_rbrace:
        parser.error(_legacy_missing_closing_brace(parser))
    else:
        parser.error(_expected_token(parser, TokenKind.RBRACE))

    return marker.complete(parser, JominiSyntaxKind.BLOCK)


def parse_scalar(parser: Parser) -> CompletedMarker | None:
    if not _can_start_scalar(parser.current):
        return None

    marker = parser.start()
    first_kind = parser.current
    parser.bump()

    if first_kind == TokenKind.STRING:
        return marker.complete(parser, JominiSyntaxKind.SCALAR)

    while _can_start_scalar(parser.current):
        if parser.has_preceding_trivia:
            break
        parser.bump()

    return marker.complete(parser, JominiSyntaxKind.SCALAR)


def _can_start_scalar(kind: TokenKind) -> bool:
    return kind not in {
        TokenKind.EOF,
        TokenKind.LBRACE,
        TokenKind.RBRACE,
        *ASSIGNMENT_OPERATORS,
    }


def _expected_token(parser: Parser, kind: TokenKind) -> Diagnostic:
    return Diagnostic(
        code=PARSER_EXPECTED_TOKEN.code,
        message=f"Expected token {kind.name}",
        range=parser.current_range,
        severity=PARSER_EXPECTED_TOKEN.severity,
        category=PARSER_EXPECTED_TOKEN.category,
    )


def _expected_value(parser: Parser) -> Diagnostic:
    return Diagnostic(
        code=PARSER_EXPECTED_VALUE.code,
        message=PARSER_EXPECTED_VALUE.message,
        range=parser.current_range,
        severity=PARSER_EXPECTED_VALUE.severity,
        category=PARSER_EXPECTED_VALUE.category,
    )


def _unexpected_token(parser: Parser) -> Diagnostic:
    return Diagnostic(
        code=PARSER_UNEXPECTED_TOKEN.code,
        message=f"Unexpected token {parser.current.name}",
        range=parser.current_range,
        severity=PARSER_UNEXPECTED_TOKEN.severity,
        category=PARSER_UNEXPECTED_TOKEN.category,
    )


def _legacy_extra_closing_brace(parser: Parser) -> Diagnostic:
    return Diagnostic(
        code=PARSER_LEGACY_EXTRA_RBRACE.code,
        message=PARSER_LEGACY_EXTRA_RBRACE.message,
        range=parser.current_range,
        severity=PARSER_LEGACY_EXTRA_RBRACE.severity,
        category=PARSER_LEGACY_EXTRA_RBRACE.category,
    )


def _legacy_missing_closing_brace(parser: Parser) -> Diagnostic:
    return Diagnostic(
        code=PARSER_LEGACY_MISSING_RBRACE.code,
        message=PARSER_LEGACY_MISSING_RBRACE.message,
        range=parser.current_range,
        severity=PARSER_LEGACY_MISSING_RBRACE.severity,
        category=PARSER_LEGACY_MISSING_RBRACE.category,
    )


def _unsupported_unmarked_list_form(parser: Parser) -> Diagnostic:
    return Diagnostic(
        code=PARSER_UNSUPPORTED_UNMARKED_LIST.code,
        message=PARSER_UNSUPPORTED_UNMARKED_LIST.message,
        range=parser.current_range,
        severity=PARSER_UNSUPPORTED_UNMARKED_LIST.severity,
        category=PARSER_UNSUPPORTED_UNMARKED_LIST.category,
    )


def _unsupported_parameter_syntax(parser: Parser) -> Diagnostic:
    return Diagnostic(
        code=PARSER_UNSUPPORTED_PARAMETER_SYNTAX.code,
        message=PARSER_UNSUPPORTED_PARAMETER_SYNTAX.message,
        range=parser.current_range,
        severity=PARSER_UNSUPPORTED_PARAMETER_SYNTAX.severity,
        category=PARSER_UNSUPPORTED_PARAMETER_SYNTAX.category,
    )


def _is_parameter_syntax_scalar(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("[[") or (len(stripped) >= 2 and stripped.startswith("$") and stripped.endswith("$"))
