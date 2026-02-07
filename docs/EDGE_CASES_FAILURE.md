# Edge Cases We Intentionally Fail (For Now)

This file tracks known Clausewitz/Jomini edge cases that are currently out of
scope for baseline `jominipy` parsing.

Policy:
- `strict` mode prioritizes deterministic diagnostics.
- `permissive` mode may tolerate legacy save quirks with warnings.

## Tracked Cases

1. Scalar key with only operator characters
- Example: `=="bar"` (`=` used as a key)
- Status: unsupported.

2. Extraneous closing braces (strict)
- Example:
  - `a = { 1 }`
  - `}`
  - `b = 2`
- Status:
  - `strict`: diagnostic/error.
  - `permissive`: tolerated with warning (`PARSER_LEGACY_EXTRA_RBRACE`).

3. Missing closing braces (strict)
- Example: `a = { b=c`
- Status:
  - `strict`: diagnostic/error.
  - `permissive`: tolerated with warning (`PARSER_LEGACY_MISSING_RBRACE`).

4. EU4 Dharma parameter syntax
- Examples:
  - `[[scaled_skill] ... ]`
  - `[[!skill] ... ]`
- Status: unsupported; reserved for a dedicated compatibility mode.

5. Unmarked list forms
- Example: `pattern = list "christian_emblems_list"`
- Status: unsupported in baseline grammar.

6. Stray bare identifiers after structured top-level content
- Example:
  - `pride_of_the_fleet = yes`
  - `definition`
  - `definition = heavy_cruiser`
- Status: unsupported in `strict` mode.

## Notes

- Semicolon statement terminators are supported (e.g. `key = "value";`).
- Alternating plain values and key-value pairs in nested blocks remains
  accepted by the baseline parser.
