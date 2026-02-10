# Junior CS Student Intro: CWTools Rules, Jomini Examples, and jominipy Parity

Last updated: 2026-02-10

This document is meant to be a practical, beginner-friendly guide that still stays technically accurate.

If you are new, read this in order:
1. What `.cwt` rules are and why they exist.
2. Each rule feature with examples.
3. How CWTools parses and uses the rules internally.
4. How `jominipy` mirrors behavior (Biome-style architecture + adapters).

---

## 0) Mental Model (simple but important)

Think of `.cwt` as a schema language for Paradox/Jomini script.

- Game/mod script (`.txt`) is the data.
- `.cwt` is the contract that says what shapes and values are allowed.
- CWTools reads `.cwt`, then validates game/mod script against it.

In compiler terms:
- `.txt` files are "programs".
- `.cwt` files are "type/validation rules".
- CWTools is the validator + completion engine.

---

## 1) Basic Structure

From `docs/RULES_SYNTAX.md`, this kind of rule:

```cwt
ship_size = {
    ## cardinality = 0..1
    cost = int

    modifier = {
        alias_name[modifier] = alias_match_left[modifier]
    }

    ## cardinality = 0..1
    acceleration = float

    construction_type = scalar

    ## cardinality = 0..1
    default_behavior = <ship_behavior>

    ## cardinality = 0..1
    prerequisites = {
        ## cardinality = 0..100
        <technology>
    }

    ## cardinality = 0..1
    upkeep_override = {
        energy = int
        minerals = int
    }

    class = enum[shipsize_class]
}
```

### What this means
- `ship_size` object has fields with specific types and occurrence limits.
- Some fields must exist (`construction_type`, `class`).
- Some are optional (`cost`, `acceleration`, etc.) because cardinality min is `0`.
- Nested blocks have their own rules (`upkeep_override`, `prerequisites`).

### Jomini script example (valid)

```txt
ship_size = {
    cost = 120
    modifier = {
        ship_fire_rate = 0.1
    }
    acceleration = 2.5
    construction_type = military_ship
    default_behavior = aggressive_patrol
    prerequisites = { laser_tech_1 armor_tech_1 }
    upkeep_override = {
        energy = 3
        minerals = 1
    }
    class = shipclass_military
}
```

### Jomini script example (invalid)

```txt
ship_size = {
    cost = fast            # invalid: expected int
    acceleration = maybe   # invalid: expected float
    class = unknown_class  # invalid if not in enum[shipsize_class]
}
```

### How CWTools handles this internally
1. Parse `.cwt` text into syntax tree nodes (`Node`, `Leaf`, comments).
2. Convert each rule into typed internal rule objects (`NodeRule`, `LeafRule`).
3. Parse metadata comments (`## cardinality`, etc.) into `Options`.
4. During script validation, walk real script blocks and check:
   - allowed keys
   - value type/shape
   - cardinality (min/max)
   - scope constraints when present

Relevant CWTools files:
- `references/cwtools/CWTools/Rules/RulesParser.fs`
- `references/cwtools/CWTools/Rules/RuleValidationService.fs`
- `references/cwtools/CWTools/Rules/FieldValidators.fs`

---

## 2) Simple Rules (datatypes and references)

This is the biggest practical category.

### 2.1 `bool`

```cwt
is_triggered_only = bool
```

Valid:
```txt
is_triggered_only = yes
```

Invalid:
```txt
is_triggered_only = true
```

CWTools: mapped to boolean validator (`yes/no` only).

### 2.2 `int` and `int[min..max]`

```cwt
count = int
threat = int[-5..100]
```

Valid:
```txt
count = 5
threat = -2
```

Invalid:
```txt
count = 2.7
threat = 1000
```

CWTools: parses range and checks bounds.

### 2.3 `float` and `float[min..max]`

```cwt
acceleration = float
factor = float[-5.0..100.0]
```

Valid:
```txt
acceleration = 1.25
factor = 99.5
```

Invalid:
```txt
acceleration = fast
factor = 200.0
```

### 2.4 `scalar`

```cwt
construction_type = scalar
```

Meaning: accepts generic string-like token.

### 2.5 `percentage_field`

```cwt
war_support = percentage_field
```

Valid:
```txt
war_support = 10%
```

Invalid:
```txt
war_support = 10
```

### 2.6 Localisation primitives

```cwt
name = localisation
title_sync = localisation_synced
tooltip = localisation_inline
```

`localisation_inline` has stricter behavior for quoted inline strings.

### 2.7 `filepath[...]` and `icon[...]`

```cwt
picture = filepath[gfx/interface/portraits/,.dds]
button_icon = icon[gfx/interface/ships]
```

Valid:
```txt
picture = commander_01
button_icon = battleship
```

These resolve to:
- `gfx/interface/portraits/commander_01.dds`
- `gfx/interface/ships/battleship.dds`

CWTools checks file existence.

### 2.8 Date-like fields

```cwt
start_date = date_field
```

Valid:
```txt
start_date = 1936.1.1
```

### 2.9 Type references (`<type_key>` and pref/suff forms)

```cwt
default_behavior = <ship_behavior>
modifier = pre_<opinion_modifier>_suf
```

Meaning:
- value must be a discovered member of that type.
- second form strips prefix/suffix and checks inner type member.

### 2.10 Enum references

```cwt
class = enum[shipsize_class]
```

Value must be in that enum.

### 2.11 Scope references

```cwt
who = scope[country]
target = event_target[country]
any_target = scope_field
```

`scope_field` means generic target-like field.

### 2.12 Variable/value field families

```cwt
amount = variable_field
count = int_variable_field
score = value_field
value_int = int_value_field
```

These allow numeric literals and dynamic references, with special handling.

### 2.13 Alias-key field

```cwt
selector = alias_keys_field[trigger]
```

Value must be a known key from alias family `trigger`.

### How CWTools handles simple rules
- Parse step: token -> typed rule field (`processKey` in `RulesParser.fs`).
- Validation step: dispatch by field kind in `FieldValidators.checkField`.
- Type/enum/scope/variable/file checks are specialized helper functions.

---

## 3) Enums

### Rule

```cwt
enums = {
    enum[shipsize_class] = {
        shipclass_military
        shipclass_military_station
        shipclass_transport
    }
}
```

### Script use

```txt
class = shipclass_transport
```

### CWTools behavior
- Parses enum declarations.
- Stores `enum_key -> allowed values`.
- Any `enum[shipsize_class]` field validates against that set.

---

## 4) Complex Enums

Complex enum means "derive enum values by scanning real files."

### Rule

```cwt
complex_enum[event_chain_counter] = {
    path = "game/common/event_chains"
    name = {
        counter = {
            enum_name = {}
        }
        scalar = {
            scalar = enum_name
        }
    }
}
```

### Idea
- Find matching files under `path`.
- Traverse by `name` structure.
- Collect names where `enum_name` indicates.

### Script use

```txt
counter_id = enum[event_chain_counter]
```

### CWTools behavior
- Parse complex enum definition.
- During refresh, scan entity files and materialize values.
- Add materialized values into enum map for normal enum validation/completion.

Core logic:
- `RulesParser.fs` (`processComplexEnum`)
- `RulesHelpers.fs` (`getEnumsFromComplexEnums`)

---

## 5) Value Sets

### Rule pair

```cwt
set_country_flag = value_set[country_flag]
has_country_flag = value[country_flag]
```

### Script example

```txt
set_country_flag = won_major_war
has_country_flag = won_major_war
```

### Meaning
- First statement defines/registers dynamic values.
- Second statement consumes those values and must match membership.

### CWTools behavior
- `value_set[...]` and `value[...]` parsed as separate semantic kinds.
- Collected values are stored and reused for validation/completion.

---

## 6) Types

Type declarations tell CWTools where to discover named entities.

### Rule

```cwt
types = {
    type[technology] = {
        path = "game/common/technology"
    }
    type[ship_behavior] = {
        name_field = "name"
        path = "game/common/ship_behaviors"
    }
}
```

### Options
- `name_field`
- `skip_root_key`
- `path_strict`
- `path_file`
- `path_extension`
- `type_per_file`
- `starts_with`
- `type_key_filter`
- `unique`
- `severity`

### Script implications
If type `ship_behavior` is discovered with IDs:
- `aggressive_patrol`
- `defensive_patrol`

Then fields typed as `<ship_behavior>` accept those only.

### CWTools behavior
1. Parse type declarations from `.cwt`.
2. Scan real files using path filters.
3. Extract actual IDs (from key or `name_field`).
4. Build type membership map.
5. Use map in `<type>` validators and completion.

---

## 7) Subtypes

Subtypes are conditional rule branches for the same top-level type/object.

### Type declaration-side subtype

```cwt
type[ship_size] = {
    path = "game/common/ship_sizes"
    subtype[starbase] = { class = shipclass_starbase }
    subtype[platform] = { class = shipclass_military_station }
    subtype[ship] = { }
}
```

### Rule-side subtype

```cwt
ship_size = {
    subtype[starbase] = {
        flip_control_on_disable = bool
    }
    subtype[ship] = {
        combat_disengage_chance = float
    }
}
```

### Script example

```txt
ship_size = {
    class = shipclass_starbase
    flip_control_on_disable = yes
}
```

This should apply `subtype[starbase]` rules.

### CWTools behavior
- Parse subtype matcher rules and subtype-specific rule blocks.
- During validation, compute which subtype matches current object.
- Apply corresponding subtype constraints.
- Support subtype options like `type_key_filter`, `starts_with`, `push_scope`.

---

## 8) Localisation Requirements

### Rule

```cwt
type[ship_size] = {
    path = "game/common/ship_sizes"
    localisation = {
        name = "$"
        description = "$_desc"
        ## required
        required = "$_required"
    }
}
```

### Script usage

```txt
for_ship = my_ship
```

Expected localisation keys:
- `my_ship`
- `my_ship_desc`
- `my_ship_required`

### CWTools behavior
- Parse template strings with `$` placeholder.
- For discovered type instances, materialize expected keys.
- Validate localisation availability and expose info/completion.

---

## 9) Modifiers

### Type-driven modifier templates

```cwt
type[ship_size] = {
    path = "game/common/ship_sizes"
    modifiers = {
        "$_production_mult" = country
        "$_firepower" = fleet
    }
}
```

### Meaning
For each `ship_size` entry, generate modifier names and scope categories.

### Script use
Used via modifier alias pathways and checked for scope compatibility.

### CWTools behavior
- Parse modifier templates from type declarations.
- Also parse static modifier lists from `modifiers.cwt`.
- Merge both into modifier knowledge used by alias/validation/completion.

---

## 10) Aliases

Aliases are reusable grammar fragments.

### Rule

```cwt
event = {
    immediate = {
        alias_name[effect] = alias_match_left[effect]
    }
}
```

and

```cwt
alias[effect:create_starbase] = {
    owner = scalar
    size = scalar
}
```

### Meaning
- `immediate` accepts any effect alias member from family `effect`.
- `create_starbase` defines one such member structure.

### CWTools behavior
- Parse alias definitions as `AliasRule`.
- Build alias family map.
- Expand/apply alias constraints where invoked.

---

## 11) Single Alias

Single alias = reusable small section.

### Rule

```cwt
single_alias[any_trigger_clause] = {
    count = int
    alias_name[trigger] = alias_match_left[trigger]
}
```

Use:

```cwt
any_country = single_alias_right[any_trigger_clause]
```

### Meaning
Equivalent to inlining the single alias body at use site.

### CWTools behavior
- Parse single alias declarations.
- Replace/inject them during rule transformation pass before final validation logic.

---

## 12) Options (`##`) and comments

### Common options
- `cardinality = min..max`
- `push_scope = ...`
- `replace_scope = {...}`
- `severity = warning|information|...`
- `scope = ...`
- `comparison` via `==`
- `error_if_only_match`
- reference labels

### Comment levels
- `#` ordinary comment
- `##` semantic options
- `###` documentation/help text

### CWTools behavior
- Comments around nodes/leaves are collected and attached.
- Semantic options are parsed into rule metadata/options.
- Docs are stored for completion/info display.

---

## 13) Special Files

These provide global metadata used by normal rule validation.

### 13.1 `scopes.cwt`
- defines scope names, aliases, subscope relationships.

### 13.2 `links.cwt`
- defines chain links (`x.y` style), input scopes, output scopes, from-data behavior, prefixes.

### 13.3 `folders.cwt`
- declares script folder scanning behavior.

### 13.4 `modifiers.cwt` + `modifier_categories.cwt`
- modifier names + category->scope mappings.

### 13.5 `values.cwt`
- hardcoded memberships for `value[...]`.

### 13.6 `localisation.cwt`
- localisation command/scope compatibility metadata.

### CWTools behavior
- Utility parser loads these files into managers/maps before full validation.
- Runtime services then consume these maps for scope transitions, modifier checks, localisation command checks, etc.

---

## 14) How CWTools Parses `.cwt` End-to-End

### Stage A: parse text
- Uses parser to create AST of clauses/leaves/comments.

### Stage B: rule lowering
- Convert parsed nodes into typed rule IR (field types, node rules, alias rules, type definitions, enums, etc.).

### Stage C: transform passes
- Replace marker fields and single aliases.
- Expand certain special markers into concrete alternatives.

### Stage D: index building + discovery
- Build rule maps (`TypeRules`, `Aliases`).
- Discover actual type members from game/mod files.
- Materialize complex enums from file scans.
- Aggregate variables/values/localisation references.

### Stage E: runtime consumers
- Validation service: diagnostics.
- Completion service: suggestions and docs.
- Info service: hover-like information and helper lookup results.

---

## 15) How `jominipy` Maintains Biome Parity While Supporting `.cwt`

This project intentionally has two goals at once:
1. Keep parser architecture Biome-like (deterministic staged pipeline).
2. Implement CWTools rule semantics for parity.

### 15.1 Biome-style architecture choices in `jominipy`
- Single parse lifecycle: parse once, share facts/results across lint/typecheck.
- Structured carriers (`ParseResultBase`, typed result pipelines).
- Explicit stage boundaries (parse -> analysis facts -> checks).
- Deterministic contracts for lint/typecheck domains and rule registration.

Key status docs:
- `docs/BIOME_PARITY.md`
- `docs/STATUS.md`

### 15.2 `.cwt` support in `jominipy` (current implemented core)
- `.cwt` parser and IR:
  - `jominipy/rules/parser.py`
  - `jominipy/rules/ir.py`
  - `jominipy/rules/result.py`
- normalization/indexing:
  - `jominipy/rules/normalize.py`
  - `jominipy/rules/schema_graph.py`
- semantic extraction:
  - `jominipy/rules/semantics.py`

### 15.3 Adapter layer (what it is)

The adapter layer is the "semantic lowering bridge":
- Input: normalized schema graph from parsed `.cwt`.
- Output: concrete semantic artifacts typecheck/lint can directly consume.

Adapter modules:
- `jominipy/rules/adapters/aliases.py`
- `jominipy/rules/adapters/subtypes.py`
- `jominipy/rules/adapters/complex_enums.py`
- `jominipy/rules/adapters/special_files.py`
- facade: `jominipy/rules/adapters/__init__.py`

What adapters produce:
- alias family membership maps
- alias definitions/invocation paths
- single alias definitions/invocations
- subtype matchers and subtype field constraints
- complex enum definitions + materialized values from project files
- special-file artifacts (`links`, `values`, `modifiers`, `localisation_commands`)
- expanded field constraints (including single-alias expansion effects)

### 15.4 Where adapters are consumed

`jominipy/typecheck/services.py` builds `TypecheckServices` by loading adapter artifacts and dynamic project memberships.

`jominipy/typecheck/rules.py` default rule stack uses these services for:
- primitive/type/reference checks
- alias/single-alias execution checks
- scope/link checks
- modifier scope checks
- localisation command/key/template checks
- subtype-aware gating and context behavior

Lint currently consumes a narrower semantic subset (for example required fields) while hard correctness is increasingly typecheck-owned.

### 15.5 Important parity decisions already reflected
- semantic parity target is CWTools meaning, not CWTools runtime architecture.
- Biome-style deterministic staging remains intact.
- one parse lifecycle remains a hard constraint.
- adapter split improved maintainability and parity velocity.

### 15.6 Current practical gap vs ultimate goal

Current state:
- semantic artifacts are mostly built in-memory (cached loaders + services).

Ultimate goal you described:
- auto-generate explicit Python rules files/artifacts for linter/typecheck consumption.

So adapters today are mostly a middle-end. A complete backend codegen step is still the long-term finish line.

---

## 16) Suggested "How to Learn This Fast" Path

If you are a junior CS student working on this codebase:
1. Read `docs/RULES_SYNTAX.md` once quickly.
2. Read this document section 2 through 7 slowly (core semantics).
3. Open these files in order:
   - `jominipy/rules/ir.py`
   - `jominipy/rules/parser.py`
   - `jominipy/rules/schema_graph.py`
   - `jominipy/rules/adapters/__init__.py`
   - `jominipy/typecheck/services.py`
   - `jominipy/typecheck/rules.py`
4. Run a few focused tests and inspect one failing diagnostic path end-to-end.

If you can explain one failing field from:
- parsed `.cwt` statement
- to adapter artifact
- to typecheck diagnostic,

then you understand the system at a professional level.

