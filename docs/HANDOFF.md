# Handoff

## Current State
- Lexer (`jominipy/lexer/lexer.py`)
  - Trivia + non-trivia tokenization is lossless.
  - Multiline quoted strings are enabled by default (`allow_multiline_strings=True`).
  - Unterminated quoted strings still emit diagnostics at EOF.
- Buffered lexer (`jominipy/lexer/buffered_lexer.py`)
  - Lookahead/checkpoint model is in place (`nth_non_trivia`, rewind).
- Token source (`jominipy/parser/token_source.py`)
  - Filters trivia and stores ownership (`Trivia.trailing`).
  - Exposes boundary metadata (`has_preceding_trivia`, `has_nth_preceding_trivia`) used by grammar.
- Syntax kinds (`jominipy/syntax/kind.py`)
  - Added `JominiSyntaxKind` with parser/tree vocabulary:
    - sentinels: `TOMBSTONE`, `EOF`
    - token kinds mapped from lexer token kinds
    - node kinds: `ROOT`, `ERROR`, `SOURCE_FILE`, `STATEMENT_LIST`, `KEY_VALUE`, `BLOCK`, `SCALAR`, `TAGGED_BLOCK_VALUE`
- Parser/events/markers
  - Events now use `JominiSyntaxKind`: `jominipy/parser/event.py`.
  - Added event replay processor with forward-parent/tombstone semantics: `process_events(...)`.
  - Marker completion/change-kind now take `JominiSyntaxKind`: `jominipy/parser/marker.py`.
- CST/Tree sink
  - Minimal immutable green tree + builder implemented: `jominipy/cst/green.py`.
  - Lossless tree sink implemented: `jominipy/parser/tree_sink.py`.
  - Fixed token slicing bug so token text excludes leading/trailing trivia.
- Grammar + entrypoint
  - Jomini grammar routines added: `jominipy/parser/grammar.py`.
  - High-level parse entrypoint added: `jominipy/parser/jomini.py` (`parse_jomini`).
  - Supports:
    - top-level and nested statement lists
    - key/value operators (`=`, `==`, `!=`, `>`, `>=`, `<`, `<=`, `?=`)
    - implicit block assignment (`foo{bar=qux}`)
    - tagged block value parsing (`color = rgb { ... }`) via `TAGGED_BLOCK_VALUE`

## Reference Map
- Biome lexer trait & helpers: `references/biome/crates/biome_parser/src/lexer.rs`
- Biome token source: `references/biome/crates/biome_parser/src/token_source.rs`
- Biome parser events/markers: `references/biome/crates/biome_parser/src/event.rs`, `references/biome/crates/biome_parser/src/marker.rs`
- Biome tree sink: `references/biome/crates/biome_parser/src/tree_sink.rs`
- Biome JSON syntax kinds/list structure: `references/biome/crates/biome_json_syntax/src/generated/kind.rs`

## Notes
- `docs/EDGE_CASES_FAILURE.md` now tracks intentionally unsupported edge cases.
- Parser tests include CST dump utility and optional console output:
  - `PRINT_CST=1 uv run pytest -s -q tests/test_parser.py`
- Current parser-test status:
  - `34 passed, 4 xfailed, 1 xpassed`
  - `xfailed` tests represent unsupported edge cases that are accepted/diagnosed inconsistently today.

## Next Steps (Suggested)
1. Normalize unsupported edge-case handling
   - Convert selected `xpass`/accepted edge cases into explicit diagnostics or parser modes.
   - Keep `EDGE_CASES_FAILURE.md` aligned with test expectations.
2. Improve value-model fidelity
   - Decide whether date-like forms (`1821.1.1`) should remain scalar-token composites in CST and be interpreted only in AST/semantic passes.
   - Add typed AST wrappers for scalar interpretation (bool/date/number/string) with delayed coercion.
3. Expand grammar precision
   - Semicolon-after-quoted scalar behavior.
   - Optional compatibility mode for legacy saves (`extra }`, missing `}`) if desired.
4. CWTools-rules readiness (later phase)
   - Keep shared infrastructure (lexer/token-source/events/sink).
   - Add separate grammar/syntax profile for rules once scope starts.
5. Test hardening
   - Keep CST regression assertions for token text/trivia boundaries.
   - Add focused tests for `TAGGED_BLOCK_VALUE` structure and nested tagged forms.
