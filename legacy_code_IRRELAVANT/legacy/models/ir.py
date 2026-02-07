from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Supported primitive kinds found in CWT configs.
PrimitiveKind = Literal[
    "bool",
    "int",
    "float",
    "scalar",
    "percentage_field",
    "localisation",
    "localisation_synced",
    "localisation_inline",
    "filepath",
    "icon",
    "date_field",
    "scope",
    "scope_field",
    "variable_field",
    "int_variable_field",
    "value_field",
    "int_value_field",
]


@dataclass
class CWTEnum:
    name: str
    values: list[str]
    is_complex: bool = False
    source_path: str | None = None
    options: dict[str, str] = field(default_factory=dict)
    description: str | None = None


@dataclass
class CWTFieldType:
    kind: Literal[
        "primitive",
        "enum_ref",
        "type_ref",
        "type_ref_complex",
        "alias_ref",
        "value_set",
        "value_marker",
        "unknown",
        "alias_match_left",
        "alias_match_right",
        "single_alias_right",
        "colour_field",
        "ignore_field",
        "scope_field",
        "scope_group",
        "event_target",
        "filepath",
        "icon",
    ]
    name: str
    raw: str | None = None
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class CWTReplaceScopes:
    root: str | None = None
    this: str | None = None
    froms: list[str] = field(default_factory=list)
    prevs: list[str] = field(default_factory=list)


@dataclass
class CWTFieldOptions:
    required_scopes: list[str] = field(default_factory=list)
    push_scope: str | None = None
    replace_scopes: CWTReplaceScopes | None = None
    severity: str | None = None
    comparison: bool = False
    reference: dict[str, str] | None = None
    key_quoted: bool = False
    value_quoted: bool = False
    error_if_only_match: str | None = None
    type_hint: str | None = None
    extra: dict[str, str | bool] = field(default_factory=dict)


@dataclass
class CWTInlineBlock:
    fields: list[CWTField] = field(default_factory=list)


@dataclass
class CWTField:
    name: str
    type: CWTFieldType
    min_count: int = 0
    max_count: int | None = None
    warn_only_min: bool = False
    doc: str | None = None
    options: dict[str, str] = field(default_factory=dict)
    options_meta: CWTFieldOptions = field(default_factory=CWTFieldOptions)
    inline_block: CWTInlineBlock | None = None


@dataclass
class CWTSubtype:
    name: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class CWTType:
    name: str
    fields: list[CWTField] = field(default_factory=list)
    key_type: CWTFieldType | None = None
    subtypes: list[CWTSubtype] = field(default_factory=list)
    raw_options: dict[str, str] = field(default_factory=dict)
    path_options: dict[str, str] = field(default_factory=dict)
    skip_root_key: list[str] = field(default_factory=list)
    starts_with: str | None = None
    type_key_filter: dict[str, list[str] | bool] | None = None
    unique: bool = False
    should_be_used: bool = False
    key_prefix: str | None = None
    name_field: str | None = None
    graph_related_types: list[str] = field(default_factory=list)
    display_name: str | None = None


@dataclass
class CWTAlias:
    name: str
    fields: list[CWTField] = field(default_factory=list)


@dataclass
class CWTSingleAlias:
    name: str
    fields: list[CWTField] = field(default_factory=list)


@dataclass
class CWTValueSet:
    name: str
    values: list[str] = field(default_factory=list)


# Magic file payloads
@dataclass
class CWTScopeDef:
    display_name: str
    aliases: list[str] = field(default_factory=list)
    data_type_name: str | None = None
    is_subscope_of: list[str] = field(default_factory=list)


@dataclass
class CWTLink:
    name: str
    desc: str | None = None
    from_data: bool = False
    type: str | None = None  # scope/both
    data_source: str | None = None
    prefix: str | None = None
    input_scopes: list[str] = field(default_factory=list)
    output_scope: str | None = None


@dataclass
class CWTModifier:
    name: str
    scope_group: str


@dataclass
class CWTLocalisationCommand:
    name: str
    scopes: list[str]


@dataclass
class CWTSpecials:
    scopes: dict[str, CWTScopeDef] = field(default_factory=dict)
    links: dict[str, CWTLink] = field(default_factory=dict)
    folders: list[str] = field(default_factory=list)
    modifiers: list[CWTModifier] = field(default_factory=list)
    values: dict[str, CWTValueSet] = field(default_factory=dict)
    localisation_commands: dict[str, CWTLocalisationCommand] = field(default_factory=dict)


@dataclass
class CWTSpec:
    enums: dict[str, CWTEnum]
    types: dict[str, CWTType]
    aliases: dict[str, CWTAlias] = field(default_factory=dict)
    single_aliases: dict[str, CWTSingleAlias] = field(default_factory=dict)
    value_sets: dict[str, CWTValueSet] = field(default_factory=dict)
    specials: CWTSpecials = field(default_factory=CWTSpecials)


__all__ = [
    "CWTAlias",
    "CWTEnum",
    "CWTField",
    "CWTFieldOptions",
    "CWTFieldType",
    "CWTInlineBlock",
    "CWTLink",
    "CWTLocalisationCommand",
    "CWTModifier",
    "CWTReplaceScopes",
    "CWTScopeDef",
    "CWTSingleAlias",
    "CWTSpec",
    "CWTSpecials",
    "CWTSubtype",
    "CWTType",
    "CWTValueSet",
    "PrimitiveKind",
]
