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
| Recovery primitives | `biome_parser/src/parse_recovery.rs` | `jominipy/parser/parse_recovery.py` | adapted | Token-set recovery implemented; API is Pythonic |
| List parse loops | `biome_parser/src/parse_lists.rs` | `jominipy/parser/parse_lists.py` | adapted | Node-list helper implemented and in use; separated-list helper intentionally deferred until a real separator-driven Jomini construct requires it |
| Parser progress/stall guard | `biome_parser/src/lib.rs` (`ParserProgress`) | `jominipy/parser/parser.py` | matched | Stall detection used in list parsing |
| Parser checkpoint/rewind | `biome_parser/src/lib.rs` | `jominipy/parser/parser.py` | adapted | Parser-level checkpoint object implemented |
| Speculative parsing guard | `biome_parser/src/lib.rs` | `jominipy/parser/parser.py` | adapted | Context-managed speculative depth implemented |
| Mode/feature gating | Biome feature support traits/options | `jominipy/parser/options.py` + `grammar.py` | adapted | Explicit mode/feature flags with grammar gates |
| AST typed layer | Biome syntax wrappers/typed nodes | `jominipy/ast/*` | adapted | AST v1 + Phase 1/2 implemented (`model`, `scalar`, `lower`); preserves CST-first semantics, delayed interpretation, and explicit scalar kind modeling |
| Red CST wrappers | Biome red syntax wrappers | `jominipy/cst/*` (planned) | pending | Green CST exists; red-layer navigation/query wrappers are next major parity gap |
| Block/list coercion policy | Biome typed-node semantic utilities | `jominipy/ast/*` | adapted | Canonical AST preserves statement order; derived object/array/mixed coercion helpers landed on `AstBlock` (last-write-wins + multimap modes) |

## Intentional deviations (must stay explicit)
- Jomini-specific grammar policy lives in grammar routines (e.g., tagged block values), not in a generic shared grammar crate.
- Current list helpers include only non-separated lists; `ParseSeparatedList` is intentionally deferred because current Jomini grammar does not rely on comma-separated constructs as a primary form.
- Repeated keys (e.g. repeated `modifier`) are preserved in canonical AST; any map/array coercion is a derived view, not parse-time mutation.

## Required parity checks before merge
1. Every new grammar/recovery feature must include at least one strict-mode and one permissive-mode test if a mode gate exists.
2. Any parser behavior deviation from Biome must add or update this file with rationale.
3. `docs/EDGE_CASES_FAILURE.md` must match current test expectations.
4. AST work must not begin until parser/CST entries above are `matched` or `adapted` with explicit rationale.
