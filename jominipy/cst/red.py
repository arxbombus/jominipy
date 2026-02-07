"""Red CST wrappers over immutable green nodes/tokens."""

from __future__ import annotations

from dataclasses import dataclass

from jominipy.cst.green import GreenNode
from jominipy.lexer import TriviaKind, TriviaPiece
from jominipy.syntax import JominiSyntaxKind


@dataclass(frozen=True, slots=True)
class SyntaxTriviaPiece:
    kind: TriviaKind
    text: str


class SyntaxToken:
    __slots__ = (
        "kind",
        "text",
        "leading_trivia",
        "trailing_trivia",
        "parent",
        "index_in_parent",
        "_source",
        "_start",
        "_token_start",
        "_token_end",
        "_end",
    )

    def __init__(
        self,
        *,
        kind: JominiSyntaxKind,
        text: str,
        leading_pieces: tuple[TriviaPiece, ...],
        trailing_pieces: tuple[TriviaPiece, ...],
        parent: SyntaxNode,
        index_in_parent: int,
        source: str,
        start: int,
    ) -> None:
        self.kind = kind
        self.text = text
        self.parent = parent
        self.index_in_parent = index_in_parent
        self._source = source
        self._start = start

        leading_len = sum(piece.length.value for piece in leading_pieces)
        trailing_len = sum(piece.length.value for piece in trailing_pieces)

        self._token_start = start + leading_len
        self._token_end = self._token_start + len(text)
        self._end = self._token_end + trailing_len

        self.leading_trivia = _build_trivia(
            source=source,
            start=self._start,
            pieces=leading_pieces,
        )
        self.trailing_trivia = _build_trivia(
            source=source,
            start=self._token_end,
            pieces=trailing_pieces,
        )

    @property
    def start(self) -> int:
        return self._start

    @property
    def end(self) -> int:
        return self._end

    @property
    def token_start(self) -> int:
        return self._token_start

    @property
    def token_end(self) -> int:
        return self._token_end

    @property
    def text_with_trivia(self) -> str:
        if not self._source:
            return self.text
        return self._source[self._start : self._end]

    @property
    def text_trimmed(self) -> str:
        return self.text

    @property
    def leading_trivia_text(self) -> str:
        return "".join(piece.text for piece in self.leading_trivia)

    @property
    def trailing_trivia_text(self) -> str:
        return "".join(piece.text for piece in self.trailing_trivia)


class SyntaxNode:
    __slots__ = (
        "kind",
        "parent",
        "index_in_parent",
        "_children",
        "_source",
        "_start",
        "_end",
    )

    def __init__(
        self,
        *,
        kind: JominiSyntaxKind,
        parent: SyntaxNode | None,
        index_in_parent: int,
        source: str,
        start: int,
    ) -> None:
        self.kind = kind
        self.parent = parent
        self.index_in_parent = index_in_parent
        self._source = source
        self._start = start
        self._end = start
        self._children: tuple[SyntaxElement, ...] = ()

    @property
    def start(self) -> int:
        return self._start

    @property
    def end(self) -> int:
        return self._end

    @property
    def text(self) -> str:
        if not self._source:
            return ""
        return self._source[self._start : self._end]

    @property
    def children(self) -> tuple[SyntaxElement, ...]:
        return self._children

    def child_nodes(self) -> tuple[SyntaxNode, ...]:
        return tuple(child for child in self._children if isinstance(child, SyntaxNode))

    def child_tokens(self) -> tuple[SyntaxToken, ...]:
        return tuple(child for child in self._children if isinstance(child, SyntaxToken))

    def descendants_tokens(self) -> tuple[SyntaxToken, ...]:
        tokens: list[SyntaxToken] = []

        def walk(node: SyntaxNode) -> None:
            for child in node.children:
                if isinstance(child, SyntaxToken):
                    tokens.append(child)
                else:
                    walk(child)

        walk(self)
        return tuple(tokens)

    def next_sibling(self) -> SyntaxElement | None:
        if self.parent is None:
            return None
        index = self.index_in_parent + 1
        if index >= len(self.parent.children):
            return None
        return self.parent.children[index]

    def prev_sibling(self) -> SyntaxElement | None:
        if self.parent is None or self.index_in_parent == 0:
            return None
        return self.parent.children[self.index_in_parent - 1]


type SyntaxElement = SyntaxNode | SyntaxToken


def from_green(root: GreenNode, source: str = "") -> SyntaxNode:
    red_root, _ = _build_node(
        green=root,
        parent=None,
        index_in_parent=0,
        source=source,
        start=0,
    )
    return red_root


def _build_node(
    *,
    green: GreenNode,
    parent: SyntaxNode | None,
    index_in_parent: int,
    source: str,
    start: int,
) -> tuple[SyntaxNode, int]:
    node = SyntaxNode(
        kind=green.kind,
        parent=parent,
        index_in_parent=index_in_parent,
        source=source,
        start=start,
    )

    current = start
    children: list[SyntaxElement] = []
    for child_index, child in enumerate(green.children):
        if isinstance(child, GreenNode):
            red_child, next_offset = _build_node(
                green=child,
                parent=node,
                index_in_parent=child_index,
                source=source,
                start=current,
            )
            children.append(red_child)
            current = next_offset
            continue

        token = SyntaxToken(
            kind=child.kind,
            text=child.text,
            leading_pieces=child.leading_trivia,
            trailing_pieces=child.trailing_trivia,
            parent=node,
            index_in_parent=child_index,
            source=source,
            start=current,
        )
        children.append(token)
        current = token.end

    node._children = tuple(children)
    node._end = current
    return node, current


def _build_trivia(
    *,
    source: str,
    start: int,
    pieces: tuple[TriviaPiece, ...],
) -> tuple[SyntaxTriviaPiece, ...]:
    if not pieces:
        return ()

    out: list[SyntaxTriviaPiece] = []
    offset = start
    for piece in pieces:
        piece_end = offset + piece.length.value
        text = source[offset:piece_end] if source else ""
        out.append(SyntaxTriviaPiece(kind=piece.kind, text=text))
        offset = piece_end
    return tuple(out)


__all__ = [
    "SyntaxElement",
    "SyntaxNode",
    "SyntaxToken",
    "SyntaxTriviaPiece",
    "from_green",
]
