# jominipy Architecture: Biome-style Lexer → Parser → CST → AST (Python-first)

This document defines the architecture we are implementing in jominipy.

## Doc Ownership
- This file is for stable architecture and invariants.
- Do not store phase-by-phase handoff logs here.
- Current execution status belongs in `docs/HANDOFF.md`.
- Forward plan belongs in `docs/NEXT_AGENT_ROADMAP.md`.

## Critical Constraint: Biome Architecture Is Non-Negotiable
- We do **not** adopt CWTools runtime architecture.
- CWTools is the semantic source of truth for rule meaning, but not the execution model.
- Required model:
  - Biome-style staged pipeline (`parse -> normalize -> semantic graph -> deterministic checks`)
  - precomputed/cached semantic artifacts
  - deterministic rule execution ordering
- Forbidden model:
  - ad hoc recursive reinterpretation of rules during each validation walk
  - implicit global mutable context between unrelated branches
  - coupling completion-oriented internals directly into checker execution

## CWTools Semantics Adapter Boundary
- Any CWTools parity behavior that is non-trivial must be implemented as a semantic adapter layer, not a new runtime engine.
- Adapter layer responsibilities:
  - normalize CWTools-specific option semantics into typed internal contracts
  - pre-resolve dynamic semantic inputs (where feasible) into cacheable artifacts
  - expose stable, deterministic inputs to lint/typecheck engines
- Examples of adapter-bound semantics:
  - `replace_scope` channel semantics (`this/root/from*/prev*`)
  - `push_scope` + `replace_scope` precedence compatibility mode
  - alias/single-alias expansion
  - subtype gating and conditional rule materialization
  - complex enum materialization
  - special-file semantic ingestion (`links`, `modifiers`, `values`, `localisation`)
  - localisation command/scope semantics as precomputed artifacts (not runtime callback-driven validation)

## Toolchain scope (Biome-style)
jominipy is a Biome-style toolchain for Paradox game scripts (Jomini/Clausewitz). The library provides:
- Parser
- Linter
- Formatter
- CLI

The architecture below focuses on the parsing stack that enables lossless formatting and consistent linting.

The design goal is not “parsing that works”, but a system that is:
- Lossless: we can reproduce the original formatting (tokens + trivia) from the CST.
- Deterministic: ownership rules for trivia are unambiguous.
- Type-safe (within Python’s limits): invalid states are hard to represent.
- Composable: features like lookahead, re-lexing, recovery, and incremental reuse fit without redesign.

## Glossary
- Token: a categorized slice of the input with a kind, a range, and optional flags.
- Trivia: text we preserve but do not parse structurally (whitespace/newlines/comments). Trivia exists to keep the CST lossless.
- SyntaxKind / TokenKind: the per-language vocabulary (token kinds + node kinds).
- CST: concrete syntax tree (lossless). Contains every token and its trivia.
- AST: typed view over the CST. May be lossy with respect to trivia/punctuation.
- Green tree: compact immutable storage (good for sharing/caching).
- Red wrappers: ergonomic handles for navigation and queries.

## Non-negotiable invariants
- Every byte of source is owned exactly once.
- The parser never consumes trivia tokens.
- Trivia ownership is deterministic (leading vs trailing is not guessed later).
- CST is syntax-only; AST is semantic.

## End-to-end pipeline (the conveyor belt)
1) Source text
2) Lexer: emits tokens (including trivia tokens)
3) BufferedLexer: adds lookahead + checkpoint/rewind + re-lex hooks
4) TokenSource: hides trivia from the parser and records it out-of-band with ownership
5) Parser: consumes non-trivia tokens and emits an event stream (Start/Token/Finish)
6) LosslessTreeSink: replays events, attaches trivia to tokens, inserts EOF if needed
7) TreeBuilder: constructs the green CST
8) Red wrappers: navigation and text/trivia queries
9) AST: typed layer over red CST nodes

## Implementation status (current)
- Implemented: `lexer.py`, `buffered_lexer.py`, `parser/token_source.py`, `parser/event.py`, `parser/marker.py`, `parser/parser.py`, `parser/parse_recovery.py`, `parser/parse_lists.py`, `parser/tree_sink.py`, `cst/green.py`, `parser/jomini.py`.
- Implemented parser modes: `strict` and `permissive` (`parser/options.py`).
- Implemented parser recovery: token-set based recovery into `ERROR` nodes, with line-break recovery support.
- Implemented parser-level checkpoints/rewind and speculative-parse guards.
- Implemented AST v1: `ast/model.py`, `ast/scalar.py`, `ast/lower.py` (typed CST-lowering with delayed scalar interpretation).
- Implemented AST Phase 1 coercion utilities on `AstBlock`: shape classification and derived object/array coercion views (including repeated-key multimap).
- Implemented AST Phase 2 scalar hardening in `ast/scalar.py`: explicit scalar kind model (`unknown`/`bool`/`number`/`date_like`) and quoted-default non-coercion with opt-in coercion.
- Implemented Phase 3 red wrappers in `cst/red.py` and migrated AST lowering to wrappers in `ast/lower.py`.
- Implemented centralized cross-pipeline test cases and debug helpers: `tests/_shared_cases.py`, `tests/_debug.py`.
- Implemented AST consumer follow-on API: `ast/views.py` (`AstBlockView`) with explicit object/multimap/array accessors and scalar interpretation helpers over canonical AST.
- Implemented parse-result carrier API:
  - `pipeline/result.py` (`ParseResultBase`, `JominiParseResult`)
  - `pipeline/results.py` (`LintRunResult`, `FormatRunResult`, `CheckRunResult`)
  - `parser/jomini.py` (`parse_result(...)`)
- Implemented CWTools rules read-only ingest pipeline:
  - `rules/result.py` (`RulesParseResult`)
  - `rules/parser.py` + `rules/ir.py` (statement IR + `##`/`###` metadata capture)
  - `rules/normalize.py` + `rules/load.py` (deterministic indexing + directory ingest)
- Remaining major gaps: production analyzer/rule engine, formatter rules pipeline, mature type checker rule set, and CLI/service orchestration over the shared carrier (pipeline/lint/format/typecheck scaffolds now exist as thin placeholders).

## jominipy types (current and intended)
The types below are chosen to mirror Biome’s *two-phase trivia model* and to prevent common category errors.

### Text coordinates
- `TextSize`: opaque offset/length type (`jominipy/text/text.py`)
- `TextRange`: half-open range [start, end) (`jominipy/text/text.py`)

### Lexer vocabulary
- `TokenKind`: the lexer can emit these (`jominipy/lexer/tokens.py`)
- `TokenFlags`: token metadata (e.g., preceding line break, quoted, escape) (`jominipy/lexer/tokens.py`)
- `Token`: `(kind: TokenKind, range: TextRange, flags: TokenFlags)` (`jominipy/lexer/tokens.py`)

### Trivia vocabulary (type-safe)
Biome explicitly separates the trivia classification from the language token kinds. We do the same.

- `TriviaKind`: the trivia vocabulary (`NEWLINE`, `WHITESPACE`, `COMMENT`, `SKIPPED`)
- `Trivia`: parser-side trivia record: `(kind: TriviaKind, range: TextRange, trailing: bool)`
- `TriviaPiece`: tree-side compact trivia: `(kind: TriviaKind, length: TextSize)`

Why two trivia types?
- `Trivia` (range-based) is ideal while streaming through the input and deciding ownership.
- `TriviaPiece` (kind+length) is ideal in the CST for compact storage and sharing; text is recovered by slicing.

## Layer-by-layer responsibilities

## 1) Lexer (language-specific)
The lexer is a single-pass scanner over the input text.

Responsibilities:
- Emit `Token` objects with `TokenKind` and `TextRange`.
- Emit trivia tokens as tokens (`TokenKind.WHITESPACE`, `TokenKind.NEWLINE`, `TokenKind.COMMENT`).
- Compute flags that are lexical facts (e.g., `HAS_ESCAPE`, `WAS_QUOTED`).

Non-responsibilities:
- No semantic classification (date vs dotted identifier vs localization key).
- No trivia ownership decisions (leading/trailing) beyond emitting trivia tokens.

## 2) BufferedLexer (shared wrapper)
Biome’s lexer interface is minimal (current token + next token). Real parsers need lookahead and rewind.

Responsibilities:
- Cache lexed tokens to provide `nth_non_trivia(n)` without re-lexing.
- Provide checkpoint/rewind.
- Clear caches when context changes or re-lexing changes the current token kind.

This layer is a performance and correctness wrapper. It does not decide grammar.

## 3) TokenSource (bridge)
This is where trivia becomes structured lossless data.

Responsibilities:
- Expose only *non-trivia* tokens to the parser (`current`, `bump`, `nth`).
- Consume lexer trivia tokens and append them to a `trivia_list: list[Trivia]`.
- Decide `Trivia.trailing` deterministically.

Trailing policy (Biome-aligned):
- Trivia immediately following a token is trailing until a newline is encountered.
- A newline flips subsequent trivia to be leading for the next non-trivia token.

Key property:
- At the end of TokenSource, we have:
  - a clean token stream for the parser
  - and a complete trivia list with ownership metadata

## 4) Parser (event-based)
The parser is not a tree builder. It’s an event recorder.

Responsibilities:
- Consume non-trivia tokens from TokenSource.
- Emit events: `Start(kind)`, `Token(kind, end)`, `Finish`.
- Use checkpoints/rewind for ambiguity resolution and recovery.

Why events?
- Events are cheap to rewind and replay.
- They decouple parsing decisions from tree construction.

## 5) LosslessTreeSink (attachment policy)
This is the second critical trivia step: *attachment*.

Responsibilities:
- Replay parser events.
- For each token event:
  - Consume trivia entries marked as leading (`trailing=False`) that align with the current text position → convert to `TriviaPiece`s.
  - Consume trivia entries marked as trailing (`trailing=True`) up to the boundary rule (typically “until next newline”) → convert to `TriviaPiece`s.
  - Call `token_with_trivia(kind, token_text, leading_pieces, trailing_pieces)`.
- Ensure EOF exists; if not, generate it and attach any remaining trivia as EOF leading trivia.

Important constraint:
- The sink does not invent ownership. It only implements deterministic consumption based on TokenSource’s `trailing` values.

## 6) TreeBuilder and CST
TreeBuilder consumes start/finish/token-with-trivia operations and builds a green tree.

Green CST stores:
- Nodes and tokens, immutable.
- Leading/trailing trivia as lists of `TriviaPiece` (kind + length).
- Token text (without trivia) plus trivia piece lengths; red wrappers recover trivia text by slicing the original source with computed token offsets.

Red wrappers provide:
- Navigation (parent/children/siblings, token iteration).
- Text queries:
  - token.text_with_trivia
  - token.text_trimmed
- Trivia queries:
  - leading_trivia / trailing_trivia views that iterate pieces and slice the original source text.

## 7) AST
The AST is a typed view over red CST nodes.

Responsibilities:
- Provide semantic accessors (e.g., “this node is a KeyValue; get key/op/value”).
- Normalize where appropriate (e.g., `yes/no` → bool) without destroying CST fidelity.

Non-responsibilities:
- AST should not be the source of truth for formatting. Formatting comes from CST tokens + trivia.

## Biome in practice: consumer wiring
Biome does not add a separate semantic tree between parser and tools. Instead, it composes tools around a shared parsed root and typed syntax wrappers.

Practical shape in Biome:
1. Parse once into a reusable parse result:
   - `biome_js_parser::Parse<T>` (`references/biome/crates/biome_js_parser/src/parse.rs`)
   - cache-aware parsing (`parse_js_with_cache`) and typed access (`Parse<T>::tree()`).
2. Use generated typed syntax wrappers as the main consumer API:
   - `biome_js_syntax` re-exports generated node wrappers (`generated::*`).
3. Run analyzer rules on the parsed language root:
   - `biome_js_analyze::{analyze, analyze_with_inspect_matcher}`
   - both consume `LanguageRoot<JsLanguage>`.
4. Run formatter rules on the same syntax tree:
   - node-level rule trait (`FormatNodeRule`) and top-level `format_node(...)`.
5. Orchestrate all of the above in service handlers:
   - `biome_service` JS file handler calls parser/analyzer/formatter from one parse lifecycle.

Implication for jominipy:
- AST consumers should be thin, typed query surfaces over canonical AST, not a second parser.
- Linter/formatter/CLI should consume these views from one parse/lower result rather than re-deriving structure independently.
- Type checker should share the same parse/fact pipeline, but remain a separate execution engine from lint rules.

## jomini-specific commitments
- Comments are trivia (not statements) for CST losslessness and Biome alignment.
- Repeated keys are preserved as separate statements; no merging in CST.
- Blocks are represented uniformly as `ClauseVal` with ordered children; list/object/mixed is derived later.

## Project layout (current + planned)
Paths below are relative to the repository root.

- `jominipy/jominipy/text/`
  - `text.py`: `TextSize`, `TextRange`, slicing helpers
- `jominipy/jominipy/lexer/`
  - `tokens.py`: `TokenKind`, `TriviaKind`, `TokenFlags`, `Token`, `Trivia`, `TriviaPiece`
  - `lexer.py`: core lexer (implemented)
  - `buffered_lexer.py`: lookahead/checkpoints (implemented)
- `jominipy/jominipy/parser/`
  - `token_source.py`: trivia filtering + trivia_list ownership (implemented)
  - `event.py`, `marker.py`, `parsed_syntax.py`, `parser.py`: event parser core (implemented)
  - `parse_recovery.py`: Biome-style token-set recovery (implemented)
  - `parse_lists.py`: Biome-style reusable node-list parse loops (implemented)
  - `options.py`: parser mode/feature options (implemented)
  - `grammar.py`: Jomini grammar routines + diagnostics policy (implemented, evolving)
  - `tree_sink.py`: lossless sink (implemented)
- `jominipy/jominipy/cst/`
  - `green.py`: green storage + builder (implemented)
  - `red.py`: red wrappers (implemented Phase 3)
- `jominipy/jominipy/ast/`
  - typed AST wrappers/lowering (implemented v1)
  - block/list/mixed coercion helpers (implemented Phase 1)
  - scalar policy hardening (implemented Phase 2)
  - lowering ported to red wrappers (implemented Phase 3)
  - consumer view/query surface (`views.py`, implemented Phase 5)

## Next steps
1. Mandatory planning gate before broad subsystem implementation:
   - evaluate project-wide roadmap and produce a detailed phased plan
   - include risks, test strategy, and parity checks per phase
   - treat Biome parity as a hard constraint
2. Deepen design before broad tool implementation:
   - linter/type-checker/formatter boundaries and shared-facts model
   - CWTools rules parser + normalized IR pipeline design
3. Build linter/formatter/type-checker/CLI integration over shared parse/lower + AST views:
   - keep one parse/lower lifecycle and reuse typed consumer views
   - avoid ad hoc raw CST structural re-derivation in tool entrypoints
4. Add developer-facing Pythonic APIs using generated models:
   - generate typed models from schema IR (dataclass/Pydantic strategy)
   - provide CST-safe edit transaction layer for manipulations/additions/deletions
   - avoid naive object serialization that loses trivia/comments
4. Maintain explicit parity tracking:
   - update `docs/BIOME_PARITY.md` for each parser/CST/AST feature change
   - record any intentional deviations with rationale and tests

## Planning-gate enforcement (current)
- Broad subsystem implementation (full linter engine, formatter rule engine, type checker, rules DSL parser) is gated behind a complete Phase 0 proposal.
- Existing `pipeline/entrypoints.py`, `lint/runner.py`, and `format/runner.py` are scaffolds only and do not represent completed subsystem architecture.
- Until Phase 0 is explicitly approved, the repository should prioritize proposal/docs parity and boundary validation over feature expansion.

## Linter and type-checker boundary (required invariant)
- Shared infrastructure:
  - parse carrier, AST views, semantic/type fact generation, diagnostic plumbing.
- Separate engines:
  - Type checker: type/scope/value-constraint diagnostics.
  - Linter: style/domain/policy/schema diagnostics.
- Dependency direction:
  - Linter may consume type facts.
  - Type checker must not depend on lint rule execution.

## Autofix model (required invariant)
- Autofix means a rule emits deterministic machine-applicable edits.
- Autofixes must be:
  - deterministic
  - idempotent
  - syntax-safe
  - trivia/comment-safe (or explicitly decline to fix when unsafe)

## Configurable style policy examples
- Field-order rules should be lint-config driven (per object/profile), not hardcoded.
- List/array layout policies (for example, disallow single-line arrays) should be style rules; formatter may enforce the same policy in output mode.

## Practical guidance (engineering discipline)
- Keep each layer “boringly single-purpose”. If a module starts needing knowledge from two layers, split it.
- Prefer types that prevent invalid states:
  - `TriviaKind` separate from `TokenKind`
  - range-based `Trivia` separate from compact `TriviaPiece`
- Keep the lexer strictly lexical and push semantic decisions into AST.
