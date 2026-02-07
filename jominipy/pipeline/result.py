"""Parse/lower carriers that mirror Biome's Parse<T> ergonomics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from jominipy.cst import from_green
from jominipy.diagnostics import has_errors
from jominipy.parser.options import ParserOptions
from jominipy.parser.tree_sink import ParsedGreenTree

if TYPE_CHECKING:
    from jominipy.analysis import AnalysisFacts
    from jominipy.ast import AstBlockView, AstSourceFile
    from jominipy.cst import GreenNode, SyntaxNode
    from jominipy.diagnostics import Diagnostic


@dataclass(slots=True)
class ParseResultBase:
    """Shared parse carrier for parse-once/consume-many workflows."""

    source_text: str
    parsed: ParsedGreenTree

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return self.parsed.diagnostics

    @property
    def has_errors(self) -> bool:
        return has_errors(self.parsed.diagnostics)

    def green_root(self) -> GreenNode:
        return self.parsed.root


@dataclass(slots=True)
class JominiParseResult(ParseResultBase):
    """Jomini game-script parse result with typed syntax/AST/view accessors."""

    options: ParserOptions
    _syntax_root: SyntaxNode | None = field(default=None, init=False, repr=False)
    _ast_root: AstSourceFile | None = field(default=None, init=False, repr=False)
    _root_view: AstBlockView | None = field(default=None, init=False, repr=False)
    _analysis_facts: AnalysisFacts | None = field(default=None, init=False, repr=False)

    def syntax_root(self) -> SyntaxNode:
        if self._syntax_root is None:
            self._syntax_root = from_green(self.parsed.root, self.source_text)
        return self._syntax_root

    def ast_root(self) -> AstSourceFile:
        if self._ast_root is None:
            from jominipy.ast.lower import lower_syntax_tree

            self._ast_root = lower_syntax_tree(self.syntax_root())
        return self._ast_root

    def root_view(self) -> AstBlockView:
        if self._root_view is None:
            from jominipy.ast import AstBlock, AstBlockView

            self._root_view = AstBlockView(AstBlock(statements=self.ast_root().statements))
        return self._root_view

    def analysis_facts(self) -> AnalysisFacts:
        if self._analysis_facts is None:
            from jominipy.analysis import build_analysis_facts

            self._analysis_facts = build_analysis_facts(self.ast_root())
        return self._analysis_facts
