"""Lint runner scaffold over a shared Jomini parse result."""

from __future__ import annotations

from jominipy.parser import ParseMode, ParserOptions, parse_result
from jominipy.pipeline.result import JominiParseResult
from jominipy.pipeline.results import LintRunResult


def run_lint(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> LintRunResult:
    """Run lint diagnostics from a single parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)

    # Placeholder until lint rules land: lint output currently mirrors parse diagnostics.
    diagnostics = list(resolved_parse.diagnostics)
    return LintRunResult(parse=resolved_parse, diagnostics=diagnostics)


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
