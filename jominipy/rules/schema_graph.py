"""Cross-file schema graph over normalized CWTools rules IR."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jominipy.rules.ir import IndexedRuleStatement, RuleSetIR, RuleStatement
from jominipy.rules.load import load_rules_directory


@dataclass(frozen=True, slots=True)
class RuleSchemaGraph:
    """Resolved cross-file schema index for one ruleset root."""

    source_root: str
    ruleset: RuleSetIR
    by_category: dict[str, tuple[IndexedRuleStatement, ...]]
    top_level_rule_statements: tuple[RuleStatement, ...]
    enums_by_key: dict[str, tuple[IndexedRuleStatement, ...]]
    types_by_key: dict[str, tuple[IndexedRuleStatement, ...]]
    aliases_by_key: dict[str, tuple[IndexedRuleStatement, ...]]
    single_aliases_by_key: dict[str, tuple[IndexedRuleStatement, ...]]
    values_by_key: dict[str, tuple[IndexedRuleStatement, ...]]
    value_sets_by_key: dict[str, tuple[IndexedRuleStatement, ...]]
    sections_by_key: dict[str, tuple[IndexedRuleStatement, ...]]


def build_schema_graph(*, source_root: str, ruleset: RuleSetIR) -> RuleSchemaGraph:
    """Build a typed schema graph from normalized ruleset IR."""
    return RuleSchemaGraph(
        source_root=source_root,
        ruleset=ruleset,
        by_category=ruleset.by_category,
        top_level_rule_statements=_collect_top_level_rule_statements(ruleset),
        enums_by_key=_group_category_by_name(ruleset, category="enum"),
        types_by_key=_group_category_by_name(ruleset, category="type"),
        aliases_by_key=_group_category_by_name(ruleset, category="alias"),
        single_aliases_by_key=_group_category_by_name(ruleset, category="single_alias"),
        values_by_key=_group_category_by_name(ruleset, category="value"),
        value_sets_by_key=_group_category_by_name(ruleset, category="value_set"),
        sections_by_key=_group_category_by_name(ruleset, category="section"),
    )


@lru_cache(maxsize=1)
def load_hoi4_schema_graph() -> RuleSchemaGraph:
    """Load cross-file schema graph for HOI4 CWTools config files."""
    root = Path(__file__).resolve().parents[2]
    config_root = root / "references/hoi4-rules/Config"
    if not config_root.exists():
        empty_ruleset = RuleSetIR(files=(), indexed=(), by_category={})
        return build_schema_graph(source_root=str(config_root), ruleset=empty_ruleset)

    loaded = load_rules_directory(config_root)
    return build_schema_graph(source_root=str(config_root), ruleset=loaded.ruleset)


def _collect_top_level_rule_statements(ruleset: RuleSetIR) -> tuple[RuleStatement, ...]:
    items = ruleset.by_category.get("rule", ())
    statements: list[RuleStatement] = []
    for item in items:
        if len(item.declaration_path) != 1:
            continue
        if item.statement.kind != "key_value":
            continue
        if item.statement.value.kind != "block":
            continue
        statements.append(item.statement)
    return tuple(statements)


def _group_category_by_name(
    ruleset: RuleSetIR,
    *,
    category: str,
) -> dict[str, tuple[IndexedRuleStatement, ...]]:
    grouped: dict[str, list[IndexedRuleStatement]] = {}
    for item in ruleset.by_category.get(category, ()):
        key = _category_item_name(item)
        grouped.setdefault(key, []).append(item)
    return {name: tuple(items) for name, items in grouped.items()}


def _category_item_name(item: IndexedRuleStatement) -> str:
    if item.argument is not None:
        return item.argument
    if item.family is not None:
        return item.family
    return item.key
