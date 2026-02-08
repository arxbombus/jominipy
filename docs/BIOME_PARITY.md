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
| Type-checker boundary | `biome_js_semantic/src/*`, `biome_js_type_info/src/*` | `jominipy/typecheck/*` | adapted | Engine scaffold + rule-domain enforcement landed (`correctness` + `sound` contracts) |
| Rules DSL parsing + generation | `xtask/codegen`, `biome_syntax_codegen/src/*` | planned `jominipy/rules/*` + generation pipeline | pending | Separate DSL parser and normalized IR for generated models/validators |
| Rules semantic graph + resolved constraints | `biome_js_analyze` registry/services composition + `biome_service` JS handler orchestration | `jominipy/rules/schema_graph.py` + planned `typecheck/rules.py` resolved checks | pending | Schema graph foundation landed; resolved correctness checks still pending. Keep one parse lifecycle; place hard correctness in typecheck and keep lint policy/style-focused |

### Rules ingest status (read-only phase)
- Landed `jominipy/rules` read-only ingest:
  - `RulesParseResult` carrier (`jominipy/rules/result.py`)
  - parsed statement IR + metadata attachment from `##`/`###` comments (`jominipy/rules/parser.py`, `jominipy/rules/ir.py`)
  - deterministic category index (`jominipy/rules/normalize.py`)
  - file/directory loaders (`jominipy/rules/load.py`)
- Status interpretation:
  - DSL parsing is now `adapted` at ingest/IR level.
  - code generation and engine consumption remain `pending`.
  - approved next parity step (2026-02-08): cross-file schema graph -> nested facts -> typecheck correctness expansion -> resolved reference checks -> advanced semantics wiring.
  - update (2026-02-08): cross-file schema graph foundation is implemented and consumed by HOI4 semantic loaders.
  - update (2026-02-08): nested analysis facts for object fields are implemented in shared facts cache (`jominipy/analysis/facts.py`) for deterministic field-level rule execution.

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
