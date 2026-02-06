# jominipy Architecture: Biome-style Lexer → Parser → CST → AST (Python-first)

This document defines the architecture we are implementing in jominipy. It is explicitly modeled after Biome’s layering (lexer → buffered lexer → token source → event parser → lossless tree sink → green tree → red wrappers → AST), but written in Python-friendly terms.

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
- Token text slices (so trivia text can always be recovered by slicing).

Red wrappers provide:
- Navigation (parent/children/siblings, token iteration).
- Text queries:
  - token.text_with_trivia
  - token.text_trimmed
- Trivia queries:
  - leading_trivia / trailing_trivia views that iterate pieces and slice the underlying token text.

## 7) AST
The AST is a typed view over red CST nodes.

Responsibilities:
- Provide semantic accessors (e.g., “this node is a KeyValue; get key/op/value”).
- Normalize where appropriate (e.g., `yes/no` → bool) without destroying CST fidelity.

Non-responsibilities:
- AST should not be the source of truth for formatting. Formatting comes from CST tokens + trivia.

## jomini-specific commitments
- Comments are trivia (not statements) for CST losslessness and Biome alignment.
- Repeated keys are preserved as separate statements; no merging in CST.
- Blocks are represented uniformly as `ClauseVal` with ordered children; list/object/mixed is derived later.

## Project layout (planned, matches current package layout)
Paths below are relative to the repository root.

- `jominipy/jominipy/text/`
  - `text.py`: `TextSize`, `TextRange`, slicing helpers
- `jominipy/jominipy/lexer/`
  - `tokens.py`: `TokenKind`, `TriviaKind`, `TokenFlags`, `Token`, `Trivia`, `TriviaPiece`
  - `lexer.py`: core lexer (to implement)
  - `buffered_lexer.py`: lookahead/checkpoints (to implement)
- `jominipy/jominipy/parser/`
  - `token_source.py`: trivia filtering + trivia_list ownership (to implement)
  - `event.py`, `marker.py`, `parsed_syntax.py`, `parser.py`: event parser (to implement)
  - `tree_sink.py`: lossless sink (to implement)
- `jominipy/jominipy/cst/`
  - green storage, red wrappers, builder (to implement)
- `jominipy/jominipy/ast/`
  - typed AST wrappers (to implement)

## Practical guidance (engineering discipline)
- Keep each layer “boringly single-purpose”. If a module starts needing knowledge from two layers, split it.
- Prefer types that prevent invalid states:
  - `TriviaKind` separate from `TokenKind`
  - range-based `Trivia` separate from compact `TriviaPiece`
- Keep the lexer strictly lexical and push semantic decisions into AST.
