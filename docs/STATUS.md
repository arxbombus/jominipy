# Current Status

Last updated: 2026-02-09

## Active Workstream
- CWTools rules parity execution over Biome-style architecture.
- Primary semantic reference: `docs/RULES_SYNTAX.md`.

## What Changed Recently
- Alias/single-alias hardening landed:
  - unresolved dynamic alias policy (`defer` vs `error`)
  - subtype-gated alias invocation enforcement
- Subtype option/scope integration landed:
  - `type_key_filter` and `starts_with` matcher options
  - declaration-order first-match behavior
  - subtype `push_scope` integration in scope/localisation checks
- Adapter split for maintainability:
  - `jominipy/rules/adapter.py` was split into smaller adapter modules
- Complex-enum parity coverage expanded:
  - end-to-end typecheck tests now validate CWTools STL fixture-derived `enum[...]` complex enums (valid + invalid),
  - quoted declaration semantics for `"enum[key]"` are now enforced in typecheck (quoted values required + membership validation),
  - filter-edge coverage added for `path_strict` + `path_extension`,
  - default typecheck rule-stack execution path is now covered for enum reference checks.
- Complex-enum hardening pass (path/structure parity) landed:
  - `path`, `path_file`, and `path_extension` matching now follows CWTools case-insensitive behavior,
  - complex enums with no configured `path` no longer match arbitrary files (matching CWTools path-filter behavior),
  - `enum_name = {}` now collects node keys only, while `enum_name = scalar` collects leaf keys only,
  - type-safe narrowing was added in `complex_enums` traversal to satisfy strict static checking,
  - `docs/RULES_SYNTAX.md` is synced with these parity semantics.

## Latest Validation Snapshot
- `uv run pyrefly check` (`0 errors`)
- `uv run pytest -q tests/test_rules_ingest.py -k "complex_enum" tests/typecheck/test_complex_enum_e2e.py` (`15 passed`)
- `uv run ruff check jominipy/rules/adapters/complex_enums.py tests/test_rules_ingest.py tests/typecheck/test_complex_enum_e2e.py` (pass)

## Exact Next Step
1. Continue remaining special-file hardening (`modifiers` and `links` edge-policy parity).
2. Re-run targeted rules/typecheck parity suites after each special-file edge-policy change.

## Notes
- Historical logs are archived under `docs/archive/`.
- Update process is defined in `docs/AGENT_UPDATE_PROTOCOL.md`.
