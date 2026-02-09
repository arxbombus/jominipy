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

## Quick Read (Operational)
- Active workstream: CWTools rules ingest -> normalized IR -> typed semantic enforcement.
- Current sequencing source of truth: `docs/RULES_SYNTAX.md` -> `Implementation Checklist (jominipy status)`.
- Critical architectural constraint:
  - keep Biome-style staged architecture; do not switch to CWTools runtime architecture.
  - CWTools is semantic source, not execution-model source.
- Immediate implementation order:
  1. alias/single-alias semantic expansion + validation wiring
  2. subtype gating/materialization + conditional rule application
  3. complex enum derivation pipeline
  4. special-file semantic providers (`links`, `modifiers`, `values`, `localisation`) and checker wiring
  5. localisation Stage 2: YAML localisation key existence/coverage indexing + checker wiring
- Test-suite structure update (2026-02-09):
  - `tests/test_lint_typecheck_engines.py` is now smoke/contract coverage only.
  - Typecheck parity coverage was split into focused modules:
    - `tests/typecheck/test_field_constraint_rules.py`
    - `tests/typecheck/test_reference_rules.py`
    - `tests/typecheck/test_localisation_rules.py`
    - `tests/typecheck/test_scope_rules.py`
    - `tests/typecheck/test_services_and_facts.py`
- Core invariants remain required:
  - one parse/facts lifecycle (`JominiParseResult`)
  - lint/typecheck boundary contracts
  - Biome parity tracking in `docs/BIOME_PARITY.md`

## Latest Parity Findings (2026-02-08)
- Scope work has improved materially:
  - alias-chain resolution now includes `this/root/from*/prev*`.
  - sibling/top-level scope isolation tests exist.
  - ambiguity detection exists for conflicting `replace_scope`.
- Full-surface parity gaps now clearly identified:
  - alias/single-alias execution semantics are now partially implemented (`single_alias_right` expansion + `alias_match_left` membership), but not end-to-end
  - subtype execution semantics are now partially implemented (deterministic subtype matcher gating), but not full CWTools parity
  - complex enum generation is now initially implemented (path/name-tree/start_from_root materialization), but not fully parity-hardened
  - special-file semantics are now partially integrated (`scopes` + `values` + `links` + initial `modifiers`/`localisation_commands` providers + localisation command/scope enforcement + advanced links chain semantics); advanced localisation parity remains
  - non-core option semantics (`comparison`, `error_if_only_match`, reference labels) are now wired
  - localisation parity remains pending and should be staged:
    - command/scope semantics from `localisation.cwt` first,
    - localisation YAML key-existence/coverage validation second.
- Compatibility note:
  - jominipy intentionally stays on Biome-style architecture and should add CWTools compatibility via semantic adapters only.
  - CWTools localisation validation is callback/service-driven at runtime (`processLocalisation`/`validateLocalisation`), while jominipy should keep precomputed adapter artifacts injected via services.

## Historical Landed State (through 2026-02-07)
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
- CWTools semantic metadata + declaration identity landed:
  - typed metadata normalization in `jominipy/rules/normalize.py`:
    - `cardinality`, `scope`, `push_scope`, `replace_scope`, `severity`, valueless flags
  - declaration path disambiguation for repeated keys:
    - `IndexedRuleStatement.declaration_path`
  - debug dump includes metadata + declaration path:
    - `tests/_debug.py` (`PRINT_RULES_IR=1`)
  - semantic extraction helper:
    - `jominipy/rules/semantics.py` (`build_required_fields_by_object`, `load_hoi4_required_fields`)
  - lint semantic rule migrated from hardcoded example policy to CWTools-derived required fields:
    - removed `start_year`-specific assumption
    - new diagnostic code: `LINT_SEMANTIC_MISSING_REQUIRED_FIELD`
- CWTools typed RHS extraction + first typed validation landed:
  - `jominipy/rules/semantics.py`:
    - `RuleValueSpec`, `RuleFieldConstraint`
    - `build_field_constraints_by_object(...)`, `load_hoi4_field_constraints(...)`
    - scalar RHS normalization for primitives (`int`, `float`, `bool`, `scalar`, `localisation*`) and refs (`enum[...]`, `scope[...]`, `value[...]`, `value_set[...]`, `<type>`)
  - lint rule added:
    - `SemanticInvalidFieldTypeRule` in `jominipy/lint/rules.py`
    - diagnostic code: `LINT_SEMANTIC_INVALID_FIELD_TYPE`
  - tests added/updated:
    - `tests/test_rules_ingest.py` field-constraint extraction test
    - `tests/test_lint_typecheck_engines.py` custom-schema type mismatch test
- CWTools syntax coverage checklist is now documented in `docs/RULES_SYNTAX.md` under `Implementation Checklist (jominipy status)`:
  - implemented: IR ingest/indexing + metadata normalization + required-field extraction + initial primitive checks
  - pending: primitive range enforcement, enum/type/scope resolution, value-set and alias wiring, subtype and special-file semantics, and typecheck ownership migration for correctness checks
- Historical note:
  - this pause state applied during earlier planning-gate work
  - current execution has resumed under the checklist-driven sequencing in `docs/RULES_SYNTAX.md`
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

## Current Next Task
- Phase 0 planning gate is complete.
- Phase 1.1 rules-parity execution plan was drafted and documented before implementation.
- Phase 1.1 Phase A (cross-file schema graph/index foundation) is now landed.
- Phase 1.1 Phase B (nested analysis facts for object fields) is now landed.
- Phase 1.1 Phase C (initial primitive/range correctness in typecheck + field-type correctness migration out of lint) is now landed.
- Phase 1.1 Phase C extension (registry-backed `filepath`/`icon` checks via `AssetRegistry`) is now landed.
- Phase 1.1 Phase D (initial alias/single-alias semantic adapter wiring) is now landed.
- Phase 1.1 Phase D2 (alias/single-alias execution parity expansion) is now landed:
  - adapter artifacts now include alias/single-alias definitions + invocation paths,
  - typecheck now executes alias/single-alias invocation validation against extracted rule constraints.
- Phase 1.1 Phase E (initial subtype gating/materialization) is now landed.
- Phase 1.1 Phase F (initial complex enum materialization) is now landed.
- Update (current): scope-context transition checks and scope-alias resolution (`this/root/from/fromfrom...` + `prev/prevprev...`) are landed in typecheck, including sibling-branch non-leakage and ambiguity diagnostics (`TYPECHECK_AMBIGUOUS_SCOPE_CONTEXT`).
- Phase 1.1 Phase G (initial special-file providers for `values` + `links`) is now landed.
- Update (current): Phase 1.1 special-file provider pass 2 is landed:
  - `modifiers` + `modifier_categories` provider extraction and service wiring,
  - `localisation_commands` provider extraction and service wiring,
  - deeper `links` `from_data + data_source` membership gating in scope-ref resolution.
- Update (current): localisation command/scope semantic enforcement is now landed in typecheck for localisation-typed fields.
- Update (current): option-surface parity is now landed (`comparison`, `error_if_only_match`, reference labels), including `TYPECHECK_RULE_CUSTOM_ERROR` execution wiring.
- Update (current): deeper `links` advanced-chain semantics are now landed (multi-segment + mixed prefixed segments with per-segment input/data-source gating).
- Update (current): strict `push_scope`/`replace_scope` precedence compatibility is now landed (CWTools precedence: same-path `push_scope` wins; `replace_scope` skipped).
- Update (current): alias/single-alias hardening pass is landed:
  - strict unresolved handling for dynamic alias keys/families (`defer` vs `error`),
  - subtype-gated alias/single-alias invocation application by object occurrence.
- Update (current): subtype option + scope integration pass is landed:
  - subtype matcher options `type_key_filter` and `starts_with` are extracted/enforced,
  - subtype matcher evaluation now uses declaration-order first-match semantics,
  - subtype `push_scope` is injected into scope-context resolution (`scope[...]`, scope-context checks, localisation command scope checks).
- Localisation Stage 2 is now landed for rules/typecheck workflows:
  - compact `LocalisationKeyProvider` key existence/coverage checks,
  - required type-template localisation key materialization checks (`$` templates + `## required`).
- Update (2026-02-09 current): CWTools STL complex-enum fixture end-to-end typecheck tests are now landed:
  - new `tests/typecheck/test_complex_enum_e2e.py` validates `enum[...]` fields against fixture-derived complex enum memberships,
  - includes valid-path coverage and invalid-path diagnostics (`TYPECHECK_INVALID_FIELD_REFERENCE`) against fixture values.
- Immediate next step: complex enum parity hardening (edge path/structure semantics) and remaining special-file semantic hardening (`modifiers` scope/usage edges) under the rules-module checklist.
- Update (2026-02-09 current): localisation parser is now implemented as a single full-file shared-lexer path and keeps all trivia/comments in a separate `LocalisationParseResult.trivia` channel.
  - Important boundary: entry-level value fields (`leading_trivia`/`trailing_trivia`) remain for value-local formatting semantics, while full-file comments/blank-line trivia are preserved separately for future formatter integration.
  - Column validation now uses dedicated diagnostic code `LOCALISATION_INVALID_COLUMN` (not generic `LOCALISATION_INVALID_ENTRY`).
  - Indexing status note: current `LocalisationIndex` still stores full `LocalisationEntry` objects (including value/trivia payload fields); `LocalisationKeyProvider` is implemented and used by rules/typecheck for compact key-level checks.
  - Planned design for rules/typecheck scale: default to key-only provider semantics for non-localisation-file workflows, and load full parse artifacts only on demand (formatter/open-loc-file paths).
  - Performance experiments were intentionally paused for now to stay on roadmap scope: optimized lexer variant was reverted from active runtime and parked at `jominipy/lexer/faster_lexer.py` for later whole-library optimization phase.
  - Priority reset: continue rules module parity work first; localisation formatter/trivia-resolution policy is deferred until formatter phase.
- Localisation implementation reset decision (2026-02-09):
  - use a single architecture path only: extend shared lexer with explicit options/mode for localisation, and consume that in localisation parsing.
  - do not maintain dual parsing strategies (standalone line parser + lexer mode in parallel).
  - localisation entries must preserve both `leading_trivia` and `trailing_trivia` around values for formatter robustness (including future column alignment policies).
  - localisation files are UTF-8 BOM in practice; file parsing must read UTF-8 bytes, strip BOM from content, and retain BOM presence metadata for policy checks.
  - localisation string values must be single-line; if quote start does not close on the same line, emit unterminated-string diagnostic.
  - keep boundaries explicit:
    - shared lexer/token infrastructure remains the source of lexical behavior,
    - localisation module remains a thin grammar/adapter over shared infrastructure,
    - no second independent parser stack.
- Localisation Stage 2 implementation blueprint (approved evaluation):
  - Reuse parser pipeline architecture (lexer/buffered lexer/token source/event parser/tree sink) with a dedicated localisation grammar module, not rules/Jomini grammar reuse.
  - Keep implementation scope to lossless parse artifacts + index/facts; do not build red wrappers/AST unless later features require it.
  - Critical syntax reality to handle:
    - Paradox loc accepts `key:version "value"` forms (e.g. `md4.1.t:0 "..."`).
    - Real-world loc files may contain unescaped inner double quotes inside outer quoted values.
  - Verified current lexer behavior on this edge:
    - unescaped inner quotes split into multiple tokens and produce `LEXER_UNTERMINATED_STRING`. (we previous had an option `allow_multiline_strings` in our lexer that remains unused, we should change it to `allow_unterminated_strings` and use that in `_lex_string()` to allow unterminated. We have to be careful with this as loc strings still must begin and end with quotes, either double or single, just like in proper yaml -> all locs are strings and must begin and end with quotes. I don't even know if our lexer can handle single quotes. We definitely need to be careful with this)
    - therefore localisation grammar must not depend on strict `STRING` token correctness for value payload capture.
  - Recommended adaptation (next agent implementation plan):

## Latest Validation Snapshot (authoritative, 2026-02-09 current)
- `uv run pytest -q tests/test_rules_ingest.py tests/typecheck/test_reference_rules.py tests/typecheck/test_localisation_rules.py tests/typecheck/test_scope_rules.py tests/typecheck/test_services_and_facts.py` (`71 passed`)
- `uv run ruff check jominipy/rules/adapter.py jominipy/rules/__init__.py jominipy/typecheck/services.py jominipy/typecheck/runner.py jominipy/typecheck/rules.py tests/test_rules_ingest.py tests/typecheck/test_reference_rules.py tests/typecheck/test_localisation_rules.py` (passed)
- `uv run pytest -q tests/test_rules_ingest.py tests/typecheck/test_reference_rules.py tests/typecheck/test_scope_rules.py tests/typecheck/test_localisation_rules.py` (`80 passed`)
- `uv run ruff check jominipy/rules/adapter.py jominipy/typecheck/rules.py tests/test_rules_ingest.py tests/typecheck/test_scope_rules.py tests/typecheck/test_localisation_rules.py tests/typecheck/test_reference_rules.py` (passed)
- `uv run pyrefly check` (`0 errors`, `1 suppressed`)

*adapter.py was split up into multiple files for long term maintainability and modularity, so we'll need to change some of the code above.

## Validation Snapshot (historical)
- `uv run pytest tests/test_lint_typecheck_engines.py tests/typecheck/test_field_constraint_rules.py tests/typecheck/test_reference_rules.py tests/typecheck/test_localisation_rules.py tests/typecheck/test_scope_rules.py tests/typecheck/test_services_and_facts.py tests/test_localisation_parser.py tests/test_localisation_keys.py` (`73 passed`)
    1. Add localisation parser mode/entrypoint and grammar (`parse_localisation_*`) while keeping existing Jomini parse path untouched.
    2. Parse header (`l_<locale>:`) and entry prefix (`key:version`) with normal tokens.
    3. Capture value payload from original source slice to end-of-line (range-based), not by trusting strict `STRING` tokenization.
    4. Record symbol spans for key/version/locale and retain trivia/comments losslessly.
    5. Build localisation key index service from parsed entries (duplicate-key detection + coverage queries).
    6. Wire Stage 2 checks in typecheck/lint:
       - required localisation key existence from rules/type templates,
       - localisation reference coverage against indexed keys,
       - policy-driven severity for unresolved/missing keys.
- Drift correction note:
  - During subtype rollout, subtype constraints were briefly merged unconditionally into base constraints in the adapter.
  - This was corrected in the same iteration; subtype constraints now apply only through per-object-occurrence matcher resolution in typecheck.
- Latest validation snapshot (post-links-data-source + provider pass 2):
  - `uv run pytest -q tests/test_rules_ingest.py tests/test_lint_typecheck_engines.py` (`68 passed`)
  - `uv run ruff check jominipy/typecheck/rules.py jominipy/typecheck/services.py jominipy/rules/adapter.py jominipy/rules/__init__.py jominipy/rules/normalize.py tests/test_rules_ingest.py tests/test_lint_typecheck_engines.py` (passed)
  - `uv run pyrefly check` (`0 errors`, `1 suppressed`)
- Latest validation snapshot (post option-surface + advanced-links + precedence passes):
  - `uv run pytest -q tests/test_rules_ingest.py tests/test_lint_typecheck_engines.py` (`76 passed`)
  - `uv run ruff check tests jominipy docs` (passed)
  - `uv run pyrefly check` (`0 errors`, `1 suppressed`)
- Latest validation snapshot (post-alias/subtype/complex-enum phases):
  - `uv run pytest -q tests/test_rules_ingest.py tests/test_lint_typecheck_engines.py` (`60 passed`)
  - `uv run ruff check jominipy tests` (passed)
- Technical-debt note (important): `project_root` service-binding for custom-injected typecheck rules (notably custom `value_set/value` constraints) is currently retained mainly for tests/compatibility and should be removed or narrowed once canonical rule-IR-based configuration is the only supported extension path.
- Phase 1 kickoff scope:
  1. deterministic lint rule registry and execution ordering
  2. first semantic/domain rule from CWTools-derived constraints (required fields/cardinality)
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
   - domain/schema rules sourced from CWTools metadata (cardinality/scope/options) as lint/semantic validation concerns
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
