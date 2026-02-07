# Edge Cases We Intentionally Fail (For Now)

This file tracks known Clausewitz/Jomini edge cases that are currently out of
scope for baseline `jominipy` parsing.

Policy:
- `strict` mode prioritizes deterministic diagnostics.
- `permissive` mode may tolerate legacy save quirks with warnings.

## Mode matrix (current contract)

| Case | strict | permissive |
|---|---|---|
| Semicolon terminator | diagnostic/error | accepted |
| Extra `}` | diagnostic/error | accepted with warning |
| Missing `}` | diagnostic/error | accepted with warning |
| Parameter syntax (`[[...]]`, `$...$`) | diagnostic/error | diagnostic/error (unless explicitly feature-enabled) |
| Unmarked list form (`list "..."`) | diagnostic/error | diagnostic/error (unless explicitly feature-enabled) |
| Alternating value + key/value in block | accepted | accepted |
| Stray bare scalar after key/value (top level) | diagnostic/error | accepted |

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
- Status: unsupported by default; controlled by `ParserOptions.allow_parameter_syntax`.

5. Unmarked list forms
- Example: `pattern = list "christian_emblems_list"`
- Status: unsupported by default; controlled by `ParserOptions.allow_unmarked_list_form`.

6. Stray bare identifiers after structured top-level content
- Example:
  - `pride_of_the_fleet = yes`
  - `definition`
  - `definition = heavy_cruiser`
- Status: unsupported in `strict` mode.

## Notes

- Alternating plain values and key-value pairs in nested blocks remains
  accepted in baseline parser mode.
