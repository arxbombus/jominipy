"""Diagnostics helpers."""

from __future__ import annotations

from collections.abc import Iterable

from jominipy.diagnostics.diagnostic import Diagnostic


def collect_diagnostics(*groups: Iterable[Diagnostic]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for group in groups:
        diagnostics.extend(group)
    return diagnostics


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    return any(d.severity == "error" for d in diagnostics)
