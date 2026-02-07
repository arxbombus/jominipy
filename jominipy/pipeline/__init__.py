"""Shared parse/lower carriers and lazy pipeline entrypoint exports."""

from __future__ import annotations

from jominipy.parser.options import ParseMode, ParserOptions
from jominipy.pipeline.result import JominiParseResult, ParseResultBase
from jominipy.pipeline.results import (
    CheckRunResult,
    FormatRunResult,
    LintRunResult,
    TypecheckRunResult,
)


def run_lint(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
    typecheck: TypecheckRunResult | None = None,
) -> LintRunResult:
    from jominipy.pipeline.entrypoints import run_lint as _run_lint

    return _run_lint(
        text,
        options=options,
        mode=mode,
        parse=parse,
        typecheck=typecheck,
    )


def run_format(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> FormatRunResult:
    from jominipy.pipeline.entrypoints import run_format as _run_format

    return _run_format(text, options=options, mode=mode, parse=parse)


def run_check(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> CheckRunResult:
    from jominipy.pipeline.entrypoints import run_check as _run_check

    return _run_check(text, options=options, mode=mode, parse=parse)


def run_typecheck(
    text: str,
    options: ParserOptions | None = None,
    *,
    mode: ParseMode | None = None,
    parse: JominiParseResult | None = None,
) -> TypecheckRunResult:
    from jominipy.pipeline.entrypoints import run_typecheck as _run_typecheck

    return _run_typecheck(text, options=options, mode=mode, parse=parse)


__all__ = [
    "CheckRunResult",
    "FormatRunResult",
    "JominiParseResult",
    "LintRunResult",
    "ParseResultBase",
    "TypecheckRunResult",
    "run_check",
    "run_format",
    "run_lint",
    "run_typecheck",
]
