# Next Agent Roadmap (Post-AST v1)

This roadmap is implementation-first and ordered to minimize rework.

## How to read this roadmap
- `Phase 0` + `Phase 1 Status` are the active rollout track for current implementation.
- `Foundation Milestones A-F` are completed historical milestones that remain important reference material.
- Use `docs/RULES_SYNTAX.md` checklist as the active execution order for CWTools rule semantics work.

## Current baseline (already landed)
- Lexer/parser/CST pipeline is stable and Biome-style.
- AST v1 exists (`jominipy/ast/model.py`, `jominipy/ast/scalar.py`, `jominipy/ast/lower.py`) and lowers from CST.
- Centralized cross-pipeline cases and debug helpers are in place under `tests/`.
- Parse-result carrier API is implemented:
  - `jominipy/pipeline/result.py` (`ParseResultBase`, `JominiParseResult`)
  - `jominipy/pipeline/results.py` (`LintRunResult`, `FormatRunResult`, `CheckRunResult`)
  - `jominipy/parser/jomini.py` (`parse_result(...)`)

## Phase 0: Planning Gate (completed)
Goal: produce a detailed, Biome-aligned project plan before broad subsystem implementation.

Authoritative deliverables (full proposal):
1. Ownership and subsystem boundaries:
   - parser/CST/AST ownership and invariants
   - linter responsibilities (policy/style/domain diagnostics)
   - type-checker responsibilities (type/scope/value-constraint diagnostics)
   - formatter responsibilities (CST/trivia-preserving emission)
   - rules-parser responsibilities (rules DSL to normalized rule IR)
2. Public API contracts (design-level, before broad implementation):
   - parse carriers: `ParseResultBase`, `JominiParseResult`, planned `RulesParseResult`
   - entrypoints: `run_check`, `run_lint`, `run_format`, planned `run_typecheck`
   - diagnostics contract: severity/category/code consistency and de-dup rules
   - rule result/fix contract: deterministic and machine-applicable edit model
3. Rule engine architecture:
   - deterministic execution ordering and phase separation
   - rule taxonomy:
     - semantic/domain rules (required fields, schema/policy constraints)
     - style/layout rules (ordering, multiline/list formatting policy)
   - profile/configuration model and enable/disable mechanics
4. Autofix architecture:
   - edit payload and application model
   - safety criteria: syntax-safe, trivia/comment-safe, range-safe
   - idempotence requirements and explicit no-fix fallback
5. Type-check architecture and coexistence model:
   - shared fact pipeline produced once per parse lifecycle
   - checker independent from linter execution
   - linter allowed to consume type facts (one-way dependency)
6. Formatter architecture:
   - decision layer (AST/views/facts) vs emission layer (CST/tokens/trivia)
   - idempotence and comment/trivia preservation criteria
   - alignment with lint style rules and conflict-resolution policy
7. Rules DSL parser and generation architecture:
   - parse CWTools-like DSL into normalized IR
   - semantic resolution layer (aliases/enums/scope/cardinality)
   - generation outputs: models/validators/selectors/adapters
   - versioning/update model per game/ruleset
8. Test strategy matrix:
   - unit tests per subsystem
   - integration tests for one-parse-lifecycle guarantees
   - parity tests against Biome-aligned contracts
   - idempotence tests (formatter and autofix)
   - regression fixtures for diagnostics stability
9. Risk register and mitigation:
   - parse duplication risk -> enforce parse carrier injection pathways
   - nondeterministic rule ordering -> canonical registry ordering + tests
   - trivia/comment corruption -> CST-first edit application + guarded fixes
   - semantic/style overlap risk -> explicit engine ownership and namespaces
10. Stop/Go gates:
   - required evidence to exit Phase 0
   - required evidence to start each subsystem phase (lint, format, typecheck, rules-parser)

Named API direction (approved):
- Game-script carrier remains Jomini-specific: `JominiParseResult`.
- Shared cross-domain behavior remains generic: `ParseResultBase`.
- Rules parser carrier will be separate: `RulesParseResult`.
- No compatibility aliases are required for this project; direct renames are acceptable.

Constraints:
- No broad subsystem implementation during this planning gate.
- Biome parity is a hard requirement, not a best-effort target.

Phase 0 exit criteria (must all be true):
1. This document defines all 10 deliverables above with enough detail to implement without re-litigating boundaries.
2. `docs/BIOME_PARITY.md` maps each planned subsystem to concrete Biome references.
3. `docs/ARCHITECTURE.md` reflects boundary invariants and planning-gate enforcement.
4. `docs/HANDOFF.md` points to planning-only next step and explicitly blocks broad subsystem coding.
5. Memory/handoff state is updated to reflect this proposal as canonical latest planning state.

Status:
- Completed on 2026-02-07.
- Phase 0 proposal package is now the canonical planning baseline.
- Next step is Phase 1 execution kickoff (lint engine core) under the defined gates.

## Phase 0 Execution Order (approved)
1. Lint engine core (registry, deterministic ordering, first semantic + style rules).
2. Formatter pipeline core (CST-first emission + idempotence harness).
3. Type-checker fact model + checker diagnostics.
4. Rules DSL parser + normalized IR + generation pipeline.
5. Integration and parity hardening.

## Phase 1 Status (in progress)
- Landed:
  - shared facts cache on parse carrier (`JominiParseResult.analysis_facts`)
  - separate type-check runner scaffold (`jominipy/typecheck/runner.py`)
  - deterministic lint rule registry scaffold with semantic/style split (`jominipy/lint/rules.py`)
  - entrypoint orchestration update: `run_typecheck(...)` and `run_check(...)` compose typecheck + lint over one parse
  - validation coverage: `tests/test_lint_typecheck_engines.py`
- Next:
  - follow the checklist in `docs/RULES_SYNTAX.md` (`Implementation Checklist (jominipy status)`) as execution order.
  - complete lower-complexity typed checks first:
    - primitive range enforcement (`int[...]`, `float[...]`)
    - additional simple primitive families (`date_field`, `percentage_field`, etc.)
  - then add resolved-reference checks over indexed schema data:
    - enum membership (`enum[...]`)
    - type references (`<type_key>` and related forms)
    - scope-reference validation (`scope[...]`, `push_scope`, `replace_scope`)
  - keep correctness checks migrating toward typecheck ownership; keep lint focused on policy/style/heuristics.

## Phase 1.1: Rules Parity Execution Plan (2026-02-08, approved proposal)
Goal: implement CWTools rules semantics with explicit Biome-style ownership boundaries and one shared parse lifecycle.

Execution phases (ordered):
1. Schema graph foundation (landed):
   - add full cross-file rules schema graph/index (enums, types, aliases, single_alias, scope metadata, value/value_set).
   - remove single-file dependency on `common/technologies.cwt` as the only schema source.
2. Nested analysis facts:
   - extend shared analysis facts to include nested object/field facts with stable source ranges.
   - keep fact generation single-pass and parse-lifecycle cached.
3. Typecheck correctness expansion (primary ownership):
   - migrate hard correctness checks from lint into typecheck.
   - implement primitive/range correctness (`int[min..max]`, `float[min..max]`, and additional primitive families such as `date_field`/`percentage_field`/variable-value variants).
4. Resolved-reference correctness:
   - enforce `enum[...]` membership.
   - enforce `<type_key>` (including prefixed/suffixed forms) against resolved type declarations.
   - enforce `scope[...]` with scope-stack transitions from `push_scope`/`replace_scope`.
5. Advanced CWTools semantics:
   - wire alias/single-alias expansion, subtype-conditional application, and special-file semantics (`scopes.cwt`, `links.cwt`, `modifiers.cwt`, `values.cwt`, `localisation.cwt`).

Phase 1.1 progress:
- Completed: Phase A schema graph foundation (`jominipy/rules/schema_graph.py`) and semantic-loader wiring to cross-file HOI4 config graph.
- Completed: Phase B nested analysis facts (`jominipy/analysis/facts.py`) with deterministic object/field path + occurrence indexing.
- Completed (initial): Phase C primitive/range correctness in typecheck (`jominipy/typecheck/rules.py`) with lint/typecheck ownership migration for field-type constraints.
- Completed (additional): registry-backed `filepath`/`icon` validation contract via `AssetRegistry` (`jominipy/typecheck/assets.py`) and typecheck integration.
- Next: finish tighter variable/value reference semantics, then Phase D resolved-reference correctness checks (prioritize `<spriteType>` membership for HOI4 icon fields before direct icon-filename assumptions).

Boundary constraints (must remain true):
- `typecheck` owns correctness diagnostics (`TYPECHECK_*`, `domain=correctness`, `confidence=sound`).
- `lint` owns policy/style/heuristic diagnostics (`LINT_*`).
- `lint` may consume type facts; typecheck must not depend on lint execution.

## Phase 1 Boundary Contracts (completed)
- checker rule contracts are enforced mechanically:
  - domain must be `correctness`
  - confidence must be `sound`
  - code prefix must be `TYPECHECK_`
- lint rule contracts are enforced mechanically:
  - domain must be `semantic`, `style`, or `heuristic`
  - confidence must be `policy` or `heuristic`
  - code prefix must be `LINT_`
- runners validate contracts before rule execution.

## Foundation Milestone A (completed): AST block/list coercion and repeated-key policy
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

## Foundation Milestone B (completed): Scalar interpretation policy hardening
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

## Foundation Milestone C (completed): Red CST wrappers (Biome parity priority)
Goal: stop doing manual green-tree walking in high-level code.

Deliverables:
1. Add red wrappers for nodes/tokens:
   - navigation: parent/children/siblings/token iteration
   - text/trivia accessors
2. Port AST lowering to red wrappers instead of direct `GreenNode` tree scans.

Tests:
- Navigation/text/trivia correctness tests.
- AST parity tests before/after port (no behavior changes).

Status:
- Implemented red wrappers in `jominipy/cst/red.py`:
  - `SyntaxNode` / `SyntaxToken` wrappers
  - parent/children/sibling navigation
  - descendant token iteration
  - token text/trivia accessors (`text_with_trivia`, `text_trimmed`, leading/trailing trivia text)
- Exported wrappers via `jominipy/cst/__init__.py`.
- Ported AST lowering to red wrappers in `jominipy/ast/lower.py`:
  - added `lower_syntax_tree(...)`
  - `parse_to_ast(...)` and `lower_tree(...)` now lower through red wrappers
- Added red-wrapper tests in `tests/test_cst_red.py`.

## Foundation Milestone D (completed): Recovery/diagnostic hardening
Goal: robust parse under malformed real-world input.

Deliverables:
1. Expand malformed fixtures and expected diagnostics.
2. Assert:
   - `ERROR` node placement is stable
   - parse continues after error
   - diagnostics stay deterministic in strict/permissive modes

Status:
- Added malformed edge fixtures in `tests/_shared_cases.py`:
  - `edge_case_recovery_between_valid_statements`
  - `edge_case_missing_value_then_invalid_operator`
- Added deterministic parser assertions in `tests/test_parser.py`:
  - top-level `ERROR` node placement is stable between valid statements
  - strict/permissive warning diagnostics assert exact code/severity/category
  - duplicate diagnostics at the same token start are suppressed
- Biome parity alignment:
  - parser diagnostic de-duplication at same position now matches Biome behavior.

## Foundation Milestone E (completed): AST consumer follow-on
Goal: actively consume Phase 1 model aliases in downstream AST APIs.

Deliverables:
1. Add `jominipy/ast/views.py` as consumer/query surface over `AstBlock` coercions.
2. Expose typed helpers that return:
   - `AstObject` / `AstObjectMultimap` for object views
   - `list[AstArrayValue]` for array views
3. Add tests (e.g. `tests/test_ast_views.py`) covering:
   - object/array/mixed/empty classification and coercion
   - repeated-key multimap behavior
   - quoted vs unquoted scalar interpretation through consumer helpers

Constraints:
- No parser/CST behavior changes.
- Canonical AST ordering stays source-of-truth; all object/array forms remain derived views.
- Keep Biome parity boundaries explicit in `docs/BIOME_PARITY.md`.

Biome-practical implementation guidance:
1. Mirror Biome layering, not Biome syntax:
   - keep one parse/lower pipeline and build consumer views on top (similar intent to Biome `Parse<T>` + typed wrappers).
2. Avoid hidden coercion:
   - offer explicit view calls (`as_object()`, `as_multimap()`, `as_array()`) rather than implicit property mutation.
3. Keep views lightweight:
   - no deep copies unless required; preserve references to canonical AST nodes where feasible.
4. Make diagnostics/tooling-friendly outputs:
   - consumer helpers should return deterministic empty/None/error states for mixed/ambiguous shapes.
5. Prepare for future linter/formatter integration:
   - consumer API should be safe for repeated use from multiple tools without side effects.

Status:
- Implemented `jominipy/ast/views.py` with `AstBlockView`:
  - explicit `as_object()`, `as_multimap()`, `as_array()` accessors
  - scalar helper accessors (`get_scalar`, `get_scalar_all`) that delegate to `interpret_scalar` and preserve quoted-default behavior unless `allow_quoted=True`
- Added `tests/test_ast_views.py` for:
  - shape/view selection across object/array/mixed/empty blocks
  - repeated-key `modifier` multimap ordering and last-write-wins object view
  - quoted vs unquoted scalar helper behavior
  - deterministic mixed/non-scalar behavior contracts
- Added central-case view coverage and debug output pathing:
  - `test_ast_views_runs_all_central_cases` (over `ALL_JOMINI_CASES`)
  - readable, path-labeled AST view dumps via `tests/_debug.py`
- Kept parser/CST behavior unchanged.
- Kept `tests/test_ast.py` focused on core lowering/model semantics and moved consumer view assertions into `tests/test_ast_views.py`.
- Updated docs (`ARCHITECTURE`, `BIOME_PARITY`, `HANDOFF`) to reflect parity and execution state.

## Foundation Milestone F (ongoing): docs and parity governance
Goal: keep architecture and parity docs accurate after each phase.

Deliverables each phase:
1. Update `docs/ARCHITECTURE.md` status and next-step bullets.
2. Update `docs/BIOME_PARITY.md` row statuses + rationale.
3. Keep `docs/EDGE_CASES_FAILURE.md` synchronized with tests/contracts.
4. Add a short handoff section in `docs/HANDOFF.md` with exact next command sequence.
5. Run agent closeout protocol for memories:
   - update `handoff_current` pointer
   - maintain timestamped `LATEST`/`ARCHIVED` handoff memory naming
   - refresh `reference_map` when implementation references change
   - keep `task_completion` checklist current

## Suggested command sequence for next agent
1. `uv run pytest -q tests/test_parse_result.py tests/test_parser.py tests/test_ast.py tests/test_ast_views.py`
2. `uv run pytest -q tests/test_lexer.py tests/test_cst_red.py tests/test_parse_result.py tests/test_parser.py tests/test_ast.py tests/test_ast_views.py`
3. Produce the planning-gate output (detailed phases + parity mapping + risk/test strategy).
4. `uv run ruff check tests jominipy docs`
5. `uv run pyrefly check`

## Design Expansion Required Before Implementation
The topics below are intentionally marked as **design-first** and must be expanded by subsequent agents before large implementation work:

1. Parse result carrier API (next concrete step):
   - define one reusable analysis carrier (Biome `Parse<T>`-style ergonomics) that bundles parse/lower artifacts and diagnostics
   - define lifecycle ownership and caching policy (parse once, lower once, consume many)
   - define stable public API surface for CLI/linter/formatter/type-checker consumers

2. Linter architecture:
   - define rule API, diagnostic model, and rule execution ordering
   - define how linter consumes AST views and (future) type facts without re-parsing
   - define game/domain rule packaging sourced from CWTools metadata (required fields/cardinality/scope)

3. Type checker architecture:
   - define semantic/type fact model and how facts are produced from AST once
   - define boundary between type errors (value/type constraints) and lint/domain violations (required fields/policy)
   - define integration with linter to avoid duplicate traversal and duplicate diagnostics

4. Formatter architecture:
   - define formatter entrypoint over shared parse result while preserving CST/trivia as output source-of-truth
   - define style/options model and deterministic/idempotent formatting guarantees
   - define relationship between AST views (decision support) and CST token emission (final output)

5. CWTools rules parser + converter architecture:
   - define separate grammar pipeline for CWTools rule DSL (`references/hoi4-rules/Config`) rather than forcing game-data grammar reuse
   - define normalized IR format for parsed rules (recommended generated artifact, not source-of-truth replacement)
   - define semantic resolution pass for aliases/enums/scope/cardinality and integration with linter/type-check layers
   - define versioning/update workflow so upstream maintained CWTools rules remain canonical input

## Additional expansion topics from current discussion (future agents)
1. Linter engine taxonomy:
   - separate rule groups for semantic/domain vs style/layout.
   - examples to support:
     - required field rules derived from CWTools cardinality metadata
     - style rules (array/list must be multiline)
     - configurable field-order rules (for example: `path`, `research_cost`, ...)

2. Autofix contracts:
   - define fix payload model and application semantics
   - deterministic/idempotent/syntax-safe/trivia-safe requirements
   - explicit no-fix fallback when safe fix cannot be guaranteed

3. Type checker coexistence with linter:
   - shared fact pipeline, separate engines
   - linter may consume type facts; checker must not depend on lint execution

4. Developer-facing Pythonic API:
   - expose simple typed objects for common entities (dataclass/Pydantic strategy)
   - support manipulations/additions/deletions through CST-safe transaction/edit layer
   - avoid direct object->text serialization that discards trivia/comments

5. Code generation strategy:
   - generate models, validators, enums, selectors, and CST mapping adapters from canonical schema IR
   - support strict typed mode + unknown/dynamic fallback for mods/custom fields
   - version models per game/ruleset and keep generated artifacts non-hand-edited
