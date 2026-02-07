# Handoff History (2026-02)

This file archives historical progress notes that were previously in `docs/HANDOFF.md`.
Current operational handoff now lives in `docs/HANDOFF.md`.

## 2026-02-07: AST v1 and Follow-on Phases

### AST v1 landed
- Implemented:
  - `jominipy/ast/model.py`
  - `jominipy/ast/scalar.py`
  - `jominipy/ast/lower.py`
  - `jominipy/ast/__init__.py`
- Centralized test helpers:
  - `tests/_shared_cases.py`
  - `tests/_debug.py`
- Validation snapshot: `206 passed` across lexer/parser/ast tests.

### Phase 1 complete: AST block/list coercion
- `AstBlock` shape helpers: `is_object_like`, `is_array_like`, `is_mixed`, `is_empty_ambiguous`
- Coercion helpers: `to_object(multimap=False)`, `to_object(multimap=True)`, `to_array()`
- Repeated-key policy retained as derived-view behavior only.
- Validation snapshot: `209 passed`.

### Phase 2 complete: scalar interpretation hardening
- Explicit scalar kinds: `unknown`, `bool`, `number`, `date_like`
- Quoted scalar default: non-coercing unless opt-in.
- Deterministic interpretation precedence and unknown handling.
- Validation snapshot: `218 passed` + Ruff clean.

### Phase 3 complete: red CST wrappers + AST lowering migration
- Implemented `jominipy/cst/red.py` wrappers:
  - `SyntaxNode` / `SyntaxToken` navigation and query API
  - token text/trivia accessors
- Exported wrappers in `jominipy/cst/__init__.py`.
- AST lowering migrated to wrappers in `jominipy/ast/lower.py`.
- Added wrapper tests in `tests/test_cst_red.py`.
- Validation snapshot: `220 passed` + Ruff clean.

### Stable policies recorded in this period
- Canonical AST remains source-ordered and non-coercive.
- Repeated key handling:
  - canonical AST: keep repeated `AstKeyValue` entries
  - derived object view: last-write-wins
  - derived multimap view: ordered list of repeated entries
- Parser/CST contracts unchanged during AST phases.

