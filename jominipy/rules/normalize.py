"""Normalize parsed rules files into deterministic indexed IR."""

from __future__ import annotations

from collections import defaultdict
import re

from jominipy.rules.ir import (
    IndexedRuleStatement,
    RuleFileIR,
    RuleSetIR,
    RuleStatement,
)

_BRACKET_KEY_PATTERN = re.compile(r"^(?P<family>[^\[\]]+)\[(?P<argument>.*)\]$")

_CATEGORY_BY_FAMILY = {
    "alias": "alias",
    "single_alias": "single_alias",
    "type": "type",
    "enum": "enum",
    "complex_enum": "complex_enum",
    "value_set": "value_set",
    "value": "value",
}

_SECTION_KEYS = {
    "types",
    "enums",
    "values",
    "links",
    "scopes",
    "folders",
    "modifiers",
    "localisation_commands",
    "list_merge_optimisations",
}


def normalize_ruleset(files: tuple[RuleFileIR, ...]) -> RuleSetIR:
    indexed: list[IndexedRuleStatement] = []
    for file in files:
        for statement in file.statements:
            _index_statement(statement, indexed=indexed)

    ordered = tuple(
        sorted(
            indexed,
            key=lambda item: (
                item.category,
                item.source_path,
                item.source_range.start.value,
                item.source_range.end.value,
                item.key,
                item.family or "",
                item.argument or "",
            ),
        )
    )

    grouped: defaultdict[str, list[IndexedRuleStatement]] = defaultdict(list)
    for item in ordered:
        grouped[item.category].append(item)
    by_category = {category: tuple(items) for category, items in sorted(grouped.items())}

    return RuleSetIR(files=files, indexed=ordered, by_category=by_category)


def _index_statement(statement: RuleStatement, *, indexed: list[IndexedRuleStatement]) -> None:
    if statement.key is not None:
        family, argument = _parse_key_pattern(statement.key)
        category = _infer_category(statement.key, family)
        indexed.append(
            IndexedRuleStatement(
                category=category,
                source_path=statement.source_path,
                source_range=statement.source_range,
                key=statement.key,
                family=family,
                argument=argument,
                statement=statement,
            )
        )

    if statement.value.kind in {"block", "tagged_block"}:
        for nested in statement.value.block:
            _index_statement(nested, indexed=indexed)


def _parse_key_pattern(key: str) -> tuple[str | None, str | None]:
    match = _BRACKET_KEY_PATTERN.match(key)
    if match is None:
        return None, None
    family = match.group("family").strip()
    argument = match.group("argument").strip()
    return family or None, argument or None


def _infer_category(key: str, family: str | None) -> str:
    if family is not None:
        return _CATEGORY_BY_FAMILY.get(family, "pattern")
    if key in _SECTION_KEYS:
        return "section"
    return "rule"

