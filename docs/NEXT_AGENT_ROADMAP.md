# Next Agent Roadmap

This file is future-only. Do not log landed history here.

## Non-negotiable constraint
- Keep Biome-style staged architecture.
- Implement CWTools parity through semantic adapters over normalized IR.
- Do not replicate CWTools runtime architecture.

## Current execution order
1. Complex enum parity hardening
   - finish remaining edge path/structure semantics
   - add parity-focused tests for CWTools-compatible behavior
2. Special-file parity hardening
   - `modifiers` edge semantics
   - remaining `links` edge-policy behavior
3. Typecheck ownership completion
   - keep correctness in `TYPECHECK_*`
   - keep lint as policy/style/heuristics only
4. Localisation follow-up (after rules parity slice)
   - continue compact key-provider hardening
   - defer formatter-level trivia emission policy to formatter phase

## Done-definition for each roadmap item
1. Implementation merged in target module(s).
2. Focused tests added/updated and passing.
3. `docs/STATUS.md` updated with delta + validation + exact next step.
4. `docs/BIOME_PARITY.md` updated if behavior/parity mapping changed.

## History location
- Legacy detailed roadmap snapshot:
  - `docs/archive/NEXT_AGENT_ROADMAP_LEGACY_2026-02-09.md`

