"""Shared debug printers for lexer/parser/ast tests."""

from __future__ import annotations

import os

from jominipy.ast import (
    AstBlock,
    AstError,
    AstKeyValue,
    AstScalar,
    AstSourceFile,
    AstTaggedBlockValue,
)
from jominipy.cst import GreenNode, GreenToken
from jominipy.diagnostics import Diagnostic
from jominipy.lexer import Token, token_text

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
