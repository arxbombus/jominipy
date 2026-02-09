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
  - type-safe narrowing was added in `complex_enums` traversal to satisfy strict static checking.
- Modifiers edge-policy hardening landed:
  - new `ModifierScopeRule` enforces `modifier_categories` scope compatibility for `alias_match_left[modifier]` references,
  - strict unresolved policy now reports known modifiers with missing/empty scope metadata.
- Links edge-policy hardening landed:
  - `scope_ref` link-chain resolution now enforces `link_type` compatibility (`scope`/`both` only),
  - prefixed and multi-segment link chains with `link_type = value` now deterministically reject in strict mode.
- Links primitive-reference hardening landed:
  - `value_field`/`int_value_field` and `variable_field`/`int_variable_field` now enforce links `link_type` compatibility (`value`/`both`) when values resolve through known link chains,
  - this validation reuses scope-context + data-source checks from the links adapter surface.
- Links continuation pass 2 (2026-02-09T11:05:11Z) landed:
  - primitive link compatibility is now wired through the default typecheck rule stack (not only ad hoc custom-rule tests),
  - targeted regression coverage was extended to lock `value_field` and `variable_field` prefixed-link behavior.

## Latest Validation Snapshot
- `uv run pyrefly check` (`0 errors`)
- `uv run ruff check jominipy/typecheck/rules.py tests/typecheck/test_reference_rules.py` (pass)
- `uv run pytest -q tests/typecheck/test_reference_rules.py` (`33 passed`)

## Exact Next Step
1. Finish `links` parity only for unresolved/unknown chain-policy edges:
   - missing link definitions,
   - missing `output_scope`,
   - unresolved `data_source` membership,
   - strict (`error`) vs defer behavior consistency.
2. Add focused regression tests for each edge above in `tests/typecheck/test_reference_rules.py`.
3. Re-run targeted validation (`ruff`, `pyrefly`, `pytest` for `test_reference_rules.py`) and then mark `links` as complete.

## Notes
- Historical logs are archived under `docs/archive/`.
- Update process is defined in `docs/AGENT_UPDATE_PROTOCOL.md`.
