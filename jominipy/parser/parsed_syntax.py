"""Parsed syntax marker utilities."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedSyntax:
    """Simple success/failure wrapper for parse routines."""

    ok: bool

    @staticmethod
    def present() -> "ParsedSyntax":
        return ParsedSyntax(ok=True)

    @staticmethod
    def absent() -> "ParsedSyntax":
        return ParsedSyntax(ok=False)

    def is_present(self) -> bool:
        return self.ok

    def is_absent(self) -> bool:
        return not self.ok
