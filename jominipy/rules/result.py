"""Rules parse result carrier."""

from __future__ import annotations

from dataclasses import dataclass, field

from jominipy.cst import SyntaxNode, from_green
from jominipy.pipeline.result import ParseResultBase
from jominipy.rules.ir import RuleFileIR


@dataclass(slots=True)
class RulesParseResult(ParseResultBase):
    """Parse result carrier for CWTools-like rules DSL files."""

    source_path: str
    _syntax_root: SyntaxNode | None = field(default=None, init=False, repr=False)
    _file_ir: RuleFileIR | None = field(default=None, init=False, repr=False)

    @property
    def file_ir(self) -> RuleFileIR | None:
        """Lazily-lowered IR for the parsed file, if lowering has been attempted."""
        return self._file_ir

    @file_ir.setter
    def file_ir(self, value: RuleFileIR) -> None:
        """Set the lazily-lowered IR for the parsed file."""
        self._file_ir = value

    def syntax_root(self) -> SyntaxNode:
        if self._syntax_root is None:
            self._syntax_root = from_green(self.parsed.root, self.source_text)
        return self._syntax_root
