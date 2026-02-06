"""Parser entrypoints for CWT `.cwt` files."""

from __future__ import annotations

from pathlib import Path

from .lexer import Lexer
from .magic import parse_magic_file
from .parser import Parser, merge_specs

__all__ = ["parse_cwt_dir", "parse_cwt_text"]


def parse_cwt_text(text: str, source: str | Path | None = None):
    """Parse a single `.cwt` document into a CWTSpec."""
    lexer = Lexer(text, source=Path(source) if source else None)
    tokens, diagnostics = lexer.lex()
    parser = Parser(tokens, diagnostics=diagnostics, source=Path(source) if source else None)
    return parser.parse()


def parse_cwt_dir(path: Path):
    """Parse every `.cwt` file under a directory and merge the resulting specs."""
    specs = []
    for file_path in Path(path).rglob("*.cwt"):
        text = file_path.read_text(encoding="utf-8")
        magic_spec = parse_magic_file(text, source=file_path)
        if magic_spec is not None:
            specs.append(magic_spec)
            continue
        specs.append(parse_cwt_text(text, source=file_path))
    return merge_specs(specs)
