# Agent Update Protocol

This is the canonical protocol for updating docs and Serena memories.

## Scope
- Update only what changed. Avoid restating existing canonical docs.
- Keep one source of truth per topic.

## Canonical docs and ownership
- `docs/STATUS.md`: current execution state, latest validation, exact next step.
- `docs/NEXT_AGENT_ROADMAP.md`: future work only (no landed-history logs).
- `docs/BIOME_PARITY.md`: parity/deviation mapping only.
- `docs/ARCHITECTURE.md`: stable architecture and boundaries only.
- `docs/RULES_SYNTAX.md`: CWTools `.cwt` syntax semantics and implementation checklist only.

## Required end-of-task updates
1. Update `docs/STATUS.md` with a delta-only summary:
   - what changed
   - validation run and result
   - exact next step
2. If parity behavior changed, update `docs/BIOME_PARITY.md` in the same change.
3. If architecture boundaries changed, update `docs/ARCHITECTURE.md` in the same change.
4. If sequencing changed, update `docs/NEXT_AGENT_ROADMAP.md`.

## Memory protocol
1. Keep exactly one active latest handoff memory:
   - `handoff_YYYY-MM-DDTHH-MM-SSZ_<scope>_LATEST`
2. Keep `handoff_current` pointing to that exact memory.
3. Archive superseded handoffs with `_ARCHIVED`.
4. Keep process guidance in a single memory: `ops_protocol`.
5. Keep the high-signal persistent memories only:
   - `project_overview`
   - `reference_map`
   - `style_and_conventions`
   - `handoff_current`
   - one `handoff_*_LATEST`

## Anti-bloat rules (mandatory)
- Do not duplicate the same validation snapshot in multiple docs/memories.
- Do not copy large "landed history" blocks into current-state docs.
- Prefer links to canonical docs over restating content.
- Move historical narrative to `docs/archive/`.

## Naming conventions
- Handoff memory format:
  - `handoff_YYYY-MM-DDTHH-MM-SSZ_<scope>_<LATEST|ARCHIVED>`

