"""Lower a Jomini CST into a typed AST."""

from __future__ import annotations

from jominipy.ast.model import (
    AstBlock,
    AstError,
    AstKeyValue,
    AstScalar,
    AstSourceFile,
    AstStatement,
    AstTaggedBlockValue,
    AstValue,
)
from jominipy.cst import GreenNode, GreenToken
from jominipy.parser import parse_jomini
from jominipy.syntax import JominiSyntaxKind

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


def parse_to_ast(text: str) -> AstSourceFile:
    parsed = parse_jomini(text)
    return lower_tree(parsed.root)


def lower_tree(root: GreenNode) -> AstSourceFile:
    source_file = _first_child_node(root, JominiSyntaxKind.SOURCE_FILE)
    if source_file is None:
        return AstSourceFile(statements=())

    statement_list = _first_child_node(source_file, JominiSyntaxKind.STATEMENT_LIST)
    if statement_list is None:
        return AstSourceFile(statements=())

    return AstSourceFile(statements=_lower_statement_list(statement_list))


def _lower_statement_list(node: GreenNode) -> tuple[AstStatement, ...]:
    statements: list[AstStatement] = []
    for child in node.children:
        if not isinstance(child, GreenNode):
            continue

        if child.kind == JominiSyntaxKind.KEY_VALUE:
            lowered = _lower_key_value(child)
            statements.append(lowered)
            continue

        if child.kind == JominiSyntaxKind.SCALAR:
            statements.append(_lower_scalar(child))
            continue

        if child.kind == JominiSyntaxKind.BLOCK:
            statements.append(_lower_block(child))
            continue

        if child.kind == JominiSyntaxKind.ERROR:
            statements.append(AstError(raw_text=_collect_node_text(child)))

    return tuple(statements)


def _lower_key_value(node: GreenNode) -> AstStatement:
    key_node: GreenNode | None = None
    key_index = -1
    operator: str | None = None
    value_node: GreenNode | None = None

    for index, child in enumerate(node.children):
        if key_node is None and isinstance(child, GreenNode):
            if child.kind == JominiSyntaxKind.SCALAR:
                key_node = child
                key_index = index
            continue

        if operator is None and isinstance(child, GreenToken):
            if child.kind in _ASSIGNMENT_OPERATORS:
                operator = child.text
            continue

        if value_node is None and isinstance(child, GreenNode):
            if index <= key_index:
                continue
            if child.kind in {
                JominiSyntaxKind.SCALAR,
                JominiSyntaxKind.BLOCK,
                JominiSyntaxKind.TAGGED_BLOCK_VALUE,
            }:
                value_node = child

    if key_node is None:
        return AstError(raw_text=_collect_node_text(node))

    key = _lower_scalar(key_node)
    value = _lower_value(value_node)
    return AstKeyValue(key=key, operator=operator, value=value)


def _lower_value(node: GreenNode | None) -> AstValue | None:
    if node is None:
        return None

    if node.kind == JominiSyntaxKind.SCALAR:
        return _lower_scalar(node)

    if node.kind == JominiSyntaxKind.BLOCK:
        return _lower_block(node)

    if node.kind == JominiSyntaxKind.TAGGED_BLOCK_VALUE:
        return _lower_tagged_block_value(node)

    return None


def _lower_block(node: GreenNode) -> AstBlock:
    statement_list = _first_child_node(node, JominiSyntaxKind.STATEMENT_LIST)
    if statement_list is None:
        return AstBlock(statements=())
    return AstBlock(statements=_lower_statement_list(statement_list))


def _lower_tagged_block_value(node: GreenNode) -> AstTaggedBlockValue:
    tag_node: GreenNode | None = None
    block_node: GreenNode | None = None

    for child in node.children:
        if not isinstance(child, GreenNode):
            continue
        if tag_node is None and child.kind == JominiSyntaxKind.SCALAR:
            tag_node = child
            continue
        if block_node is None and child.kind == JominiSyntaxKind.BLOCK:
            block_node = child

    if tag_node is None:
        tag = AstScalar(raw_text="", token_kinds=(), was_quoted=False)
    else:
        tag = _lower_scalar(tag_node)

    block = _lower_block(block_node) if block_node is not None else AstBlock(statements=())
    return AstTaggedBlockValue(tag=tag, block=block)


def _lower_scalar(node: GreenNode) -> AstScalar:
    token_kinds: list[JominiSyntaxKind] = []
    parts: list[str] = []

    for child in node.children:
        if not isinstance(child, GreenToken):
            continue
        token_kinds.append(child.kind)
        parts.append(child.text)

    was_quoted = (
        len(token_kinds) == 1 and token_kinds[0] == JominiSyntaxKind.STRING
    )
    return AstScalar(
        raw_text="".join(parts),
        token_kinds=tuple(token_kinds),
        was_quoted=was_quoted,
    )


def _first_child_node(node: GreenNode, kind: JominiSyntaxKind) -> GreenNode | None:
    for child in node.children:
        if isinstance(child, GreenNode) and child.kind == kind:
            return child
    return None


def _collect_node_text(node: GreenNode) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, GreenToken):
            parts.append(child.text)
        else:
            parts.append(_collect_node_text(child))
    return "".join(parts)


__all__ = ["lower_tree", "parse_to_ast"]
