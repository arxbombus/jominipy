"""Dedicated parser for Paradox localisation files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jominipy.diagnostics import Diagnostic, Severity
from jominipy.diagnostics.codes import (
    LEXER_UNTERMINATED_STRING,
    LOCALISATION_DUPLICATE_KEY,
    LOCALISATION_INVALID_COLUMN,
    LOCALISATION_INVALID_ENTRY,
    LOCALISATION_INVALID_VALUE_QUOTES,
    LOCALISATION_MISSING_HEADER,
    LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE,
)
from jominipy.lexer import Lexer
from jominipy.lexer.tokens import (
    Token,
    TokenKind,
    TriviaKind,
    trivia_kind_from_token_kind,
)
from jominipy.localisation.model import (
    LocalisationEntry,
    LocalisationParseResult,
    LocalisationTrivia,
)
from jominipy.localisation.profile import (
    PERMISSIVE_PROFILE,
    LocalisationProfile,
)
from jominipy.text import TextRange, TextSize


@dataclass(frozen=True, slots=True)
class _LineInfo:
    number: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _EntryPrefix:
    key: str
    key_start: int
    key_end: int
    key_column: int
    version_text: str | None
    version_start: int
    version_end: int
    value_start: int


def parse_localisation_text(
    source_text: str,
    *,
    source_path: str = "<memory>",
    profile: LocalisationProfile = PERMISSIVE_PROFILE,
    had_bom: bool = False,
) -> LocalisationParseResult:
    """Parse one localisation file using a single full-file lexer pass."""
    lexer = Lexer(source_text, allow_multiline_strings=False)
    all_tokens = lexer.lex()

    diagnostics: list[Diagnostic] = []
    entries: list[LocalisationEntry] = []
    trivia: list[LocalisationTrivia] = _collect_trivia(source_text, all_tokens)

    header_key: str | None = None
    locale: str | None = None
    saw_header = False
    entry_column: int | None = None

    seen_entries_by_key: dict[str, LocalisationEntry] = {}

    lines = _split_lines(source_text)
    tokens_by_line = _group_tokens_by_line(all_tokens, lines)

    for line, line_tokens in zip(lines, tokens_by_line, strict=True):
        line_text = source_text[line.start : line.end]
        stripped = line_text.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue

        if not saw_header:
            parsed_header = _parse_header_key(line_text, line.start, line_tokens)
            if parsed_header is None:
                diagnostics.append(
                    _diagnostic(
                        code=LOCALISATION_MISSING_HEADER.code,
                        message=LOCALISATION_MISSING_HEADER.message,
                        start=line.start,
                        end=line.end,
                        hint=LOCALISATION_MISSING_HEADER.hint,
                        category=LOCALISATION_MISSING_HEADER.category,
                        severity=LOCALISATION_MISSING_HEADER.severity,
                    )
                )
                saw_header = True
                continue
            header_key = parsed_header
            if not profile.is_supported_header_key(parsed_header):
                diagnostics.append(
                    _diagnostic(
                        code=LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE.code,
                        message=(
                            f"{LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE.message} "
                            f"`{parsed_header}` is not valid for profile `{profile.name}`."
                        ),
                        start=line.start,
                        end=line.end,
                        hint=LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE.hint,
                        category=LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE.category,
                        severity=LOCALISATION_UNSUPPORTED_HEADER_LANGUAGE.severity,
                    )
                )
            locale = parsed_header.removeprefix("l_")
            saw_header = True
            continue

        parsed_entry = _parse_entry_prefix(
            source_text,
            line,
            line_tokens,
        )
        if parsed_entry is None:
            diagnostics.append(
                _diagnostic(
                    code=LOCALISATION_INVALID_ENTRY.code,
                    message=LOCALISATION_INVALID_ENTRY.message,
                    start=line.start,
                    end=line.end,
                    hint=LOCALISATION_INVALID_ENTRY.hint,
                    category=LOCALISATION_INVALID_ENTRY.category,
                    severity=LOCALISATION_INVALID_ENTRY.severity,
                )
            )
            continue

        if entry_column is None:
            entry_column = parsed_entry.key_column
        elif parsed_entry.key_column != entry_column:
            diagnostics.append(
                _diagnostic(
                    code=LOCALISATION_INVALID_COLUMN.code,
                    message=LOCALISATION_INVALID_COLUMN.message,
                    start=line.start,
                    end=line.end,
                    hint=(f"{LOCALISATION_INVALID_COLUMN.hint} Expected column {entry_column + 1}."),
                    category=LOCALISATION_INVALID_COLUMN.category,
                    severity=LOCALISATION_INVALID_COLUMN.severity,
                )
            )
            continue

        raw_value = source_text[parsed_entry.value_start : line.end]
        parsed_value = _extract_quoted_value_parts(raw_value)
        if parsed_value is None:
            first_non_ws = raw_value.lstrip()[:1]
            code_spec = LEXER_UNTERMINATED_STRING if first_non_ws in {'"', "'"} else LOCALISATION_INVALID_VALUE_QUOTES
            diagnostics.append(
                _diagnostic(
                    code=code_spec.code,
                    message=code_spec.message,
                    start=parsed_entry.value_start,
                    end=line.end,
                    hint=code_spec.hint,
                    category=code_spec.category,
                    severity=code_spec.severity,
                )
            )
            continue

        leading_trivia, quoted_raw_value, value_text, trailing_trivia, quoted_start, quoted_end = parsed_value

        entry = LocalisationEntry(
            source_path=source_path,
            locale=locale or "",
            key=parsed_entry.key,
            version=(int(parsed_entry.version_text) if parsed_entry.version_text is not None else None),
            leading_trivia=leading_trivia,
            raw_value=quoted_raw_value,
            trailing_trivia=trailing_trivia,
            value_text=value_text,
            key_range=TextRange.new(
                TextSize.from_int(parsed_entry.key_start),
                TextSize.from_int(parsed_entry.key_end),
            ),
            version_range=TextRange.new(
                TextSize.from_int(parsed_entry.version_start),
                TextSize.from_int(parsed_entry.version_end),
            ),
            value_range=TextRange.new(
                TextSize.from_int(parsed_entry.value_start + quoted_start),
                TextSize.from_int(parsed_entry.value_start + quoted_end),
            ),
            line=line.number,
        )

        existing = seen_entries_by_key.get(parsed_entry.key)
        if existing is not None:
            diagnostics.append(
                _diagnostic(
                    code=LOCALISATION_DUPLICATE_KEY.code,
                    message=(
                        f"{LOCALISATION_DUPLICATE_KEY.message} "
                        f"`{parsed_entry.key}` already declared on line {existing.line}."
                    ),
                    start=parsed_entry.key_start,
                    end=parsed_entry.key_end,
                    hint=LOCALISATION_DUPLICATE_KEY.hint,
                    category=LOCALISATION_DUPLICATE_KEY.category,
                    severity=LOCALISATION_DUPLICATE_KEY.severity,
                )
            )

        entries.append(entry)
        seen_entries_by_key[parsed_entry.key] = entry

    if not saw_header:
        diagnostics.append(
            _diagnostic(
                code=LOCALISATION_MISSING_HEADER.code,
                message=LOCALISATION_MISSING_HEADER.message,
                start=0,
                end=min(len(source_text), 1),
                hint=LOCALISATION_MISSING_HEADER.hint,
                category=LOCALISATION_MISSING_HEADER.category,
                severity=LOCALISATION_MISSING_HEADER.severity,
            )
        )

    return LocalisationParseResult(
        source_path=source_path,
        source_text=source_text,
        had_bom=had_bom,
        header_key=header_key,
        locale=locale,
        entries=tuple(entries),
        trivia=tuple(trivia),
        diagnostics=tuple(diagnostics),
    )


def parse_localisation_file(
    path: str | Path,
    *,
    profile: LocalisationProfile = PERMISSIVE_PROFILE,
) -> LocalisationParseResult:
    """Parse one localisation file from disk."""
    file_path = Path(path)
    decoded = file_path.read_bytes().decode("utf-8")
    had_bom = decoded.startswith("\ufeff")
    text = decoded[1:] if had_bom else decoded
    return parse_localisation_text(
        text,
        source_path=str(file_path).replace("\\", "/"),
        profile=profile,
        had_bom=had_bom,
    )


def _split_lines(source_text: str) -> list[_LineInfo]:
    lines: list[_LineInfo] = []
    offset = 0
    for number, line_with_break in enumerate(source_text.splitlines(keepends=True), start=1):
        line = line_with_break.rstrip("\r\n")
        line_len = len(line)
        lines.append(_LineInfo(number=number, start=offset, end=offset + line_len))
        offset += len(line_with_break)
    return lines


def _group_tokens_by_line(tokens: list[Token], lines: list[_LineInfo]) -> list[list[Token]]:
    groups: list[list[Token]] = []
    token_index = 0

    for line in lines:
        line_tokens: list[Token] = []
        while token_index < len(tokens):
            token = tokens[token_index]
            if token.kind == TokenKind.EOF:
                break
            token_start = token.range.start.value
            if token_start < line.start:
                token_index += 1
                continue
            if token_start >= line.end:
                break
            if token.kind != TokenKind.NEWLINE:
                line_tokens.append(token)
            token_index += 1
        groups.append(line_tokens)

    return groups


def _collect_trivia(source_text: str, tokens: list[Token]) -> list[LocalisationTrivia]:
    trivia: list[LocalisationTrivia] = []
    for token in tokens:
        if token.kind == TokenKind.EOF:
            continue
        if not token.kind.is_trivia:
            continue
        kind: TriviaKind = trivia_kind_from_token_kind(token.kind)
        start = token.range.start.value
        end = token.range.end.value
        trivia.append(
            LocalisationTrivia(
                kind=kind,
                text=source_text[start:end],
                range=token.range,
            )
        )
    return trivia


def _parse_header_key(line_text: str, line_start: int, tokens: list[Token]) -> str | None:
    significant = [token for token in tokens if token.kind not in {TokenKind.WHITESPACE, TokenKind.COMMENT}]
    if len(significant) < 2:
        return None

    key_token = significant[0]
    colon_token = significant[1]

    if key_token.kind != TokenKind.IDENTIFIER:
        return None
    if colon_token.kind != TokenKind.COLON:
        return None
    if colon_token.range.start.value != key_token.range.end.value:
        return None
    if len(significant) != 2:
        return None

    header_key = line_text[key_token.range.start.value - line_start : key_token.range.end.value - line_start]
    if not header_key.startswith("l_"):
        return None
    return header_key


def _parse_entry_prefix(
    source_text: str,
    line: _LineInfo,
    tokens: list[Token],
) -> _EntryPrefix | None:
    significant = [token for token in tokens if token.kind not in {TokenKind.WHITESPACE, TokenKind.COMMENT}]
    if not significant:
        return None

    cursor = 0
    head = significant[cursor]
    if head.kind not in {TokenKind.IDENTIFIER, TokenKind.INT}:
        return None

    key_start = head.range.start.value
    key_end = head.range.end.value
    cursor += 1

    while cursor + 1 < len(significant):
        dot = significant[cursor]
        part = significant[cursor + 1]

        if dot.kind != TokenKind.DOT:
            break
        if part.kind not in {TokenKind.IDENTIFIER, TokenKind.INT}:
            break
        if dot.range.start.value != key_end:
            break
        if dot.range.end.value != part.range.start.value:
            break

        key_end = part.range.end.value
        cursor += 2

    key = source_text[key_start:key_end]
    if not key:
        return None

    version_text: str | None = None
    version_start = key_end
    version_end = key_end

    if cursor < len(significant) and significant[cursor].kind == TokenKind.COLON:
        colon = significant[cursor]
        if colon.range.start.value != key_end:
            return None
        cursor += 1

        if cursor < len(significant) and significant[cursor].kind == TokenKind.INT:
            version = significant[cursor]
            # Space before version is invalid: key: 0 "..."
            if version.range.start.value != colon.range.end.value:
                return None
            version_text = source_text[version.range.start.value : version.range.end.value]
            version_start = version.range.start.value
            version_end = version.range.end.value
            cursor += 1
            value_start = _skip_inline_whitespace(
                source_text,
                start=version_end,
                end=line.end,
            )
        else:
            value_start = _skip_inline_whitespace(
                source_text,
                start=colon.range.end.value,
                end=line.end,
            )
    else:
        if key_end >= line.end:
            return None
        if source_text[key_end] not in {" ", "\t"}:
            return None
        value_start = _skip_inline_whitespace(
            source_text,
            start=key_end,
            end=line.end,
        )

    if value_start >= line.end:
        return None

    # There must not be any non-whitespace, non-comment tokens before value start.
    for token in significant[cursor:]:
        if token.range.start.value < value_start:
            return None

    return _EntryPrefix(
        key=key,
        key_start=key_start,
        key_end=key_end,
        key_column=key_start - line.start,
        version_text=version_text,
        version_start=version_start,
        version_end=version_end,
        value_start=value_start,
    )


def _extract_quoted_value_parts(raw_value: str) -> tuple[str, str, str, str, int, int] | None:
    leading = len(raw_value) - len(raw_value.lstrip())
    if leading >= len(raw_value):
        return None

    quote = raw_value[leading]
    if quote not in {'"', "'"}:
        return None

    for idx in range(len(raw_value) - 1, leading, -1):
        if raw_value[idx] != quote:
            continue
        suffix = raw_value[idx + 1 :]
        stripped_suffix = suffix.strip()
        if not stripped_suffix or stripped_suffix.startswith("#"):
            quoted_end = idx + 1
            return (
                raw_value[:leading],
                raw_value[leading:quoted_end],
                raw_value[leading + 1 : idx],
                raw_value[quoted_end:],
                leading,
                quoted_end,
            )
    return None


def _skip_inline_whitespace(source_text: str, *, start: int, end: int) -> int:
    index = start
    while index < end and source_text[index] in {" ", "\t"}:
        index += 1
    return index


def _diagnostic(
    *,
    code: str,
    message: str,
    start: int,
    end: int,
    hint: str | None,
    category: str | None,
    severity: Severity,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        message=message,
        range=TextRange.new(TextSize.from_int(start), TextSize.from_int(end)),
        severity=severity,
        hint=hint,
        category=category,
    )
