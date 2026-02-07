"""Unified entrypoints that orchestrate parse/lint/format with one parse lifecycle."""

from __future__ import annotations

from jominipy.diagnostics import has_errors
from jominipy.format import run_format as _run_format
from jominipy.lint import run_lint as _run_lint
from jominipy.parser import ParseMode, ParserOptions, parse_result
from jominipy.pipeline.result import JominiParseResult
from jominipy.pipeline.results import (
    CheckRunResult,
    FormatRunResult,
    LintRunResult,
)


def run_lint(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> LintRunResult:
    """Run linting over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    return _run_lint(resolved_parse.source_text, parse=resolved_parse)


def run_format(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> FormatRunResult:
    """Run formatting over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    return _run_format(resolved_parse.source_text, parse=resolved_parse)


def run_check(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> CheckRunResult:
    """Run parse + lint checks over one Jomini parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)
    lint_result = _run_lint(resolved_parse.source_text, parse=resolved_parse)
    diagnostics = list(lint_result.diagnostics)
    return CheckRunResult(
        parse=resolved_parse,
        diagnostics=diagnostics,
        has_errors=has_errors(diagnostics),
    )


def _resolve_parse(
    text: str,
    *,
    options: ParserOptions | None,
    mode: ParseMode | None,
    parse: JominiParseResult | None,
) -> JominiParseResult:
    if parse is not None:
        if options is not None or mode is not None:
            raise ValueError("Pass either parse or options/mode, not both")
        return parse
    return parse_result(text, options=options, mode=mode)
