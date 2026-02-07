"""Biome-style parser recovery primitives."""

from dataclasses import dataclass
from enum import StrEnum

from jominipy.lexer import TokenKind
from jominipy.parser.marker import CompletedMarker
from jominipy.syntax import JominiSyntaxKind


class RecoveryError(StrEnum):
    EOF = "eof"
    ALREADY_RECOVERED = "already_recovered"
    RECOVERY_DISABLED = "recovery_disabled"


@dataclass(frozen=True, slots=True)
class ParseRecoveryTokenSet:
    """Recover by consuming tokens into an ERROR node until a safe token is reached."""

    node_kind: JominiSyntaxKind
    recovery_set: frozenset[TokenKind]
    line_break: bool = False

    def enable_recovery_on_line_break(self) -> "ParseRecoveryTokenSet":
        return ParseRecoveryTokenSet(
            node_kind=self.node_kind,
            recovery_set=self.recovery_set,
            line_break=True,
        )

    def recover(self, parser: "Parser") -> tuple[CompletedMarker | None, RecoveryError | None]:
        if parser.at(TokenKind.EOF):
            return None, RecoveryError.EOF

        if self.is_at_recovered(parser):
            return None, RecoveryError.ALREADY_RECOVERED

        if parser.is_speculative_parsing():
            return None, RecoveryError.RECOVERY_DISABLED

        marker = parser.start()
        while not parser.at(TokenKind.EOF) and not self.is_at_recovered(parser):
            parser.bump_any()

        return marker.complete(parser, self.node_kind), None

    def is_at_recovered(self, parser: "Parser") -> bool:
        return parser.at_set(self.recovery_set) or (
            self.line_break and parser.has_preceding_line_break
        )


from jominipy.parser.parser import Parser
