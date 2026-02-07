"""CWTools-like rules ingest and normalized IR utilities."""

from jominipy.rules.ir import (
    IndexedRuleStatement,
    RuleCardinality,
    RuleExpression,
    RuleFileIR,
    RuleMetadata,
    RuleOption,
    RuleScopeReplacement,
    RuleSetIR,
    RuleStatement,
)
from jominipy.rules.load import (
    LoadRulesResult,
    load_rules_directory,
    load_rules_paths,
)
from jominipy.rules.parser import parse_rules_file, parse_rules_text, to_file_ir
from jominipy.rules.result import RulesParseResult

__all__ = [
    "IndexedRuleStatement",
    "LoadRulesResult",
    "RuleCardinality",
    "RuleExpression",
    "RuleFileIR",
    "RuleMetadata",
    "RuleOption",
    "RuleScopeReplacement",
    "RuleSetIR",
    "RuleStatement",
    "RulesParseResult",
    "load_rules_directory",
    "load_rules_paths",
    "parse_rules_file",
    "parse_rules_text",
    "to_file_ir",
]
