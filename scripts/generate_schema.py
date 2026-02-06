from __future__ import annotations

import argparse
from pathlib import Path
import sys

from jominipy.legacy.generator import emit_spec
from jominipy.legacy.parser import parse_cwt_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate OpenAPI schema from CWT definitions.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("references/hoi4-rules/Config"),
        help="Directory containing .cwt files (defaults to references/hoi4-rules/Config).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("out"),
        help="Output directory (defaults to ./out).",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["openapi-json", "openapi-yaml", "dto-json"],
        default=["openapi-json", "openapi-yaml"],
        help="Which artifacts to emit.",
    )
    parser.add_argument("--dto", action="store_true", help="Also emit dto.json alongside OpenAPI output.")
    parser.add_argument("--no-validate", action="store_true", help="Skip OpenAPI schema validation.")
    parser.add_argument("--split", action="store_true", help="Write split component JSON files for debugging.")
    parser.add_argument("--title", default="CWT Schema", help="Title for the OpenAPI document.")
    parser.add_argument("--version", default="0.1.0", help="Version for the OpenAPI document.")
    args = parser.parse_args(argv)

    formats = list(args.formats)
    if args.dto and "dto-json" not in formats:
        formats.append("dto-json")

    try:
        spec = parse_cwt_dir(args.input)
        written = emit_spec(
            spec,
            args.out,
            formats=formats,
            split=args.split,
            validate=not args.no_validate,
            title=args.title,
            version=args.version,
        )
    except Exception as exc:
        print(f"Failed to generate schema: {exc}", file=sys.stderr)
        return 1

    for fmt, path in written.items():
        print(f"Wrote {fmt} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
