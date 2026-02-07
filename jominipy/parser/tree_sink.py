"""Lossless tree sink for parser events."""

from dataclasses import dataclass

from jominipy.cst import GreenNode, TreeBuilder
from jominipy.diagnostics import Diagnostic
from jominipy.lexer import Trivia, TriviaPiece
from jominipy.syntax import JominiSyntaxKind
from jominipy.text import TextSize


@dataclass(frozen=True, slots=True)
class ParsedGreenTree:
    root: GreenNode
    diagnostics: list[Diagnostic]


class LosslessTreeSink:
    """Converts parser events + trivia ownership into a green CST."""

    def __init__(
        self,
        text: str,
        trivia: list[Trivia],
        builder: TreeBuilder | None = None,
    ) -> None:
        self._text = text
        self._trivia = trivia
        self._text_pos = TextSize.from_int(0)
        self._trivia_pos = 0
        self._parents_count = 0
        self._errors: list[Diagnostic] = []
        self._builder = builder if builder is not None else TreeBuilder()
        self._needs_eof = True
        self._trivia_pieces: list[TriviaPiece] = []

    def token(self, kind: JominiSyntaxKind, end: TextSize) -> None:
        self._do_token(kind, end)

    def start_node(self, kind: JominiSyntaxKind) -> None:
        self._builder.start_node(kind)
        self._parents_count += 1

    def finish_node(self) -> None:
        self._parents_count -= 1
        if self._parents_count < 0:
            raise RuntimeError("finish_node called more often than start_node")

        if self._parents_count == 0 and self._needs_eof:
            self._do_token(JominiSyntaxKind.EOF, TextSize.from_int(len(self._text)))

        self._builder.finish_node()

    def errors(self, errors: list[Diagnostic]) -> None:
        self._errors = list(errors)

    def finish(self) -> ParsedGreenTree:
        return ParsedGreenTree(root=self._builder.finish(), diagnostics=self._errors)

    def _do_token(self, kind: JominiSyntaxKind, token_end: TextSize) -> None:
        if kind == JominiSyntaxKind.EOF:
            self._needs_eof = False

        # Attach all trivia up to token start as leading trivia.
        self._eat_trivia(trailing=False, token_end=token_end)
        token_start = self._text_pos
        trailing_start = len(self._trivia_pieces)

        self._text_pos = token_end

        # Attach trailing trivia until next newline boundary.
        self._eat_trivia(trailing=True, token_end=token_end)

        token_text = self._text[token_start.value : token_end.value]
        leading = tuple(self._trivia_pieces[:trailing_start])
        trailing = tuple(self._trivia_pieces[trailing_start:])

        self._builder.token_with_trivia(
            kind=kind,
            text=token_text,
            leading=leading,
            trailing=trailing,
        )
        self._trivia_pieces.clear()

    def _eat_trivia(self, trailing: bool, token_end: TextSize) -> None:
        while self._trivia_pos < len(self._trivia):
            trivia = self._trivia[self._trivia_pos]
            trivia_start = trivia.range.start
            trivia_end = trivia.range.end

            if trivia.trailing != trailing:
                break
            if self._text_pos != trivia_start:
                break
            if not trailing and trivia_end > token_end:
                break

            self._trivia_pieces.append(
                TriviaPiece(kind=trivia.kind, length=trivia.range.len())
            )
            self._text_pos = trivia_end
            self._trivia_pos += 1
