"""Parser and normalizer entrypoint for CWTools-like rules files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jominipy.cst import SyntaxElement, SyntaxNode, SyntaxToken
from jominipy.parser import parse
from jominipy.rules.ir import (
    RuleExpression,
    RuleFileIR,
    RuleMetadata,
    RuleOption,
    RuleStatement,
)
from jominipy.rules.result import RulesParseResult
from jominipy.syntax import JominiSyntaxKind
from jominipy.text import TextRange, TextSize

_ASSIGNMENT_OPERATORS: frozenset[JominiSyntaxKind] = frozenset(
    {
        JominiSyntaxKind.EQUAL,
        JominiSyntaxKind.EQUAL_EQUAL,
        JominiSyntaxKind.NOT_EQUAL,
        JominiSyntaxKind.LESS_THAN_OR_EQUAL,
        JominiSyntaxKind.GREATER_THAN_OR_EQUAL,
        JominiSyntaxKind.LESS_THAN,
        JominiSyntaxKind.GREATER_THAN,
        JominiSyntaxKind.QUESTION_EQUAL,
    }
)


@dataclass(frozen=True, slots=True)
class _StatementSyntax:
    node: SyntaxNode
    metadata: RuleMetadata


def parse_rules_text(text: str, source_path: str) -> RulesParseResult:
    """Parse one rules file into a reusable parse carrier."""
    parsed = parse(text)
    return RulesParseResult(source_text=text, parsed=parsed, source_path=source_path)


def to_file_ir(result: RulesParseResult) -> RuleFileIR:
    """Lower one parse result into normalized file IR."""
    syntax_root = result.syntax_root()
    source_file = _first_child_node(syntax_root, JominiSyntaxKind.SOURCE_FILE)
    if source_file is None:
        return RuleFileIR(path=result.source_path, statements=(), diagnostics=tuple(result.diagnostics))

    statement_list = _first_child_node(source_file, JominiSyntaxKind.STATEMENT_LIST)
    if statement_list is None:
        return RuleFileIR(path=result.source_path, statements=(), diagnostics=tuple(result.diagnostics))

    statements = tuple(_lower_statement_list(statement_list, result.source_path))
    file_ir = RuleFileIR(path=result.source_path, statements=statements, diagnostics=tuple(result.diagnostics))
    result.file_ir = file_ir
    return file_ir


def parse_rules_file(path: str | Path) -> RulesParseResult:
    path_obj = Path(path)
    text = path_obj.read_text(encoding="utf-8")
    return parse_rules_text(text, source_path=str(path_obj))


def _lower_statement_list(statement_list: SyntaxNode, source_path: str) -> list[RuleStatement]:
    lowered: list[RuleStatement] = []
    for syntax_statement in _iter_statement_syntax(statement_list):
        lowered.append(_lower_statement(syntax_statement, source_path))
    return lowered


def _iter_statement_syntax(statement_list: SyntaxNode) -> list[_StatementSyntax]:
    statements: list[_StatementSyntax] = []
    for child in statement_list.children:
        if not isinstance(child, SyntaxNode):
            continue
        if child.kind not in {
            JominiSyntaxKind.KEY_VALUE,
            JominiSyntaxKind.SCALAR,
            JominiSyntaxKind.BLOCK,
            JominiSyntaxKind.ERROR,
        }:
            continue
        first_token = _first_token(child)
        metadata = _extract_metadata(first_token.leading_trivia_text if first_token else "")
        statements.append(_StatementSyntax(node=child, metadata=metadata))
    return statements


def _lower_statement(statement: _StatementSyntax, source_path: str) -> RuleStatement:
    node = statement.node
    source_range = TextRange.at(
        TextSize(node.start),
        TextSize(max(node.end - node.start, 0)),
    )
    if node.kind == JominiSyntaxKind.KEY_VALUE:
        key, operator, value = _lower_key_value(node, source_path)
        return RuleStatement(
            source_path=source_path,
            source_range=source_range,
            kind="key_value",
            key=key,
            operator=operator,
            value=value,
            metadata=statement.metadata,
        )

    if node.kind == JominiSyntaxKind.SCALAR:
        return RuleStatement(
            source_path=source_path,
            source_range=source_range,
            kind="value",
            key=None,
            operator=None,
            value=RuleExpression(kind="scalar", text=_collect_node_text(node)),
            metadata=statement.metadata,
        )

    if node.kind == JominiSyntaxKind.BLOCK:
        return RuleStatement(
            source_path=source_path,
            source_range=source_range,
            kind="value",
            key=None,
            operator=None,
            value=_lower_block_expression(node, source_path),
            metadata=statement.metadata,
        )

    return RuleStatement(
        source_path=source_path,
        source_range=source_range,
        kind="error",
        key=None,
        operator=None,
        value=RuleExpression(kind="error", text=_collect_node_text(node)),
        metadata=statement.metadata,
    )


def _lower_key_value(node: SyntaxNode, source_path: str) -> tuple[str | None, str | None, RuleExpression]:
    key_node: SyntaxNode | None = None
    operator: str | None = None
    value_node: SyntaxNode | None = None
    key_index = -1
    for index, child in enumerate(node.children):
        if key_node is None and isinstance(child, SyntaxNode) and child.kind == JominiSyntaxKind.SCALAR:
            key_node = child
            key_index = index
            continue
        if operator is None and isinstance(child, SyntaxToken) and child.kind in _ASSIGNMENT_OPERATORS:
            operator = child.text
            continue
        if value_node is None and isinstance(child, SyntaxNode) and index > key_index:
            if child.kind in {
                JominiSyntaxKind.SCALAR,
                JominiSyntaxKind.BLOCK,
                JominiSyntaxKind.TAGGED_BLOCK_VALUE,
            }:
                value_node = child
    key_text = _collect_node_text(key_node) if key_node is not None else None
    return key_text, operator, _lower_expression(value_node, source_path=source_path)


def _lower_expression(node: SyntaxNode | None, source_path: str) -> RuleExpression:
    if node is None:
        return RuleExpression(kind="missing")
    if node.kind == JominiSyntaxKind.SCALAR:
        return RuleExpression(kind="scalar", text=_collect_node_text(node))
    if node.kind == JominiSyntaxKind.BLOCK:
        return _lower_block_expression(node, source_path)
    if node.kind == JominiSyntaxKind.TAGGED_BLOCK_VALUE:
        tag_node: SyntaxNode | None = None
        block_node: SyntaxNode | None = None
        for child in node.children:
            if not isinstance(child, SyntaxNode):
                continue
            if tag_node is None and child.kind == JominiSyntaxKind.SCALAR:
                tag_node = child
                continue
            if block_node is None and child.kind == JominiSyntaxKind.BLOCK:
                block_node = child
        return RuleExpression(
            kind="tagged_block",
            tag=_collect_node_text(tag_node) if tag_node else "",
            block=tuple(
                _lower_statement_list(statement_list, source_path)
                if (statement_list := _first_child_node(block_node, JominiSyntaxKind.STATEMENT_LIST)) is not None
                else ()
            ),
        )
    return RuleExpression(kind="error", text=_collect_node_text(node))


def _lower_block_expression(node: SyntaxNode, source_path: str) -> RuleExpression:
    statement_list = _first_child_node(node, JominiSyntaxKind.STATEMENT_LIST)
    if statement_list is None:
        return RuleExpression(kind="block", block=())
    return RuleExpression(
        kind="block",
        block=tuple(_lower_statement_list(statement_list, source_path)),
    )


def _extract_metadata(leading_trivia_text: str) -> RuleMetadata:
    docs: list[str] = []
    options: list[RuleOption] = []
    for raw_line in leading_trivia_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        if line.startswith("###"):
            docs.append(line[3:].strip())
            continue
        if line.startswith("##"):
            raw_option = line[2:].strip()
            if not raw_option:
                continue
            if "=" in raw_option:
                key, value = raw_option.split("=", 1)
                options.append(
                    RuleOption(
                        key=key.strip(),
                        value=value.strip() or None,
                        raw=raw_option,
                    )
                )
            else:
                options.append(
                    RuleOption(
                        key=raw_option.strip(),
                        value=None,
                        raw=raw_option,
                    )
                )
    return RuleMetadata(documentation=tuple(docs), options=tuple(options))


def _first_child_node(node: SyntaxNode | None, kind: JominiSyntaxKind) -> SyntaxNode | None:
    if node is None:
        return None
    for child in node.children:
        if isinstance(child, SyntaxNode) and child.kind == kind:
            return child
    return None


def _first_token(node: SyntaxNode) -> SyntaxToken | None:
    for child in node.children:
        if isinstance(child, SyntaxToken):
            return child
        nested = _first_token(child)
        if nested is not None:
            return nested


def _collect_node_text(node: SyntaxElement | None) -> str:
    if node is None:
        return ""
    if isinstance(node, SyntaxToken):
        return node.text
    text: list[str] = []
    for child in node.children:
        text.append(_collect_node_text(child))
    return "".join(text)
