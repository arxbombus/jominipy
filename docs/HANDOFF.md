# Handoff

## Doc Ownership
- `docs/HANDOFF.md`: current execution state only (latest validated status + exact next commands).
- `docs/archive/HANDOFF_HISTORY_2026-02.md`: historical phase logs and older handoff details.
- `docs/ARCHITECTURE.md`: stable architecture/invariants, not day-to-day status churn.
- `docs/NEXT_AGENT_ROADMAP.md`: forward implementation plan and phase sequencing.

## Current State (as of 2026-02-07)
- Parser/CST pipeline is stable and unchanged during AST phases.
- AST phases 1-5 are complete:
  - block/list coercion utilities
  - scalar interpretation hardening
  - red CST wrappers + lowering migration
  - recovery/diagnostic hardening with deterministic assertions
  - AST consumer follow-on views (`AstBlockView`) and dedicated consumer tests
- Last validation snapshot:
  - `uv run pytest -q tests/test_ast_views.py tests/test_ast.py` (`72 passed`)
  - `uv run ruff check tests jominipy docs` (passed)
  - `uv run pyrefly check` (`0 errors`)
  - `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py tests/test_cst_red.py tests/test_ast_views.py` (`228 passed`)

## AST Consumer Follow-on landed details
- Added `jominipy/ast/views.py`:
  - `AstBlockView` explicit accessors: `as_object`, `as_multimap`, `as_array`
  - scalar helper accessors: `get_scalar`, `get_scalar_all`
  - scalar helpers delegate to `interpret_scalar` and preserve quoted-default non-coercion
- Added `tests/test_ast_views.py`:
  - object/array/mixed/empty view behavior
  - repeated-key `modifier` ordering and last-write-wins parity
  - quoted vs unquoted scalar helper behavior
  - deterministic handling for mixed/non-scalar/missing keys
  - central-case parity/debug pass: `test_ast_views_runs_all_central_cases` over `ALL_JOMINI_CASES`
- Refocused `tests/test_ast.py` to core lowering/model semantics by moving consumer-specific assertions to `tests/test_ast_views.py`.
- Parser/CST stack unchanged in this phase.
- Improved AST-view debug readability in `tests/_debug.py`:
  - structured shape/view sections
  - compact value renderers
  - source printed once per central-case run with path-labeled block dumps

## Next Task
- Immediate next step: implement parse-result carrier ergonomics (Biome `Parse<T>`-style API shape) over current parse/lower outputs.
- After carrier lands, start consumer integration parity work over one shared parse/lower lifecycle:
  - add parse-result carrier ergonomics for downstream consumers
  - consume `AstBlockView` from downstream tool entrypoints
  - keep parser/CST behavior unchanged
  - preserve explicit, deterministic coercion boundaries

## Design Expansion Required (do before broad implementation)
The following topics were discussed and must be deeply expanded in design docs/notes before full implementation:
1. Linter architecture:
   - rule API, diagnostics model, deterministic execution ordering
   - domain/schema rules (e.g. required `start_year`) as lint/semantic validation concerns
2. Type checker architecture:
   - type fact model and single-pass fact generation from AST
   - boundary: type constraints (type checker) vs policy/required-field constraints (linter)
3. Formatter architecture:
   - CST/trivia source-of-truth guarantees and idempotence criteria
   - integration over shared parse-result carrier without duplicated parsing
4. CWTools rules parser architecture:
   - dedicated parser for CWTools DSL (`references/hoi4-rules/Config`)
   - normalized IR/conversion pipeline while keeping upstream CWTools files as canonical source
   - semantic resolution layer for aliases/enums/scope/cardinality

## Biome practical findings (for next agent)
- Biome composes tools around a shared parse result and typed consumer layer:
  - parse carrier: `biome_js_parser::Parse<T>` (`parse.rs`)
  - typed surface: generated syntax wrappers in `biome_js_syntax`
  - linter entry: `biome_js_analyze::{analyze, analyze_with_inspect_matcher}`
  - formatter entry: `biome_js_formatter::format_node` + `FormatNodeRule`
  - orchestration: `biome_service` JS file handler calls parser/analyzer/formatter in one lifecycle
- jominipy equivalent already landed for this phase:
  - thin AST consumer surface over canonical AST in `ast/views.py`
  - CST and parser unchanged
  - hidden coercion avoided via explicit view methods

## Proposed implementation sequence (next agent)
1. Add parse-result carrier APIs for consumer tooling (Biome `Parse<T>`-style ergonomics over existing parse/lower outputs).
2. Expand design notes for linter/type-checker/formatter/rules-parser boundaries and ownership before broad implementation.
3. Wire linter entrypoints to consume one parse/lower result + AST views.
4. Wire formatter entrypoints to consume typed views while keeping CST as formatting source-of-truth.
5. Add integration tests that prove no duplicate structural interpretation between tool entrypoints.
6. Update parity + handoff docs after landing.

## Command Sequence
1. `uv run pytest -q tests/test_lexer.py tests/test_parser.py tests/test_ast.py tests/test_cst_red.py`
2. `uv run pytest -q tests/test_ast_views.py tests/test_ast.py`
3. `uv run ruff check tests jominipy docs`
4. `uv run pyrefly check`
5. Re-run full parser/lexer/ast/cst-red suite.

## Supersedes
- `docs/archive/HANDOFF_HISTORY_2026-02.md` for earlier phase logs.
