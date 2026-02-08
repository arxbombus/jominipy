"""Normalize parsed rules files into deterministic indexed IR."""

from __future__ import annotations

from collections import defaultdict
import re

from jominipy.rules.ir import (
    IndexedRuleStatement,
    RuleCardinality,
    RuleFileIR,
    RuleMetadata,
    RuleScopeReplacement,
    RuleSetIR,
    RuleStatement,
)

_BRACKET_KEY_PATTERN = re.compile(r"^(?P<family>[^\[\]]+)\[(?P<argument>.*)\]$")

_CATEGORY_BY_FAMILY = {
    "alias": "alias",
    "single_alias": "single_alias",
    "type": "type",
    "enum": "enum",
    "complex_enum": "complex_enum",
    "value_set": "value_set",
    "value": "value",
}

_OPTION_KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")

_SECTION_KEYS = {
    "types",
    "enums",
    "values",
    "links",
    "scopes",
    "folders",
    "modifiers",
    "modifier_categories",
    "localisation_commands",
    "list_merge_optimisations",
}


def normalize_ruleset(files: tuple[RuleFileIR, ...]) -> RuleSetIR:
    normalized_files = tuple(_normalize_file(file) for file in files)
    indexed: list[IndexedRuleStatement] = []
    for file in normalized_files:
        _index_statement_list(file.statements, parent_path=(), indexed=indexed)

    ordered = tuple(
        sorted(
            indexed,
            key=lambda item: (
                item.category,
                item.source_path,
                item.source_range.start.value,
                item.source_range.end.value,
                item.key,
                item.family or "",
                item.argument or "",
            ),
        )
    )

    grouped: defaultdict[str, list[IndexedRuleStatement]] = defaultdict(list)
    for item in ordered:
        grouped[item.category].append(item)
    by_category = {category: tuple(items) for category, items in sorted(grouped.items())}

    return RuleSetIR(files=normalized_files, indexed=ordered, by_category=by_category)


def _normalize_file(file: RuleFileIR) -> RuleFileIR:
    return RuleFileIR(
        path=file.path,
        statements=tuple(_normalize_statement(statement) for statement in file.statements),
        diagnostics=file.diagnostics,
    )


def _normalize_statement(statement: RuleStatement) -> RuleStatement:
    normalized_metadata = _normalize_metadata(statement.metadata)
    if statement.operator == "==":
        normalized_metadata = RuleMetadata(
            documentation=normalized_metadata.documentation,
            options=normalized_metadata.options,
            cardinality=normalized_metadata.cardinality,
            scope=normalized_metadata.scope,
            push_scope=normalized_metadata.push_scope,
            replace_scope=normalized_metadata.replace_scope,
            severity=normalized_metadata.severity,
            comparison=True,
            error_if_only_match=normalized_metadata.error_if_only_match,
            outgoing_reference_label=normalized_metadata.outgoing_reference_label,
            incoming_reference_label=normalized_metadata.incoming_reference_label,
            flags=normalized_metadata.flags,
        )
    if statement.value.kind not in {"block", "tagged_block"}:
        return RuleStatement(
            source_path=statement.source_path,
            source_range=statement.source_range,
            kind=statement.kind,
            key=statement.key,
            operator=statement.operator,
            value=statement.value,
            metadata=normalized_metadata,
        )

    normalized_children = tuple(_normalize_statement(child) for child in statement.value.block)
    normalized_value = statement.value.__class__(
        kind=statement.value.kind,
        text=statement.value.text,
        block=normalized_children,
        tag=statement.value.tag,
    )
    return RuleStatement(
        source_path=statement.source_path,
        source_range=statement.source_range,
        kind=statement.kind,
        key=statement.key,
        operator=statement.operator,
        value=normalized_value,
        metadata=normalized_metadata,
    )


def _normalize_metadata(metadata: RuleMetadata) -> RuleMetadata:
    cardinality: RuleCardinality | None = None
    scope: tuple[str, ...] | None = None
    push_scope: tuple[str, ...] | None = None
    replace_scope: tuple[RuleScopeReplacement, ...] | None = None
    severity: str | None = None
    error_if_only_match: str | None = None
    outgoing_reference_label: str | None = None
    incoming_reference_label: str | None = None
    flags: set[str] = set(metadata.flags)

    for option in metadata.options:
        key = option.key.strip()
        value = option.value.strip() if option.value is not None else None
        key_lower = key.lower()
        normalized_key = _normalize_option_key(key)
        if value is None:
            flags.add(key)
            continue
        if key_lower == "cardinality":
            parsed = _parse_cardinality(value)
            if parsed is not None:
                cardinality = parsed
            continue
        if key_lower == "scope":
            scope = _parse_value_list(value)
            continue
        if key_lower == "push_scope":
            push_scope = _parse_value_list(value)
            continue
        if key_lower == "replace_scope":
            parsed_replace = _parse_replace_scope(value)
            if parsed_replace is not None:
                replace_scope = parsed_replace
            continue
        if key_lower == "severity":
            severity = value
            continue
        if normalized_key == "errorifonlymatch":
            error_if_only_match = value
            continue
        if normalized_key == "outgoingreferencelabel":
            outgoing_reference_label = value
            continue
        if normalized_key == "incomingreferencelabel":
            incoming_reference_label = value

    return RuleMetadata(
        documentation=metadata.documentation,
        options=metadata.options,
        cardinality=cardinality,
        scope=scope,
        push_scope=push_scope,
        replace_scope=replace_scope,
        severity=severity,
        comparison=metadata.comparison,
        error_if_only_match=error_if_only_match,
        outgoing_reference_label=outgoing_reference_label,
        incoming_reference_label=incoming_reference_label,
        flags=frozenset(flags),
    )


def _normalize_option_key(key: str) -> str:
    return _OPTION_KEY_NORMALIZER.sub("", key.strip().lower())


def _parse_cardinality(value: str) -> RuleCardinality | None:
    raw = value.strip()
    if ".." not in raw:
        return None
    soft = False
    if raw.startswith("~"):
        soft = True
        raw = raw[1:].strip()
    min_text, max_text = (part.strip() for part in raw.split("..", 1))
    minimum, minimum_unbounded = _parse_bound(min_text)
    maximum, maximum_unbounded = _parse_bound(max_text)
    return RuleCardinality(
        minimum=minimum,
        maximum=maximum,
        soft_minimum=soft,
        minimum_unbounded=minimum_unbounded,
        maximum_unbounded=maximum_unbounded,
    )


def _parse_bound(value: str) -> tuple[int | None, bool]:
    lowered = value.strip().lower()
    if lowered in {"inf", "+inf", "-inf"}:
        return None, True
    try:
        return int(lowered), False
    except ValueError:
        return None, False


def _parse_value_list(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        inner = stripped[1:-1].strip()
        if not inner:
            return ()
        return tuple(part for part in inner.split() if part)
    return (stripped,) if stripped else ()


def _parse_replace_scope(value: str) -> tuple[RuleScopeReplacement, ...] | None:
    stripped = value.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    inner = stripped[1:-1]
    pairs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", inner)
    if not pairs:
        return None
    return tuple(RuleScopeReplacement(source=source, target=target) for source, target in pairs)


def _index_statement_list(
    statements: tuple[RuleStatement, ...], *, parent_path: tuple[str, ...], indexed: list[IndexedRuleStatement]
) -> None:
    sibling_counts: defaultdict[str, int] = defaultdict(int)
    for statement in statements:
        label = statement.key if statement.key is not None else statement.kind
        occurrence = sibling_counts[label]
        sibling_counts[label] += 1
        declaration_path = (*parent_path, f"{label}#{occurrence}")

        if statement.key is not None:
            family, argument = _parse_key_pattern(statement.key)
            category = _infer_category(statement.key, family)
            indexed.append(
                IndexedRuleStatement(
                    category=category,
                    source_path=statement.source_path,
                    source_range=statement.source_range,
                    key=statement.key,
                    family=family,
                    argument=argument,
                    declaration_path=declaration_path,
                    statement=statement,
                )
            )

        if statement.value.kind in {"block", "tagged_block"}:
            _index_statement_list(statement.value.block, parent_path=declaration_path, indexed=indexed)


def _parse_key_pattern(key: str) -> tuple[str | None, str | None]:
    match = _BRACKET_KEY_PATTERN.match(key)
    if match is None:
        return None, None
    family = match.group("family").strip()
    argument = match.group("argument").strip()
    return family or None, argument or None


def _infer_category(key: str, family: str | None) -> str:
    if family is not None:
        return _CATEGORY_BY_FAMILY.get(family, "pattern")
    if key in _SECTION_KEYS:
        return "section"
    return "rule"
