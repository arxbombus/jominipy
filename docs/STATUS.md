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

## Latest Validation Snapshot
- `uv run pytest -q tests/typecheck/test_complex_enum_e2e.py` (`6 passed`)
- `uv run pytest -q tests/typecheck/test_complex_enum_e2e.py tests/typecheck/test_reference_rules.py` (`31 passed`)
- `uv run ruff check tests/typecheck/test_complex_enum_e2e.py jominipy/rules/semantics.py jominipy/typecheck/rules.py` (pass)

## Exact Next Step
1. Continue complex-enum parity hardening for remaining edge-path/structure semantics beyond current fixture coverage.
2. Continue remaining special-file hardening (`modifiers` and `links` edge-policy parity).

## Notes
- Historical logs are archived under `docs/archive/`.
- Update process is defined in `docs/AGENT_UPDATE_PROTOCOL.md`.
