"""Minimal immutable green CST representation."""

from dataclasses import dataclass

from jominipy.lexer import TriviaPiece
from jominipy.syntax import JominiSyntaxKind
from jominipy.text import TextSize


@dataclass(frozen=True, slots=True)
class GreenToken:
    kind: JominiSyntaxKind
    text: str
    leading_trivia: tuple[TriviaPiece, ...]
    trailing_trivia: tuple[TriviaPiece, ...]

    @property
    def text_len(self) -> TextSize:
        return TextSize.from_int(len(self.text))


@dataclass(frozen=True, slots=True)
class GreenNode:
    kind: JominiSyntaxKind
    children: tuple["GreenElement", ...]

    @property
    def text_len(self) -> TextSize:
        total = 0
        for child in self.children:
            total += child.text_len.value
        return TextSize.from_int(total)


type GreenElement = GreenNode | GreenToken


class TreeBuilder:
    """Biome-style tree builder with pythonic immutable outputs."""

    def __init__(self) -> None:
        self._stack: list[tuple[JominiSyntaxKind, list[GreenElement]]] = []
        self._roots: list[GreenElement] = []

    def start_node(self, kind: JominiSyntaxKind) -> None:
        self._stack.append((kind, []))

    def token_with_trivia(
        self,
        kind: JominiSyntaxKind,
        text: str,
        leading: tuple[TriviaPiece, ...],
        trailing: tuple[TriviaPiece, ...],
    ) -> None:
        token = GreenToken(
            kind=kind,
            text=text,
            leading_trivia=leading,
            trailing_trivia=trailing,
        )
        self._push_element(token)

    def finish_node(self) -> None:
        if not self._stack:
            raise RuntimeError("finish_node called with empty builder stack")

        kind, children = self._stack.pop()
        node = GreenNode(kind=kind, children=tuple(children))
        self._push_element(node)

    def finish(self) -> GreenNode:
        if self._stack:
            raise RuntimeError("Cannot finish tree: unclosed nodes remain on stack")

        if len(self._roots) == 1 and isinstance(self._roots[0], GreenNode):
            root = self._roots[0]
            if root.kind == JominiSyntaxKind.ROOT:
                return root

        return GreenNode(
            kind=JominiSyntaxKind.ROOT,
            children=tuple(self._roots),
        )

    def _push_element(self, element: GreenElement) -> None:
        if self._stack:
            self._stack[-1][1].append(element)
            return
        self._roots.append(element)
