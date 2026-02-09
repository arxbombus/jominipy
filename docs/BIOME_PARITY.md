# Biome Parity Map

This document tracks parity between jominipy and Biome parser architecture.

## How to use this file
For every parser/CST/AST feature, record:
1. Biome reference module
2. jominipy module
3. Current parity status (`matched`, `adapted`, `intentional deviation`, `pending`)
4. Behavior tests proving current contract
5. Notes on why any deviation exists

## Parser/CST parity matrix

| Area | Biome reference | jominipy | Status | Notes |
|---|---|---|---|---|
| Event stream + markers | `biome_parser/src/event.rs`, `marker.rs` | `jominipy/parser/event.py`, `marker.py` | matched | Forward-parent/tombstone flow implemented |
| TokenSource bridge | `biome_parser/src/token_source.rs` | `jominipy/parser/token_source.py` | matched | Trivia filtering and ownership metadata implemented |
| Lossless tree sink | `biome_parser/src/tree_sink.rs` | `jominipy/parser/tree_sink.py` | matched | EOF insertion + trivia attachment behavior implemented |
| Recovery primitives | `biome_parser/src/parse_recovery.rs` | `jominipy/parser/parse_recovery.py` | adapted | Token-set recovery + line-break recovery implemented; parser now suppresses duplicate diagnostics at the same token start to match Biome error-reporting behavior |
| List parse loops | `biome_parser/src/parse_lists.rs` | `jominipy/parser/parse_lists.py` | adapted | Node-list helper implemented and in use; separated-list helper intentionally deferred until a real separator-driven Jomini construct requires it |
| Localisation lexer mode/options | `biome_*_parser` per-language mode/config pattern | `jominipy/lexer/lexer.py` (+ localisation adapter) | pending | Decision locked (2026-02-09): localisation must consume shared lexer via mode/options; avoid dual parser paths |
| Parser progress/stall guard | `biome_parser/src/lib.rs` (`ParserProgress`) | `jominipy/parser/parser.py` | matched | Stall detection used in list parsing |
| Parser checkpoint/rewind | `biome_parser/src/lib.rs` | `jominipy/parser/parser.py` | adapted | Parser-level checkpoint object implemented |
| Speculative parsing guard | `biome_parser/src/lib.rs` | `jominipy/parser/parser.py` | adapted | Context-managed speculative depth implemented |
| Mode/feature gating | Biome feature support traits/options | `jominipy/parser/options.py` + `grammar.py` | adapted | Explicit mode/feature flags with grammar gates |
| AST typed layer | Biome syntax wrappers/typed nodes | `jominipy/ast/*` | adapted | AST v1 + Phase 1/2/3 implemented (`model`, `scalar`, `lower`); lowering now runs through red wrappers while preserving CST-first semantics |
| Red CST wrappers | Biome red syntax wrappers | `jominipy/cst/red.py` + `jominipy/cst/__init__.py` | adapted | `SyntaxNode`/`SyntaxToken` wrappers implemented with navigation and token text/trivia accessors; current scope is read-only traversal/query API |
| Block/list coercion policy | Biome typed-node semantic utilities | `jominipy/ast/*` | adapted | Canonical AST preserves statement order; derived object/array/mixed coercion helpers landed on `AstBlock` (last-write-wins + multimap modes) |

## Consumer integration parity matrix

| Area | Biome reference | jominipy | Status | Notes |
|---|---|---|---|---|
| Parse result carrier | `biome_js_parser/src/parse.rs` (`Parse<T>`, `parse_js_with_cache`) | `jominipy/pipeline/result.py` + `jominipy/parser/jomini.py` | adapted | `ParseResultBase` + `JominiParseResult` landed with diagnostics/error-state and cached green/syntax/AST/view/facts accessors; downstream tool orchestration is the next step |
| Typed consumer surface | `biome_js_syntax` generated typed wrappers (`generated::*`) | `jominipy/ast/model.py` + `jominipy/ast/views.py` | adapted | Canonical AST remains source-of-truth; `AstBlockView` adds explicit `as_object`/`as_multimap`/`as_array` and scalar helpers with quoted-default interpretation policy; central-case view/debug coverage added in `tests/test_ast_views.py` |
| Analyzer entry on shared root | `biome_js_analyze/src/lib.rs` (`analyze`, `LanguageRoot<JsLanguage>`) | pending linter integration | pending | Linter should consume a single parse/lower result, not re-walk raw CST ad hoc |
| Formatter entry on shared root | `biome_js_formatter/src/lib.rs` (`FormatNodeRule`, `format_node`) | pending formatter integration | pending | Formatter should consume stable typed views while preserving CST as formatting source-of-truth |
| Service-level orchestration | `biome_service/src/file_handlers/javascript.rs` | pending CLI/service orchestration | pending | Future jominipy service layer should centralize parser/lower/analyze/format pipeline |
| Run-result carriers | `biome_service` parse/analyze/format orchestration carriers | `jominipy/pipeline/results.py` | adapted | `LintRunResult`/`FormatRunResult`/`CheckRunResult` landed to enforce one shared parse lifecycle across entrypoints |

## Planning-gate parity targets (next implementation step)

| Area | Biome reference | jominipy target | Status | Notes |
|---|---|---|---|---|
| Thin orchestration entrypoints | `biome_service/src/file_handlers/javascript.rs` | `jominipy/pipeline/entrypoints.py` | adapted | `run_typecheck` added; `run_check` now composes parse + typecheck + lint with one shared parse lifecycle |
| Lint runner boundary | `biome_js_analyze/src/lib.rs`, `registry.rs` | `jominipy/lint/runner.py` | adapted | Deterministic registry scaffolds landed with semantic/style split and type-fact consumption |
| Formatter runner boundary | `biome_js_formatter/src/lib.rs` | `jominipy/format/runner.py` | pending | CST/trivia remains source-of-truth; AST views only guide decisions |
| Type-checker boundary | `biome_js_semantic/src/*`, `biome_js_type_info/src/*` | `jominipy/typecheck/*` | adapted | Engine scaffold + rule-domain enforcement landed (`correctness` + `sound` contracts); field-type/range correctness checks now run in typecheck |
| Rules DSL parsing + generation | `xtask/codegen`, `biome_syntax_codegen/src/*` | planned `jominipy/rules/*` + generation pipeline | pending | Separate DSL parser and normalized IR for generated models/validators |
| Rules semantic graph + resolved constraints | `biome_js_analyze` registry/services composition + `biome_service` JS handler orchestration | `jominipy/rules/schema_graph.py` + planned `typecheck/rules.py` resolved checks | pending | Schema graph foundation landed; resolved correctness checks still pending. Keep one parse lifecycle; place hard correctness in typecheck and keep lint policy/style-focused |

### Rules ingest + semantic adapter status
- Landed `jominipy/rules` read-only ingest:
  - `RulesParseResult` carrier (`jominipy/rules/result.py`)
  - parsed statement IR + metadata attachment from `##`/`###` comments (`jominipy/rules/parser.py`, `jominipy/rules/ir.py`)
  - deterministic category index (`jominipy/rules/normalize.py`)
  - file/directory loaders (`jominipy/rules/load.py`)
- Status interpretation:
  - DSL parsing is now `adapted` at ingest/IR level.
  - code generation remains `pending`.
  - engine consumption is now partially implemented through semantic adapters + typecheck services.
  - approved next parity step (2026-02-08): cross-file schema graph -> nested facts -> typecheck correctness expansion -> resolved reference checks -> advanced semantics wiring.
  - update (2026-02-08): cross-file schema graph foundation is implemented and consumed by HOI4 semantic loaders.
  - update (2026-02-08): nested analysis facts for object fields are implemented in shared facts cache (`jominipy/analysis/facts.py`) for deterministic field-level rule execution.
  - update (2026-02-08): primitive field-type/range correctness moved into typecheck (`TYPECHECK_INVALID_FIELD_TYPE`), keeping lint focused on policy/style concerns.
  - update (2026-02-08): registry-backed asset lookup contract added for typecheck (`jominipy/typecheck/assets.py`), mirroring Biome-style shared-service injection patterns while keeping one parse/facts lifecycle.
  - update (2026-02-08): HOI4 icon correctness is now documented as primarily type-reference resolution (`<spriteType>` from `interface/gfx.cwt`) with texture file existence validated on sprite definitions, not direct icon filename path checks alone.
  - update (2026-02-08): alias/single-alias adapter wiring landed (`single_alias_right[...]` expansion + `alias_match_left[...]` membership checks) with checker integration.
  - update (2026-02-09): alias/single-alias execution expansion landed:
    - adapter artifacts now extract alias/single-alias definitions and invocation paths,
    - typecheck now validates alias/single-alias invocation blocks against extracted rule constraints.
  - update (2026-02-09): localisation required-template parity expanded:
    - type-localisation templates (`$` forms + `## required`) are extracted from rules adapters,
    - typecheck validates required materialized keys against compact localisation key-provider artifacts.
  - update (2026-02-08): subtype adapter wiring landed (deterministic matcher gating + subtype-conditional field constraints in typecheck).
  - update (2026-02-09): alias/single-alias hardening landed:
    - strict unresolved policy behavior for unknown dynamic alias keys/families (`defer` vs `error`),
    - subtype-gated alias/single-alias invocation application per object occurrence.
  - update (2026-02-09): subtype option + scope integration landed:
    - subtype matcher options `type_key_filter` and `starts_with` extracted from rules metadata and enforced in matcher evaluation,
    - subtype evaluation now follows declaration-order first-match semantics (single active subtype),
    - subtype `push_scope` now feeds scope-context resolution in reference, scope-context, and localisation-command scope rules.
  - update (2026-02-08): complex enum materialization landed (project-file scan + name-tree traversal + `start_from_root`/path filtering) and is injected into enum reference checks through services.
  - update (2026-02-09 current): complex-enum parity hardening coverage expanded:
    - added end-to-end typecheck tests against CWTools STL fixture-derived complex enums (valid + invalid cases),
    - added quoted declaration parity for `"enum[key]"` with quoted-value enforcement in reference matching,
    - added filter-edge test coverage for `path_strict` + `path_extension`,
    - added default typecheck rule-stack execution coverage for enum-reference service wiring.
  - update (2026-02-09 current, path/structure hardening):
    - aligned complex-enum path filtering with CWTools `CheckPathDir` semantics (case-insensitive `path`/`path_file`/`path_extension`; no-match when no `path` entries are configured),
    - aligned `enum_name` extraction shape semantics so `enum_name = {}` collects node keys only and `enum_name = scalar` collects leaf keys only,
    - parity locked with focused ingest + E2E tests.
  - update (2026-02-08): special-file provider pass 1 landed:
    - `values` section memberships merged into `value[...]` reference memberships,
    - `links` definitions injected into typecheck scope-reference validation for link-prefix/output-scope transitions with input-scope gating.
  - update (2026-02-08): special-file provider pass 2 landed:
    - `modifiers` + `modifier_categories` provider extraction wired into typecheck services,
    - `localisation_commands` provider extraction wired into typecheck services,
    - `links` `from_data` now enforces `data_source` membership during scope-link resolution (with unresolved defer/error policy).
  - update (2026-02-09 current): modifier edge-policy hardening landed:
    - typecheck now enforces `modifier_categories` scope compatibility for `alias_match_left[modifier]` references,
    - strict mode now reports known modifiers with missing/empty scope metadata as unresolved metadata errors.
  - update (2026-02-08): localisation command/scope semantic enforcement landed:
    - typecheck now validates localisation commands used in localisation-typed fields against `localisation_commands` scope metadata,
    - unresolved command metadata follows typecheck unresolved-reference policy (`defer` vs `error`).
  - update (2026-02-08): clarified file-classification boundary:
    - `effects*.cwt` and `triggers*.cwt` remain regular rules files (normal ingest/adapter path), not special-file providers.
  - update (2026-02-08): localisation parity model clarified:
    - CWTools uses runtime callback/service validation (`processLocalisation`/`validateLocalisation`),
    - jominipy keeps Biome-style staged artifacts (adapter extraction + service injection), with YAML content indexing as a later layer.
  - update (2026-02-08): option-surface parity pass landed:
    - normalized metadata now captures `comparison`, `error_if_only_match`, and incoming/outgoing reference labels,
    - typecheck now executes `error_if_only_match` as a deterministic correctness diagnostic (`TYPECHECK_RULE_CUSTOM_ERROR`).
  - update (2026-02-08): links advanced-chain parity pass landed:
    - scope-link resolution now supports multi-segment chains (`a.b.c`) and mixed prefixed segments (`owner.var:foo`),
    - each segment enforces input-scope gating and `from_data + data_source` membership rules.
  - update (2026-02-09 current): links edge-policy hardening landed:
    - scope-link resolution now enforces `link_type` compatibility for `scope_ref` checks (`scope`/`both` accepted, `value` rejected),
    - behavior is locked by prefixed and mixed-chain regression coverage.
  - update (2026-02-09 current): links primitive-reference hardening landed:
    - `value_field`/`int_value_field` and `variable_field`/`int_variable_field` now enforce `link_type` compatibility for known link-chain references (`value`/`both`),
    - validation runs on the same scope-context/data-source semantics used by scope-link resolution.
  - update (2026-02-09 current, pass 2 @ 11:05Z): links primitive execution wiring landed:
    - primitive link compatibility checks are now part of default typecheck service wiring,
    - targeted regressions lock prefixed-link behavior on primitive value/variable fields.
  - update (2026-02-08): strict scope precedence compatibility landed:
    - when a declaration has both `push_scope` and `replace_scope`, typecheck now applies CWTools precedence (`push_scope` wins; same-path `replace_scope` skipped),
    - precedence behavior is locked by explicit regression tests.
  - update (2026-02-09): localisation parser architecture reset requirement:
    - implement one-path ingestion only (shared lexer options + localisation adapter),
    - preserve both leading and trailing value trivia for formatter parity,
    - keep localisation values single-line and emit unterminated diagnostics for unclosed same-line quotes,
    - keep BOM-aware file ingestion metadata without introducing a second parser stack.
  - update (2026-02-09 current):
    - localisation parse results now preserve full-file trivia/comments in a separate trivia channel for formatter-phase round-trip safety,
    - invalid child-column structure uses dedicated `LOCALISATION_INVALID_COLUMN` diagnostics,
    - lexer micro-optimization experiment is intentionally parked (`jominipy/lexer/faster_lexer.py`) and not active runtime behavior during current rules-parity phase.
  - update (2026-02-09 current, Stage 2a initial):
    - added compact localisation key-provider artifacts (`key -> locale-bitmask`) for rules/typecheck paths to avoid carrying full localisation entry payloads when only key existence/coverage checks are needed,
    - wired provider into typecheck services and added deterministic key existence/coverage rule execution (`localisation_coverage` policy: `any`/`all`),
    - retained full localisation parse/index payloads for formatter/open-localisation workflows as intentional separate path.

## Phase 0 parity gate checklist
1. Every planned subsystem has at least one concrete Biome reference module in this file.
2. Planned local module boundaries are documented before subsystem implementation.
3. One-parse-lifecycle invariant is explicitly preserved across lint/format/check/typecheck entrypoints.
4. Naming boundaries are explicit across domains (`JominiParseResult` vs planned `RulesParseResult`).
5. Any deviation introduced during implementation must update this document and corresponding tests in the same change.

Phase 0 status:
- Completed on 2026-02-07.
- Checklist items above are satisfied at planning level and now govern Phase 1+ implementation.

## Intentional deviations (must stay explicit)
- Jomini-specific grammar policy lives in grammar routines (e.g., tagged block values), not in a generic shared grammar crate.
- Current list helpers include only non-separated lists; `ParseSeparatedList` is intentionally deferred because current Jomini grammar does not rely on comma-separated constructs as a primary form.
- Repeated keys (e.g. repeated `modifier`) are preserved in canonical AST; any map/array coercion is a derived view, not parse-time mutation.
- Naming/domain boundary policy:
  - Game-script pipeline uses `JominiParseResult`.
  - Shared cross-domain carrier behavior lives in `ParseResultBase`.
  - Future rules-DSL parsing must use a distinct carrier type name (`RulesParseResult`).
  - Do not rely on compatibility aliases for this project; rename directly when boundaries become clearer.

## Required parity checks before merge
1. Every new grammar/recovery feature must include at least one strict-mode and one permissive-mode test if a mode gate exists.
2. Any parser behavior deviation from Biome must add or update this file with rationale.
3. `docs/EDGE_CASES_FAILURE.md` must match current test expectations.
4. AST work must not begin until parser/CST entries above are `matched` or `adapted` with explicit rationale.
5. Consumer API changes must document how they map to Biome’s parse-result + typed-wrapper + tool-entry layering.
6. New lint/type-check/format entrypoints must prove they consume one `JominiParseResult` lifecycle and do not duplicate parse/lower work.
7. Planning documents for new subsystems must include explicit Biome mapping references before implementation.
