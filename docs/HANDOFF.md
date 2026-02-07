# Handoff

## Doc Ownership
- `docs/HANDOFF.md`: current execution state only (latest validated status + exact next commands).
- `docs/archive/HANDOFF_HISTORY_2026-02.md`: historical phase logs and older handoff details.
- `docs/ARCHITECTURE.md`: stable architecture/invariants, not day-to-day status churn.
- `docs/NEXT_AGENT_ROADMAP.md`: forward implementation plan and phase sequencing.

## Current State (as of 2026-02-07)
- Parser/CST pipeline is stable and unchanged during AST phases.
- AST phases 1-3 are complete:
  - block/list coercion utilities
  - scalar interpretation hardening
  - red CST wrappers + lowering migration
- Last validation snapshot:
  - `uv run ruff check tests jominipy`
  - `uv run pytest -q tests/test_cst_red.py tests/test_ast.py tests/test_parser.py tests/test_lexer.py`
  - `220 passed`

## Next Task
- Execute **Phase 4** from `docs/NEXT_AGENT_ROADMAP.md`:
  - recovery/diagnostic hardening
  - deterministic strict/permissive diagnostics
  - stable `ERROR` placement and parse continuation assertions

## Command Sequence
1. `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py tests/test_cst_red.py`
2. Implement Phase 4 only.
3. `uv run ruff check tests jominipy`
4. `uv run pyrefly check`
5. Re-run targeted tests, then full parser/lexer/ast/cst-red suite.

## Supersedes
- `docs/archive/HANDOFF_HISTORY_2026-02.md` for earlier phase logs.

