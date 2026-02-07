# Handoff

## Doc Ownership
- `docs/HANDOFF.md`: current execution state only (latest validated status + exact next commands).
- `docs/archive/HANDOFF_HISTORY_2026-02.md`: historical phase logs and older handoff details.
- `docs/ARCHITECTURE.md`: stable architecture/invariants, not day-to-day status churn.
- `docs/NEXT_AGENT_ROADMAP.md`: forward implementation plan and phase sequencing.

## Agent Update Protocol (required at task end)
Every agent must perform this checklist before finishing a substantive task:
1. Update docs that changed in meaning:
   - `docs/HANDOFF.md` for current state/next step/validation
   - `docs/BIOME_PARITY.md` for parity status/deviations
   - `docs/ARCHITECTURE.md` only if architectural invariants or boundaries changed
   - `docs/NEXT_AGENT_ROADMAP.md` for phase sequencing changes
2. Update memories:
   - `handoff_current` must point to the canonical latest timestamped handoff memory
   - `reference_map` if implementation references changed
   - `task_completion` if completion checklist changed
3. Create/refresh a timestamped handoff memory for major progress:
   - Naming format (required):
     - `handoff_YYYY-MM-DDTHH-MM-SSZ_<scope>_<status>`
   - Required status suffix:
     - `LATEST` for canonical current
     - `ARCHIVED` for historical snapshots
4. Keep exactly one canonical latest handoff memory at a time:
   - `handoff_current` must explicitly name it.
   - Previous latest handoff must be marked `ARCHIVED` or removed if redundant.
5. Validation evidence must be recorded in handoff doc/memory:
   - exact commands and pass/fail results.

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
- Parse-result carrier phase is now implemented:
  - `jominipy/pipeline/result.py`: `ParseResultBase`, `JominiParseResult`
  - `jominipy/pipeline/results.py`: `LintRunResult`, `FormatRunResult`, `CheckRunResult`
  - `jominipy/parser/jomini.py`: new `parse_result(...)` entrypoint
  - `jominipy/parser/__init__.py`: exports `parse_result`
- Planning-gate drafting has started in docs:
  - `docs/NEXT_AGENT_ROADMAP.md` now includes concrete scaffold/API contracts and Phase 0 acceptance criteria.
  - `docs/BIOME_PARITY.md` now includes planning-gate parity targets and parse-carrier naming/domain boundary policy.
- Pipeline scaffold draft has landed (no real lint/format rules yet):
  - `jominipy/pipeline/entrypoints.py`: `run_check`, `run_lint`, `run_format`
  - `jominipy/lint/runner.py`: lint runner skeleton over shared parse lifecycle
  - `jominipy/format/runner.py`: formatter runner skeleton over shared parse lifecycle
  - `tests/test_pipeline_entrypoints.py`: lifecycle and contract coverage
- Phase 1 execution kickoff landed (engine core + initial scaffolds):
  - shared facts cache on parse carrier: `JominiParseResult.analysis_facts()`
  - separate type-check engine scaffold: `jominipy/typecheck/*`
  - deterministic lint rule registry scaffold consuming type facts: `jominipy/lint/rules.py`
  - pipeline entrypoint added: `run_typecheck(...)` and `run_check(...)` now composes typecheck + lint with dedupe
  - validation tests added: `tests/test_lint_typecheck_engines.py`
- Boundary refinement from latest planning discussion:
  - type checker is reserved for high-confidence correctness diagnostics
  - linter is reserved for static analysis policy, semantics, style, and heuristics
  - linter may consume type facts, but checker must remain independent from lint rules
  - next implementation step is to enforce this boundary mechanically (rule metadata/contracts + tests), not just by convention
- Boundary enforcement landed:
  - `jominipy/typecheck/rules.py`: type-check rule contract now enforces `domain=correctness`, `confidence=sound`, `TYPECHECK_` code prefix
  - `jominipy/lint/rules.py`: lint rule contract now enforces `domain in {semantic, style, heuristic}`, `confidence in {policy, heuristic}`, `LINT_` code prefix
  - runners validate contracts before execution:
    - `jominipy/typecheck/runner.py`
    - `jominipy/lint/runner.py`
  - boundary tests added:
    - `tests/test_lint_typecheck_engines.py` (invalid-domain/confidence rejection)
- CWTools rules read-only ingest (no engine wiring) landed:
  - new package: `jominipy/rules/*`
    - `result.py`: `RulesParseResult` (separate carrier domain from `JominiParseResult`)
    - `parser.py`: parse `.cwt` text/files and lower to statement IR with comment metadata
    - `ir.py`: normalized rule IR dataclasses
    - `normalize.py`: deterministic category indexing over parsed statements
    - `load.py`: directory/path loaders for `.cwt` inputs
  - tests:
    - `tests/test_rules_ingest.py` (comment options/docs attachment + HOI4 sample ingest/indexing)
- Implementation status adjustment:
  - implementation work is now paused
  - current focus is completing the full Phase 0 proposal and gating criteria across docs/memories
- Validation snapshot after carrier work:
  - `uv run pytest -q tests/test_parse_result.py tests/test_parser.py tests/test_ast.py tests/test_ast_views.py` (`217 passed`)
  - `uv run pytest -q tests/test_lexer.py tests/test_cst_red.py tests/test_parse_result.py tests/test_parser.py tests/test_ast.py tests/test_ast_views.py` (`286 passed`)
  - `uv run ruff check tests jominipy docs` (passed)
  - `uv run pyrefly check` (`0 errors`)

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

## Next Task (post-Phase-0 kickoff)
- Phase 0 planning gate is complete.
- Immediate next step: start Phase 1 execution (lint engine core) under the approved proposal constraints.
- Immediate next step: replace scaffold rules with CWTools-derived rule IR consumers under the enforced lint/checker contracts.
- Immediate next step: map `jominipy/rules` normalized IR into lint/type-check rule registries while preserving one parse/facts lifecycle and domain contracts.
- Phase 1 kickoff scope:
  1. deterministic lint rule registry and execution ordering
  2. first semantic/domain rule (`start_year` required for HOI4 technology objects)
  3. first style/layout rules (multiline list/array + configurable field order)
  4. keep one-parse-lifecycle invariant via `JominiParseResult`
- Biome parity remains a hard architectural constraint during implementation.
- Naming boundary decision is now explicit:
  - game-script carrier is explicitly `JominiParseResult`
  - shared carrier behavior is `ParseResultBase` for reuse by non-game-specific pipelines
  - future rules DSL must use a distinct carrier (`RulesParseResult`)

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

5. Linter rule categories and autofix model:
   - separate semantic/domain rules vs style/layout rules
   - define autofix contracts (deterministic, idempotent, syntax-safe, trivia/comment-safe)
   - include configurable rules (example: field-order rules per object type/profile)

6. Type checker and linter coexistence:
   - shared analysis/fact pipeline, separate execution engines and rule namespaces
   - allow linter rules to consume type facts; prevent checker depending on lint rules

7. Developer API and generated typed models:
   - evaluate generated dataclass/Pydantic model surfaces over schema IR
   - define CST/AST-to-model mapping and model-to-edit mapping (round-trip safe)
   - require transaction/edit layer rather than naive dict->text serialization

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
1. Planning gate: produce detailed design docs and phased execution plan (no broad feature implementation yet).
2. Wire entrypoint scaffolds over existing carriers:
   - `pipeline/entrypoints.py`
   - `lint/runner.py` scaffold
   - `format/runner.py` scaffold
3. Implement lint analyzer/rule engine with deterministic ordering and configurable rule profiles.
4. Implement formatter rule pipeline with CST/trivia source-of-truth and idempotence guarantees.
5. Implement type-checker over shared facts with clear ownership boundary vs lint.
6. Design and stage generated Pythonic model/edit API over schema IR.
7. Add integration tests proving single parse/lower lifecycle reuse and parity invariants.
8. Update parity + handoff docs after each phase.

## Command Sequence
1. `uv run pytest -q tests/test_pipeline_entrypoints.py tests/test_parse_result.py tests/test_parser.py tests/test_ast.py tests/test_ast_views.py`
2. Implement Phase 1 lint engine core over existing scaffolds.
3. `uv run ruff check tests jominipy docs`
4. `uv run pyrefly check`
5. Update parity + handoff docs and memories after Phase 1 milestone.

## Supersedes
- `docs/archive/HANDOFF_HISTORY_2026-02.md` for earlier phase logs.
