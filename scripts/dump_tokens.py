#!/usr/bin/env python
from pathlib import Path

from jominipy.parser.lexer import Lexer
from jominipy.parser.tokens import (
    FloatLiteralToken,
    IntLiteralToken,
    OperatorToken,
    StrLiteralToken,
    TokenType,
    Trivia,
)


def format_trivia(trivia: tuple[Trivia, ...]) -> str:
    if not trivia:
        return "[]"
    parts: list[str] = []
    for t in trivia:
        parts.append(f"({t.kind.name}, {t.lexeme!r}, span=({t.span.start},{t.span.end}))")
    return "[" + ", ".join(parts) + "]"


def format_token(idx: int, token: TokenType) -> str:
    base = (
        f"[{idx}] {token.__class__.__name__} "
        f"kind={token.kind.name} "
        f"lexeme={token.lexeme!r} "
        f"span=({token.span.start},{token.span.end}) "
        f"leading={format_trivia(token.leading_trivia)} "
        f"trailing={format_trivia(token.trailing_trivia)}"
    )

    # Add type-specific details
    if isinstance(token, OperatorToken):
        return base + f" operator={token.operator.name}"
    if isinstance(token, IntLiteralToken):
        return base + f" int_value={token.int_value}"
    if isinstance(token, FloatLiteralToken):
        return base + f" float_value={token.float_value}"
    if isinstance(token, StrLiteralToken):
        return base + f" str_value={token.str_value!r} is_quoted={token.is_quoted}"

    return base


def main() -> None:
    input_path = Path(
        "~/programming/paradox/hoi4/clausewitzpy/docs/MillenniumDawn/common/units/equipment/MD_artillery.txt"
    ).expanduser()
    output_path = Path("out/MD_artillery_tokens.txt")

    text = input_path.read_text(encoding="utf-8")

    lexer = Lexer(text, source=input_path)
    tokens = lexer.tokenize()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for idx, token in enumerate(tokens):
            f.write(format_token(idx, token) + "\n")

    print(f"Wrote {len(tokens)} tokens to {output_path}")


if __name__ == "__main__":
    main()
