"""Format runner scaffold over a shared Jomini parse result."""

from __future__ import annotations

from jominipy.parser import ParseMode, ParserOptions, parse_result
from jominipy.pipeline.result import JominiParseResult
from jominipy.pipeline.results import FormatRunResult


def run_format(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> FormatRunResult:
    """Run formatting from a single parse lifecycle."""
    resolved_parse = _resolve_parse(text, options=options, mode=mode, parse=parse)

    # Placeholder until formatting rules land.
    formatted_text = resolved_parse.source_text
    diagnostics = list(resolved_parse.diagnostics)
    changed = formatted_text != resolved_parse.source_text

    return FormatRunResult(
        parse=resolved_parse,
        formatted_text=formatted_text,
        diagnostics=diagnostics,
        changed=changed,
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
