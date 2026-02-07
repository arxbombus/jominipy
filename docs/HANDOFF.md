# Handoff

## Doc Ownership
- `docs/HANDOFF.md`: current execution state only (latest validated status + exact next commands).
- `docs/archive/HANDOFF_HISTORY_2026-02.md`: historical phase logs and older handoff details.
- `docs/ARCHITECTURE.md`: stable architecture/invariants, not day-to-day status churn.
- `docs/NEXT_AGENT_ROADMAP.md`: forward implementation plan and phase sequencing.

## Current State (as of 2026-02-07)
- Parser/CST pipeline is stable and unchanged during AST phases.
- AST phases 1-4 are complete:
  - block/list coercion utilities
  - scalar interpretation hardening
  - red CST wrappers + lowering migration
  - recovery/diagnostic hardening with deterministic assertions
- Last validation snapshot:
  - `uv run ruff check tests jominipy`
  - `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py tests/test_cst_red.py`
  - `uv run pyrefly check`
  - `227 passed` and `0 pyrefly errors`

## Phase 4 landed details
- Added malformed recovery fixtures in `tests/_shared_cases.py`:
  - `edge_case_recovery_between_valid_statements`
  - `edge_case_missing_value_then_invalid_operator`
- Expanded parser hardening tests in `tests/test_parser.py`:
  - stable top-level `ERROR` placement: `KEY_VALUE`, `ERROR`, `KEY_VALUE`
  - strict/permissive warning diagnostics now assert exact code/severity/category
  - diagnostics are de-duplicated at the same token start
- Parser diagnostics normalization:
  - added `PARSER_EXPECTED_TOKEN` and `PARSER_UNEXPECTED_TOKEN` specs in `jominipy/diagnostics/codes.py`
  - updated `jominipy/parser/grammar.py` to use spec-backed severity/category
- Biome parity alignment:
  - `jominipy/parser/parser.py::error` now suppresses duplicate diagnostics at the same range start.

## Next Task
- Execute **AST Consumer Follow-on** from `docs/NEXT_AGENT_ROADMAP.md`:
  - add `jominipy/ast/views.py` over `AstBlock` coercion helpers
  - add `tests/test_ast_views.py`
  - keep parser/CST behavior unchanged

## Biome practical findings (for next agent)
- Biome composes tools around a shared parse result and typed consumer layer:
  - parse carrier: `biome_js_parser::Parse<T>` (`parse.rs`)
  - typed surface: generated syntax wrappers in `biome_js_syntax`
  - linter entry: `biome_js_analyze::{analyze, analyze_with_inspect_matcher}`
  - formatter entry: `biome_js_formatter::format_node` + `FormatNodeRule`
  - orchestration: `biome_service` JS file handler calls parser/analyzer/formatter in one lifecycle
- jominipy equivalent for this phase:
  - implement a thin AST consumer surface over canonical AST
  - keep CST and parser unchanged
  - avoid hidden coercion and keep behavior deterministic

## Proposed implementation sequence (next agent)
1. Create `jominipy/ast/views.py`:
   - add `AstBlockView` and explicit accessors for object/multimap/array
   - add scalar helper accessors that call existing `interpret_scalar` policy
2. Create `tests/test_ast_views.py`:
   - repeated-key multimap behavior (`modifier`) and ordering
   - mixed/empty behavior contracts
   - quoted vs unquoted scalar helper behavior
3. Keep existing AST/model tests green without parser/CST changes.
4. Update parity + handoff docs after landing.

## Command Sequence
1. `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py tests/test_cst_red.py`
2. Implement AST consumer follow-on only (`jominipy/ast/views.py`, `tests/test_ast_views.py`).
3. `uv run pytest -q tests/test_ast_views.py tests/test_ast.py`
4. `uv run ruff check tests jominipy docs`
5. `uv run pyrefly check`
6. Re-run full parser/lexer/ast/cst-red suite.

## Supersedes
- `docs/archive/HANDOFF_HISTORY_2026-02.md` for earlier phase logs.
