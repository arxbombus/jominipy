# Handoff

## 2026-02-07 Update: Phase 2 (scalar interpretation hardening) landed
- Implemented in `jominipy/ast/scalar.py`:
  - explicit scalar interpretation kinds via `ScalarKind` (`unknown`, `bool`, `number`, `date_like`)
  - formal interpretation payload via `ScalarInterpretation.kind` and `ScalarInterpretation.value`
  - deterministic precedence and explicit unknown handling
  - quoted scalar policy: non-coercing by default; opt-in coercion via `allow_quoted=True`
- Added scalar policy tests in `tests/test_ast.py`:
  - table-driven unquoted interpretation coverage (bool/date/number/unknown)
  - quoted default-vs-opt-in behavior
  - large integer and sign handling checks
- Validation:
  - `uv run pytest -q tests/test_ast.py tests/test_parser.py tests/test_lexer.py`
  - `uv run ruff check tests jominipy`
  - `218 passed` and Ruff clean
- Parser/CST contracts unchanged; Phase 2 is AST-semantic only.

## 2026-02-07 Update: Phase 1 (AST block/list coercion) landed
- Implemented in `jominipy/ast/model.py`:
  - block-shape helpers: `is_object_like`, `is_array_like`, `is_mixed`, `is_empty_ambiguous`
  - derived coercion helpers: `to_object(multimap=False)`, `to_object(multimap=True)`, `to_array()`
  - typed object/multimap overloads for `to_object(...)`
- Added AST coverage in `tests/test_ast.py` for:
  - object-like/array-like/mixed/empty classification
  - repeated-key coercion policy (`modifier`) with stable ordering
  - coercion guardrails and empty-block behavior
- Validation:
  - `uv run pytest -q tests/test_ast.py tests/test_parser.py tests/test_lexer.py`
  - `209 passed`
- Parser/CST contracts unchanged; Phase 1 is AST-derived-view only.

## 2026-02-07 Update: AST v1 landed + centralized tests
- AST v1 is now implemented:
  - `jominipy/ast/model.py`
  - `jominipy/ast/scalar.py`
  - `jominipy/ast/lower.py`
  - `jominipy/ast/__init__.py`
- Centralized test cases/debug utilities are now implemented:
  - `tests/_shared_cases.py`
  - `tests/_debug.py`
  - cross-pipeline parameterized sweeps in lexer/parser/ast tests
- Current test status:
  - `206 passed` across `tests/test_lexer.py tests/test_parser.py tests/test_ast.py`
- See `docs/NEXT_AGENT_ROADMAP.md` for phased implementation plan.

## Repeated-key coercion policy (AST)
For Jomini objects that repeat keys (e.g. repeated `modifier` in one block), the next agent should keep two levels:
1. Canonical AST (always):
   - preserve exact ordered `AstKeyValue` statements, no implicit merging.
2. Derived coercion views (for consumers):
   - default object coercion: last-write-wins map.
   - multimap coercion: repeated keys become ordered arrays.

Concrete example:
- Input has:
  - `modifier={ country_revolt_factor = 0.5 }`
  - `modifier={ country_pop_unrest=0.25 }`
- Multimap view should expose:
  - `modifier -> [AstBlock(...), AstBlock(...)]`

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

## Next Task
Follow `docs/NEXT_AGENT_ROADMAP.md` starting with **Phase 3** (red CST wrappers) without changing parser/CST contracts.

Suggested next command sequence:
1. `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py`
2. Implement Phase 3 only.
3. `uv run ruff check tests jominipy`
4. Re-run targeted tests, then the full test trio.
