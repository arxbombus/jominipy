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
  - `JominiSyntaxKind` is parser/tree vocabulary (token-level syntax kinds + node kinds):
    - sentinels: `TOMBSTONE`, `EOF`
    - token kinds mapped from lexer token kinds
    - node kinds: `ROOT`, `ERROR`, `SOURCE_FILE`, `STATEMENT_LIST`, `KEY_VALUE`, `BLOCK`, `SCALAR`, `TAGGED_BLOCK_VALUE`
- Parser/events/markers
  - Events now use `JominiSyntaxKind`: `jominipy/parser/event.py`.
  - Added event replay processor with forward-parent/tombstone semantics: `process_events(...)`.
  - Marker completion/change-kind now take `JominiSyntaxKind`: `jominipy/parser/marker.py`.
  - Parser now has Biome-style parser-level control helpers in `jominipy/parser/parser.py`:
    - `ParserProgress` stall guard
    - `ParserCheckpoint` + `checkpoint()` / `rewind(...)`
    - speculative mode context (`speculative_parsing()`)
- CST/Tree sink
  - Minimal immutable green tree + builder implemented: `jominipy/cst/green.py`.
  - Lossless tree sink implemented: `jominipy/parser/tree_sink.py`.
  - Fixed token slicing bug so token text excludes leading/trailing trivia.
- Grammar + entrypoint
  - Jomini grammar routines live in `jominipy/parser/grammar.py`.
  - High-level parse entrypoint: `jominipy/parser/jomini.py` (`parse_jomini`).
  - Parser options and modes: `jominipy/parser/options.py` (`strict`, `permissive`, feature gates).
  - List-loop helper aligned with Biome structure: `jominipy/parser/parse_lists.py` (`ParseNodeList`).
  - Recovery primitive aligned with Biome: `jominipy/parser/parse_recovery.py` (`ParseRecoveryTokenSet`).
  - Supports:
    - top-level and nested statement lists
    - key/value operators (`=`, `==`, `!=`, `>`, `>=`, `<`, `<=`, `?=`)
    - implicit block assignment (`foo{bar=qux}`)
    - tagged block value parsing (`color = rgb { ... }`) via `TAGGED_BLOCK_VALUE`

## Reference Map
- Biome lexer trait/helpers: `references/biome/crates/biome_parser/src/lexer.rs`
- Biome token source: `references/biome/crates/biome_parser/src/token_source.rs`
- Biome parser events/markers: `references/biome/crates/biome_parser/src/event.rs`, `references/biome/crates/biome_parser/src/marker.rs`
- Biome recovery/list patterns: `references/biome/crates/biome_parser/src/parse_recovery.rs`, `references/biome/crates/biome_parser/src/parse_lists.rs`
- Biome tree sink: `references/biome/crates/biome_parser/src/tree_sink.rs`
- Biome generated syntax kinds: `references/biome/crates/biome_json_syntax/src/generated/kind.rs`
- Local parity tracker: `docs/BIOME_PARITY.md`

## Notes
- Parser contract has been normalized and is now explicit in `docs/EDGE_CASES_FAILURE.md` (strict vs permissive matrix + feature-gated cases).
- `ParseSeparatedList` is intentionally deferred for now; Jomini currently uses node-list style parsing (`ParseNodeList`).
- Parser tests include optional diagnostics/CST printing:
  - `PRINT_CST=1 PRINT_DIAGNOSTICS=1 uv run pytest -s -q tests/test_parser.py`
- Current parser-test status:
  - `47 passed` in `tests/test_parser.py`
- Lint status was recently autofixed with Ruff:
  - `uv run ruff check --fix`

## Next Task: AST Implementation (Unblocked)
### Goal
Implement a first AST layer over CST without changing parser/CST contracts.

### Required constraints
1. CST remains source-of-truth and lossless (no AST-driven parsing changes).
2. AST performs delayed interpretation for scalars (bool/date-like/number/string).
3. Do not change strict/permissive parser behavior while implementing AST.

### Suggested AST plan
1. Add `jominipy/ast/model.py`
   - dataclass AST node types:
     - `AstSourceFile`
     - `AstStatement` (sum type)
     - `AstKeyValue`
     - `AstBlock`
     - `AstScalar`
     - `AstTaggedBlockValue`
2. Add `jominipy/ast/scalar.py`
   - delayed coercion helpers:
     - `parse_bool(text) -> bool | None`
     - `parse_number(text) -> int | float | None`
     - `parse_date_like(text) -> tuple[int, int, int] | None` (or small typed wrapper)
   - keep original raw text in AST scalar payload.
3. Add `jominipy/ast/lower.py`
   - transform CST nodes (`JominiSyntaxKind.*`) into AST nodes.
   - tolerate `ERROR` nodes by skipping or wrapping as recoverable AST “unknown/error” nodes.
4. Add AST tests (`tests/test_ast.py`)
   - CST -> AST shape tests for:
     - simple key/value
     - nested blocks
     - tagged block values
     - date-like scalar delayed interpretation
     - quoted vs unquoted scalar distinction preserved
   - recovery tolerance tests for malformed input (AST still builds from partial CST).
5. Documentation updates
   - update `docs/ARCHITECTURE.md` and `docs/BIOME_PARITY.md` AST rows after AST is implemented.

### Start points
- CST entrypoint: `parse_jomini` in `jominipy/parser/jomini.py`
- Kind mapping and node vocabulary: `jominipy/syntax/kind.py`
- Green CST structure: `jominipy/cst/green.py`
