"""Diagnostic codes and messages."""

from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class DiagnosticSpec:
    code: str
    message: str
    hint: str | None = None
    severity: Severity = "error"
    category: str | None = None


LEXER_UNTERMINATED_STRING: Final[DiagnosticSpec] = DiagnosticSpec(
    code="LEXER_UNTERMINATED_STRING",
    message="Unterminated string literal.",
    hint="Close the string with a double quote or enable multiline strings.",
    severity="error",
    category="lexer",
)

PARSER_EXPECTED_VALUE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_EXPECTED_VALUE",
    message="Expected a value",
    severity="error",
    category="parser",
)

PARSER_EXPECTED_TOKEN: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_EXPECTED_TOKEN",
    message="Expected token",
    severity="error",
    category="parser",
)

PARSER_UNEXPECTED_TOKEN: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_UNEXPECTED_TOKEN",
    message="Unexpected token",
    severity="error",
    category="parser",
)

PARSER_LEGACY_EXTRA_RBRACE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_LEGACY_EXTRA_RBRACE",
    message="Ignoring extra closing brace in permissive mode",
    severity="warning",
    category="parser",
)

PARSER_LEGACY_MISSING_RBRACE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_LEGACY_MISSING_RBRACE",
    message="Missing closing brace tolerated in permissive mode",
    severity="warning",
    category="parser",
)

PARSER_UNSUPPORTED_UNMARKED_LIST: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_UNSUPPORTED_UNMARKED_LIST",
    message='Unsupported unmarked list form: expected tagged list block, got `list "..."`',
    severity="error",
    category="parser",
)

PARSER_UNSUPPORTED_PARAMETER_SYNTAX: Final[DiagnosticSpec] = DiagnosticSpec(
    code="PARSER_UNSUPPORTED_PARAMETER_SYNTAX",
    message="Unsupported parameter syntax scalar (`[[...]]` or `$...$`)",
    severity="error",
    category="parser",
)

TYPECHECK_INCONSISTENT_VALUE_SHAPE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="TYPECHECK_INCONSISTENT_VALUE_SHAPE",
    message="Top-level key mixes incompatible value shapes.",
    severity="warning",
    category="typecheck",
)

TYPECHECK_INVALID_FIELD_TYPE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="TYPECHECK_INVALID_FIELD_TYPE",
    message="Field value does not match CWTools type constraints.",
    severity="warning",
    category="typecheck",
)

TYPECHECK_INVALID_FIELD_REFERENCE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="TYPECHECK_INVALID_FIELD_REFERENCE",
    message="Field value does not match CWTools reference constraints.",
    severity="warning",
    category="typecheck",
)

TYPECHECK_INVALID_SCOPE_CONTEXT: Final[DiagnosticSpec] = DiagnosticSpec(
    code="TYPECHECK_INVALID_SCOPE_CONTEXT",
    message="Field is used outside allowed CWTools scope context.",
    severity="warning",
    category="typecheck",
)

TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT: Final[DiagnosticSpec] = DiagnosticSpec(
    code="TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT",
    message="Scope context is ambiguous due to conflicting scope alias replacements.",
    severity="warning",
    category="typecheck",
)

TYPECHECK_RULE_CUSTOM_ERROR: Final[DiagnosticSpec] = DiagnosticSpec(
    code="TYPECHECK_RULE_CUSTOM_ERROR",
    message="Field matched a CWTools custom error rule.",
    severity="warning",
    category="typecheck",
)

LINT_SEMANTIC_INCONSISTENT_SHAPE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="LINT_SEMANTIC_INCONSISTENT_SHAPE",
    message="Semantic rule: mixed value shapes should be normalized.",
    severity="warning",
    category="lint/semantic",
)

LINT_SEMANTIC_MISSING_REQUIRED_FIELD: Final[DiagnosticSpec] = DiagnosticSpec(
    code="LINT_SEMANTIC_MISSING_REQUIRED_FIELD",
    message="Semantic rule: required field missing according to CWTools schema.",
    severity="warning",
    category="lint/semantic",
)

LINT_SEMANTIC_INVALID_FIELD_TYPE: Final[DiagnosticSpec] = DiagnosticSpec(
    code="LINT_SEMANTIC_INVALID_FIELD_TYPE",
    message="Semantic rule: field value does not match CWTools type constraints.",
    severity="warning",
    category="lint/semantic",
)

LINT_STYLE_SINGLE_LINE_BLOCK: Final[DiagnosticSpec] = DiagnosticSpec(
    code="LINT_STYLE_SINGLE_LINE_BLOCK",
    message="Style rule: multi-value blocks should be split across lines.",
    severity="warning",
    category="lint/style",
)
