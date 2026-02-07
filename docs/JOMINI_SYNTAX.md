# Jomini Syntax Reference

This document captures the practical syntax surface `jominipy` targets.

## Core Shape
- Data is expressed as key/value statements and block values.
- Comments begin with `#` and continue to end-of-line.
- Blocks are delimited by `{` and `}`.

Example:
```jomini
a = 1
b = "hello" # inline comment
```

## Scalars
Common scalar forms:
```jomini
plain = foo
integer = -1
decimal = 1.000
bool_true = yes
bool_false = no
quoted = "foo"
date_like = 1821.1.1
```

Notes:
- Quoted values can contain newlines and `#` without starting a comment.
- Quoted and unquoted values can differ semantically in game behavior; quotedness must be preserved.
- Keys are scalars and may include symbols (for example `@var`, dotted names, dashed names).

## Operators
Supported key/value operators include:
- `=`
- `==`
- `!=`
- `>`
- `>=`
- `<`
- `<=`
- `?=`

## Boundary Rules
Statement/value boundaries can be introduced by:
- whitespace/newlines
- braces (`{` `}`)
- operators
- quotes
- comments

Compact form is valid:
```jomini
a={b="1"c=d}foo=bar#good
```

## Arrays, Objects, and Mixed Blocks
Blocks are structurally uniform and can represent:
- object-like content (`key = value` entries)
- array-like content (plain values)
- mixed content (both)

Examples:
```jomini
flags = { schools_initiated=1444.11.11 mol_polish_march=1444.12.4 }
players_countries = { "Player" "ENG" }
levels = { 10 0=2 1=2 } # mixed
```

## Implicit and Tagged Blocks
Implicit assignment form is valid:
```jomini
foo{bar=qux} # equivalent to foo={bar=qux}
```

Tagged block values are valid:
```jomini
color = rgb { 100 200 150 }
color = hsv { 0.43 0.86 0.61 }
```

## Repeated Keys
Repeated keys are valid and common:
```jomini
a = 1
a = 2
```

`jominipy` policy:
- canonical AST keeps source-ordered repeated entries
- object coercion behavior is derived-view policy (see AST docs)

## Feature-gated / Legacy Forms
Some forms are intentionally gated or mode-dependent:
- parameter syntax (`[[...]]`, `[[!...]]`)
- unmarked list forms (`list "..."`)
- extra or missing `}` in legacy save files
- semicolon terminators in some contexts

See `docs/EDGE_CASES_FAILURE.md` for strict/permissive contract details.

