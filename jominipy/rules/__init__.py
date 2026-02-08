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
from jominipy.rules.schema_graph import (
    RuleSchemaGraph,
    build_schema_graph,
    load_hoi4_schema_graph,
)
from jominipy.rules.semantics import (
    RuleFieldConstraint,
    RuleValueSpec,
    build_field_constraints_by_object,
    build_required_fields_by_object,
    load_hoi4_enum_values,
    load_hoi4_field_constraints,
    load_hoi4_required_fields,
    load_hoi4_type_keys,
)

__all__ = [
    "IndexedRuleStatement",
    "LoadRulesResult",
    "RuleCardinality",
    "RuleExpression",
    "RuleFieldConstraint",
    "RuleFileIR",
    "RuleMetadata",
    "RuleOption",
    "RuleSchemaGraph",
    "RuleScopeReplacement",
    "RuleSetIR",
    "RuleStatement",
    "RuleValueSpec",
    "RulesParseResult",
    "build_field_constraints_by_object",
    "build_required_fields_by_object",
    "build_schema_graph",
    "load_hoi4_enum_values",
    "load_hoi4_field_constraints",
    "load_hoi4_required_fields",
    "load_hoi4_schema_graph",
    "load_hoi4_type_keys",
    "load_rules_directory",
    "load_rules_paths",
    "parse_rules_file",
    "parse_rules_text",
    "to_file_ir",
]
