"""Helpers for loading and normalizing CWTools-like `.cwt` files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jominipy.rules.ir import RuleFileIR, RuleSetIR
from jominipy.rules.normalize import normalize_ruleset
from jominipy.rules.parser import parse_rules_file, to_file_ir
from jominipy.rules.result import RulesParseResult


@dataclass(frozen=True, slots=True)
class LoadRulesResult:
    """Loaded parse results and merged normalized ruleset."""

    parse_results: tuple[RulesParseResult, ...]
    file_irs: tuple[RuleFileIR, ...]
    ruleset: RuleSetIR


def load_rules_directory(root: str | Path, *, pattern: str = "**/*.cwt") -> LoadRulesResult:
    root_path = Path(root)
    paths = sorted(path for path in root_path.glob(pattern) if path.is_file())
    return load_rules_paths(paths)


def load_rules_paths(paths: Iterable[str | Path]) -> LoadRulesResult:
    parsed: list[RulesParseResult] = []
    files: list[RuleFileIR] = []
    for path in sorted(Path(path_like) for path_like in paths):
        result = parse_rules_file(path)
        parsed.append(result)
        files.append(to_file_ir(result))

    files_tuple = tuple(files)
    return LoadRulesResult(
        parse_results=tuple(parsed),
        file_irs=files_tuple,
        ruleset=normalize_ruleset(files_tuple),
    )

