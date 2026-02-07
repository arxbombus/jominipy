"""Shared debug printers for lexer/parser/ast tests."""

from __future__ import annotations

import os

from jominipy.ast import (
    AstArrayValue,
    AstBlock,
    AstBlockView,
    AstError,
    AstKeyValue,
    AstObject,
    AstObjectMultimap,
    AstScalar,
    AstSourceFile,
    AstTaggedBlockValue,
)
from jominipy.cst import GreenNode, GreenToken
from jominipy.diagnostics import Diagnostic
from jominipy.lexer import Token, token_text
from jominipy.rules import RuleSetIR

PRINT_TOKENS = os.getenv("PRINT_TOKENS", "0").lower() in {"1", "true", "yes", "on"}
PRINT_CST = os.getenv("PRINT_CST", "0").lower() in {"1", "true", "yes", "on"}
PRINT_AST = os.getenv("PRINT_AST", "0").lower() in {"1", "true", "yes", "on"}
PRINT_SOURCE = os.getenv("PRINT_SOURCE", "0").lower() in {"1", "true", "yes", "on"}
PRINT_DIAGNOSTICS = os.getenv("PRINT_DIAGNOSTICS", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PRINT_AST_VIEWS = os.getenv("PRINT_AST_VIEWS", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PRINT_RULES_IR = os.getenv("PRINT_RULES_IR", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def debug_print_source(test_name: str, source: str) -> None:
    if not PRINT_SOURCE:
        return
    print(f"\n===== {test_name} SOURCE =====")
    print(source)


def debug_dump_tokens(test_name: str, source: str, tokens: list[Token]) -> None:
    if not PRINT_TOKENS:
        return
    debug_print_source(test_name, source)
    print(f"\n===== {test_name} TOKENS =====")
    for index, tok in enumerate(tokens):
        text = token_text(source, tok)
        print(f"{index:03d} {tok.kind.name:<24} range={tok.range.as_tuple()} flags={tok.flags} text={text!r}")


def debug_dump_cst(test_name: str, source: str, root: GreenNode) -> None:
    if not PRINT_CST:
        return
    if not PRINT_SOURCE:
        print(f"\n===== {test_name} SOURCE =====")
        print(source)
    else:
        debug_print_source(test_name, source)
    print(f"===== {test_name} CST =====")
    print(_dump_cst(root))


def debug_dump_ast(test_name: str, ast: AstSourceFile, source: str | None = None) -> None:
    if not PRINT_AST:
        return
    if source is not None:
        debug_print_source(test_name, source)
    print(f"\n===== {test_name} AST =====")
    print(_dump_ast(ast))


def debug_dump_diagnostics(test_name: str, diagnostics: list[Diagnostic], source: str | None = None) -> None:
    if not PRINT_DIAGNOSTICS:
        return
    if source is not None:
        debug_print_source(test_name, source)
    print(f"===== {test_name} DIAGNOSTICS =====")
    if not diagnostics:
        print("(none)")
        return
    for diagnostic in diagnostics:
        print(diagnostic)


def debug_dump_ast_block_view(
    test_name: str,
    view: AstBlockView,
    *,
    source: str | None = None,
) -> None:
    if not PRINT_AST_VIEWS:
        return
    if source is not None:
        debug_print_source(test_name, source)
    print(f"\n===== {test_name} AST VIEW =====")
    print(_dump_ast_block_view(view))


def debug_dump_rules_ir(test_name: str, ruleset: RuleSetIR) -> None:
    if not PRINT_RULES_IR:
        return
    print(f"\n===== {test_name} RULES IR =====")
    print(_dump_rules_ir(ruleset))


def _dump_cst(node: GreenNode) -> str:
    lines: list[str] = []

    def walk_node(current: GreenNode, depth: int) -> None:
        indent = "  " * depth
        lines.append(f"{indent}{current.kind.name}")
        for child in current.children:
            if isinstance(child, GreenNode):
                walk_node(child, depth + 1)
            else:
                walk_token(child, depth + 1)

    def walk_token(token: GreenToken, depth: int) -> None:
        indent = "  " * depth
        text = token.text.replace("\n", "\\n").replace("\r", "\\r")
        lines.append(
            f"{indent}{token.kind.name} text={text!r} "
            f"leading={len(token.leading_trivia)} trailing={len(token.trailing_trivia)}"
        )

    walk_node(node, 0)
    return "\n".join(lines)


def _dump_ast(ast: AstSourceFile) -> str:
    lines: list[str] = ["AstSourceFile"]

    def walk_statement(statement: AstKeyValue | AstScalar | AstBlock | AstError, depth: int) -> None:
        indent = "  " * depth
        if isinstance(statement, AstKeyValue):
            lines.append(f"{indent}AstKeyValue op={statement.operator!r}")
            lines.append(f"{indent}  key={statement.key.raw_text!r}")
            if statement.value is None:
                lines.append(f"{indent}  value=None")
            else:
                walk_value(statement.value, depth + 1)
            return
        if isinstance(statement, AstScalar):
            lines.append(
                f"{indent}AstScalar raw={statement.raw_text!r} quoted={statement.was_quoted} kinds={tuple(k.name for k in statement.token_kinds)}"
            )
            return
        if isinstance(statement, AstBlock):
            lines.append(f"{indent}AstBlock")
            for child in statement.statements:
                walk_statement(child, depth + 1)
            return
        lines.append(f"{indent}AstError raw={statement.raw_text!r}")

    def walk_value(value: AstScalar | AstBlock | AstTaggedBlockValue, depth: int) -> None:
        if isinstance(value, AstScalar):
            walk_statement(value, depth)
            return
        if isinstance(value, AstBlock):
            walk_statement(value, depth)
            return
        indent = "  " * depth
        lines.append(f"{indent}AstTaggedBlockValue tag={value.tag.raw_text!r}")
        walk_statement(value.block, depth + 1)

    for statement in ast.statements:
        walk_statement(statement, 1)

    return "\n".join(lines)


def _dump_ast_block_view(view: AstBlockView) -> str:
    object_view = view.as_object()
    multimap_view = view.as_multimap()
    array_view = view.as_array()

    lines: list[str] = [
        "shape:",
        f"  object_like: {view.is_object_like}",
        f"  array_like: {view.is_array_like}",
        f"  mixed: {view.is_mixed}",
        f"  empty_ambiguous: {view.is_empty_ambiguous}",
        "views:",
        f"  as_object: {_format_object_view(object_view)}",
        f"  as_multimap: {_format_multimap_view(multimap_view)}",
        f"  as_array: {_format_array_view(array_view)}",
    ]
    return "\n".join(lines)


def _format_object_view(value: AstObject | None) -> str:
    if value is None:
        return "None"
    if not value:
        return "{}"
    parts = [f"{key}={_format_ast_value(item)}" for key, item in value.items()]
    return "{ " + ", ".join(parts) + " }"


def _format_multimap_view(value: AstObjectMultimap | None) -> str:
    if value is None:
        return "None"
    if not value:
        return "{}"
    parts: list[str] = []
    for key, items in value.items():
        rendered = ", ".join(_format_ast_value(item) for item in items)
        parts.append(f"{key}=[{rendered}]")
    return "{ " + ", ".join(parts) + " }"


def _format_array_view(value: list[AstArrayValue] | None) -> str:
    if value is None:
        return "None"
    if not value:
        return "[]"
    rendered = ", ".join(_format_ast_value(item) for item in value)
    return "[" + rendered + "]"


def _format_ast_value(value: object) -> str:
    if value is None:
        return "None"
    if isinstance(value, AstScalar):
        text = f"quoted({value.raw_text.strip('"')!r})" if value.was_quoted else value.raw_text
        return f"Scalar({text})"
    if isinstance(value, AstBlock):
        return f"Block(len={len(value.statements)})"
    if isinstance(value, AstTaggedBlockValue):
        return f"Tagged(tag={value.tag.raw_text!r}, block_len={len(value.block.statements)})"
    if isinstance(value, AstKeyValue):
        return f"KeyValue({value.key.raw_text!r})"
    if isinstance(value, AstError):
        return f"Error({value.raw_text!r})"
    return repr(value)


def _dump_rules_ir(ruleset: RuleSetIR) -> str:
    lines: list[str] = []
    lines.append(f"files={len(ruleset.files)} indexed={len(ruleset.indexed)}")
    lines.append("categories:")
    for category, items in ruleset.by_category.items():
        lines.append(f"  {category}: {len(items)}")
    lines.append("indexed:")
    for item in ruleset.indexed:
        start = item.source_range.start.value
        end = item.source_range.end.value
        family = item.family or "-"
        argument = item.argument or "-"
        lines.append(
            f"  [{item.category}] {item.source_path}:{start}-{end} key={item.key!r} family={family!r} arg={argument!r}"
        )
        lines.append(f"    path={' > '.join(item.declaration_path)}")
        metadata_lines = _format_rule_metadata_lines(item.statement.metadata)
        lines.extend(f"    {entry}" for entry in metadata_lines)
    return "\n".join(lines)


def _format_rule_metadata_lines(metadata: object) -> list[str]:
    # Keep this intentionally duck-typed so the debug module stays import-light.
    documentation = getattr(metadata, "documentation", ())
    options = getattr(metadata, "options", ())
    cardinality = getattr(metadata, "cardinality", None)
    scope = getattr(metadata, "scope", None)
    push_scope = getattr(metadata, "push_scope", None)
    replace_scope = getattr(metadata, "replace_scope", None)
    severity = getattr(metadata, "severity", None)
    flags = getattr(metadata, "flags", frozenset())

    lines: list[str] = []
    if documentation:
        lines.append(f"docs={tuple(documentation)!r}")
    if options:
        rendered_options = tuple(f"{option.key}={option.value!r}" for option in options)
        lines.append(f"options={rendered_options!r}")
    if cardinality is not None:
        lines.append(
            "cardinality="
            f"(min={cardinality.minimum!r}, max={cardinality.maximum!r}, soft={cardinality.soft_minimum}, "
            f"min_unbounded={cardinality.minimum_unbounded}, max_unbounded={cardinality.maximum_unbounded})"
        )
    if scope is not None:
        lines.append(f"scope={scope!r}")
    if push_scope is not None:
        lines.append(f"push_scope={push_scope!r}")
    if replace_scope is not None:
        rendered_replace = tuple(f"{entry.source}->{entry.target}" for entry in replace_scope)
        lines.append(f"replace_scope={rendered_replace!r}")
    if severity is not None:
        lines.append(f"severity={severity!r}")
    if flags:
        lines.append(f"flags={tuple(sorted(flags))!r}")
    if not lines:
        lines.append("metadata=(none)")
    return lines
