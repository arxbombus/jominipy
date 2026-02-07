# Next Agent Roadmap (Post-AST v1)

This roadmap is implementation-first and ordered to minimize rework.

## Current baseline (already landed)
- Lexer/parser/CST pipeline is stable and Biome-style.
- AST v1 exists (`jominipy/ast/model.py`, `jominipy/ast/scalar.py`, `jominipy/ast/lower.py`) and lowers from CST.
- Centralized cross-pipeline cases and debug helpers are in place under `tests/`.

## Phase 1: AST block/list coercion and repeated-key policy (completed)
Goal: make AST ergonomic for Jomini data access while preserving CST truth.

Deliverables:
1. Add block-shape classification helpers on `AstBlock`:
   - object-like: all statements are `AstKeyValue`
   - array-like: all statements are non-`AstKeyValue` values
   - mixed: contains both key-values and values
   - empty-ambiguous: no statements
2. Add derived coercion helpers (no parser changes):
   - `to_object(multimap=False)` returns key -> last value (default)
   - `to_object(multimap=True)` returns key -> list[value]
   - `to_array()` returns ordered value list for array-like blocks
3. Define repeated-key behavior explicitly:
   - Preserve lexical order in canonical AST always.
   - For object coercion:
     - default map policy: last-write-wins
     - multimap policy: collect repeated keys into ordered arrays
   - Example:
     - `modifier={...}` repeated twice under one object
     - `multimap=True` => `"modifier": [AstBlock(...), AstBlock(...)]`
     - default map => `"modifier": AstBlock(...)` (second one)

Tests:
- New AST tests for object-like/array-like/mixed/empty blocks.
- New tests for repeated key coercion (`modifier`) and stable order.
- Keep existing parser/CST output unchanged.

Status:
- Implemented on `AstBlock` in `jominipy/ast/model.py`:
  - shape helpers: `is_object_like`, `is_array_like`, `is_mixed`, `is_empty_ambiguous`
  - coercion helpers: `to_object(multimap=False)`, `to_object(multimap=True)`, `to_array()`
- Added AST tests for shape/coercion/repeated-key behavior in `tests/test_ast.py`.
- Canonical AST remains order-preserving and unchanged; coercion remains derived-view only.

## Phase 2: Scalar interpretation policy hardening (completed)
Goal: keep semantics explicit and non-destructive.

Deliverables:
1. Formal API for scalar interpretation:
   - bool, int/float, date-like, and unknown
2. Quoted behavior:
   - quoted scalar does not coerce by default
   - optional opt-in coercion mode for consumers
3. Ambiguity handling:
   - document precedence and non-coercion cases (`yes`, `1821.1.1`, large ints, signs)

Tests:
- Add table-driven scalar interpretation tests, including quoted/unquoted contrast and very large integers.

Status:
- Implemented in `jominipy/ast/scalar.py`:
  - explicit scalar kind model: `ScalarKind` (`unknown`, `bool`, `number`, `date_like`)
  - formal interpretation result model with explicit `kind`, `value`, and compatibility fields
  - deterministic interpretation precedence and explicit unknown handling
  - quoted scalar policy: no coercion by default, optional opt-in via `allow_quoted=True`
- Added table-driven scalar interpretation tests in `tests/test_ast.py`:
  - bool/number/date/unknown coverage
  - quoted default vs opt-in coercion coverage
  - large integer and sign handling coverage

## Phase 3: Red CST wrappers (Biome parity priority)
Goal: stop doing manual green-tree walking in high-level code.

Deliverables:
1. Add red wrappers for nodes/tokens:
   - navigation: parent/children/siblings/token iteration
   - text/trivia accessors
2. Port AST lowering to red wrappers instead of direct `GreenNode` tree scans.

Tests:
- Navigation/text/trivia correctness tests.
- AST parity tests before/after port (no behavior changes).

## Phase 4: Recovery/diagnostic hardening
Goal: robust parse under malformed real-world input.

Deliverables:
1. Expand malformed fixtures and expected diagnostics.
2. Assert:
   - `ERROR` node placement is stable
   - parse continues after error
   - diagnostics stay deterministic in strict/permissive modes

## Phase 5: Docs and parity governance
Goal: keep architecture and parity docs accurate after each phase.

Deliverables each phase:
1. Update `docs/ARCHITECTURE.md` status and next-step bullets.
2. Update `docs/BIOME_PARITY.md` row statuses + rationale.
3. Keep `docs/EDGE_CASES_FAILURE.md` synchronized with tests/contracts.
4. Add a short handoff section in `docs/HANDOFF.md` with exact next command sequence.

## Suggested command sequence for next agent
1. `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py`
2. Implement one phase only (start with Phase 3).
3. `uv run ruff check tests jominipy`
4. Re-run targeted tests for changed modules, then full test trio again.
