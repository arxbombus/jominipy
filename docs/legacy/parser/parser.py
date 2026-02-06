from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Iterable

from jominipy.legacy.models.ir import (
    CWTAlias,
    CWTEnum,
    CWTField,
    CWTFieldOptions,
    CWTFieldType,
    CWTInlineBlock,
    CWTModifier,
    CWTReplaceScopes,
    CWTSingleAlias,
    CWTSpec,
    CWTSpecials,
    CWTSubtype,
    CWTType,
    CWTValueSet,
    PrimitiveKind,
)

from .errors import Diagnostic
from .tokens import Token, TokenKind

PRIMITIVE_KINDS: set[PrimitiveKind] = {
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
}

TYPE_OPTION_KEYS = {
    "path",
    "type_per_file",
    "skip_root_key",
    "starts_with",
    "severity",
    "unique",
    "graph_related_types",
    "path_strict",
    "path_file",
    "path_extension",
    "type_key_filter",
    "name_field",
    "should_be_used",
    "key_prefix",
}


def _parse_range_text(text: str) -> tuple[float | None, float | None]:
    if text is None:
        return (None, None)
    text = text.strip()
    if ".." not in text:
        try:
            val = float(text)
            return val, val
        except ValueError:
            return None, None
    lower_raw, upper_raw = text.split("..", 1)

    def _convert(raw: str) -> float | None:
        raw = raw.strip()
        if raw in {"inf", "infinity"}:
            return None
        if raw in {"-inf", "-infinity"}:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    return _convert(lower_raw), _convert(upper_raw)


def _parse_space_list(value: str) -> list[str]:
    if not value:
        return []
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1]
    parts = [p for p in value.replace(",", " ").split(" ") if p]
    return parts


class Parser:
    def __init__(
        self,
        tokens: list[Token],
        *,
        diagnostics: list[Diagnostic] | None = None,
        source: Path | None = None,
    ):
        self.tokens = tokens
        self._pos = 0
        self.diagnostics: list[Diagnostic] = diagnostics or []
        self.source = source
        self.spec = CWTSpec(enums={}, types={}, aliases={}, single_aliases={}, value_sets={}, specials=CWTSpecials())
        self._type_names: set[str] = set()
        self._declared_types: dict[str, CWTType] = {}
        # Specials (links, localisation commands, modifiers, scopes) are populated once magic files are parsed.

    # Public ------------------------------------------------------------------
    def parse(self) -> CWTSpec:
        while not self._check(TokenKind.EOF):
            tok = self._peek()
            if tok.kind == TokenKind.COMMENT:
                self._advance()
                continue
            if self._match_identifier("enums"):
                self._parse_enums_block()
                continue
            if self._match_identifier("types"):
                self._parse_types_block()
                continue
            if self._match_identifier("value_set"):
                self._parse_value_set_definition()
                continue
            if self._match_identifier("alias_name"):
                self._parse_alias_definition(single=False)
                continue
            if self._match_identifier("single_alias"):
                self._parse_alias_definition(single=True)
                continue
            if tok.kind == TokenKind.IDENTIFIER and self._is_type_body_start(str(tok.value)):
                type_name = str(self._advance().value)
                if not self._expect(TokenKind.EQUAL, f"Expected '=' after type name '{type_name}'"):
                    self._skip_to_statement_end()
                    continue
                if not self._expect(TokenKind.LBRACE, f"Expected '{{' to start type '{type_name}' body"):
                    self._skip_to_statement_end()
                    continue
                standalone_type = self._parse_type_body(type_name)
                existing = self.spec.types.get(type_name) or self._declared_types.get(type_name)
                if existing:
                    self._merge_type_def(existing, standalone_type)
                    self.spec.types[type_name] = existing
                else:
                    self.spec.types[type_name] = standalone_type
                    self._type_names.add(type_name)
                continue
            # Unknown top-level construct, skip token to avoid infinite loop.
            self._advance()
        self._apply_rewrites()
        return self.spec

    # Option helpers ---------------------------------------------------------
    def _build_field_options(
        self,
        pending_options: dict[str, str],
        *,
        key_quoted: bool = False,
        value_quoted: bool = False,
        comparison: bool = False,
    ) -> CWTFieldOptions:
        required_scopes: list[str] = []
        if "scope" in pending_options:
            required_scopes = _parse_space_list(pending_options["scope"])
        push_scope = pending_options.get("push_scope")
        replace_scope_raw = pending_options.get("replace_scope")
        replace_scopes: CWTReplaceScopes | None = None
        if replace_scope_raw:
            replace_scopes = CWTReplaceScopes()
            parts = replace_scope_raw.replace(",", " ").split()
            for part in parts:
                if ":" not in part:
                    continue
                key, val = part.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key == "root":
                    replace_scopes.root = val
                elif key == "this":
                    replace_scopes.this = val
                elif key.startswith("from"):
                    replace_scopes.froms.append(val)
                elif key.startswith("prev"):
                    replace_scopes.prevs.append(val)
        reference: dict[str, str] | None = None
        if "outgoingReferenceLabel" in pending_options:
            reference = {"direction": "outgoing", "label": pending_options["outgoingReferenceLabel"]}
        elif "incomingReferenceLabel" in pending_options:
            reference = {"direction": "incoming", "label": pending_options["incomingReferenceLabel"]}
        error_if_only_match = pending_options.get("error_if_only_match")
        severity = pending_options.get("severity")
        type_hint = pending_options.get("type_hint")
        extra = {
            k: v
            for k, v in pending_options.items()
            if k
            not in {
                "scope",
                "push_scope",
                "replace_scope",
                "outgoingReferenceLabel",
                "incomingReferenceLabel",
                "error_if_only_match",
                "severity",
                "type_hint",
                "cardinality",
            }
        }
        return CWTFieldOptions(
            required_scopes=required_scopes,
            push_scope=push_scope,
            replace_scopes=replace_scopes,
            severity=severity,
            comparison=comparison,
            reference=reference,
            key_quoted=key_quoted,
            value_quoted=value_quoted,
            error_if_only_match=error_if_only_match,
            type_hint=type_hint,
            extra=extra,
        )

    # Blocks ------------------------------------------------------------------
    def _parse_enums_block(self) -> None:
        if not self._expect(TokenKind.EQUAL, "Expected '=' after 'enums'"):
            return
        if not self._expect(TokenKind.LBRACE, "Expected '{' to start enums block"):
            return
        pending_doc: str | None = None
        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            doc_update = self._consume_comments()
            if doc_update is not None:
                if doc_update:
                    pending_doc = doc_update
                continue
            if not self._check(TokenKind.IDENTIFIER):
                self._advance()
                continue
            is_complex = self._peek().value == "complex_enum"
            if self._peek().value not in {"enum", "complex_enum"}:
                self._advance()
                continue
            self._advance()
            enum_name = self._parse_bracket_name()
            if enum_name is None:
                self._skip_to_block_end()
                continue
            if not self._expect(TokenKind.EQUAL, "Expected '=' after enum name"):
                self._skip_to_block_end()
                continue
            if is_complex:
                opts = self._parse_complex_enum_body()
                enum = CWTEnum(name=enum_name, values=[], is_complex=True, options=opts, description=pending_doc)
                if self.source:
                    enum.source_path = str(self.source)
                self.spec.enums[enum_name] = enum
            else:
                values = self._parse_value_list_block()
                enum = CWTEnum(
                    name=enum_name,
                    values=values,
                    is_complex=False,
                    description=pending_doc,
                )
                self.spec.enums[enum_name] = enum
            pending_doc = None
        self._expect(TokenKind.RBRACE, "Expected '}' to close enums block")

    def _parse_types_block(self) -> None:
        if not self._expect(TokenKind.EQUAL, "Expected '=' after 'types'"):
            return
        if not self._expect(TokenKind.LBRACE, "Expected '{' to start types block"):
            return
        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            if self._consume_comments():
                continue
            if not self._match_identifier("type"):
                self._advance()
                continue
            type_name = self._parse_bracket_name()
            if type_name is None:
                self._skip_to_block_end()
                continue
            if not self._expect(TokenKind.EQUAL, "Expected '=' after type name"):
                self._skip_to_block_end()
                continue
            if not self._expect(TokenKind.LBRACE, "Expected '{' to start type body"):
                self._skip_to_block_end()
                continue
            cwt_type = self._parse_type_body(type_name)
            self._type_names.add(type_name)
            self.spec.types[type_name] = cwt_type
            self._declared_types[type_name] = cwt_type
        self._expect(TokenKind.RBRACE, "Expected '}' to close types block")

    def _parse_type_body(self, type_name: str) -> CWTType:
        type_obj = CWTType(name=type_name)
        pending_doc: str | None = None
        pending_options: dict[str, str] = {}

        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            doc_update = self._consume_comments(pending_options)
            if doc_update is not None:
                if doc_update:
                    pending_doc = doc_update
                continue
            if self._peek().kind == TokenKind.RBRACE:
                break
            if self._peek().kind != TokenKind.IDENTIFIER:
                self._advance()
                continue
            name_token = self._advance()
            name_value = str(name_token.value)

            if name_value == "subtype" and self._check(TokenKind.LBRACKET):
                subtype_name = self._parse_bracket_name()
                subtype_opts = pending_options
                pending_options = {}
                pending_doc = None
                if self._match(TokenKind.EQUAL) and self._match(TokenKind.LBRACE):
                    self._skip_block()
                if subtype_name:
                    type_obj.subtypes.append(CWTSubtype(name=subtype_name, options=subtype_opts))
                continue

            if name_value in TYPE_OPTION_KEYS:
                if not self._expect(TokenKind.EQUAL, f"Expected '=' after option '{name_value}'"):
                    self._skip_to_statement_end()
                    continue
                option_value = self._parse_simple_value()
                if option_value is not None:
                    type_obj.raw_options[name_value] = option_value
                    if name_value == "path":
                        type_obj.path_options["paths"] = option_value
                    elif name_value == "path_strict":
                        type_obj.path_options["path_strict"] = option_value
                    elif name_value == "path_file":
                        type_obj.path_options["path_file"] = option_value
                    elif name_value == "path_extension":
                        type_obj.path_options["path_extension"] = option_value
                    elif name_value == "skip_root_key":
                        type_obj.skip_root_key = _parse_space_list(option_value)
                    elif name_value == "starts_with":
                        type_obj.starts_with = option_value
                    elif name_value == "type_key_filter":
                        type_obj.type_key_filter = {
                            "values": _parse_space_list(option_value),
                            "negative": "<>" in option_value,
                        }
                    elif name_value == "unique":
                        type_obj.unique = option_value.lower() == "yes"
                    elif name_value == "should_be_used":
                        type_obj.should_be_used = option_value.lower() == "yes"
                    elif name_value == "key_prefix":
                        type_obj.key_prefix = option_value
                    elif name_value == "name_field":
                        type_obj.name_field = option_value
                    elif name_value == "graph_related_types":
                        type_obj.graph_related_types = _parse_space_list(option_value)
                pending_options = {}
                pending_doc = None
                continue

            if not self._expect(TokenKind.EQUAL, f"Expected '=' after field name '{name_value}'"):
                self._skip_to_statement_end()
                continue

            field_type = self._parse_field_type()
            min_count, max_count, warn_only_min = self._apply_cardinality(pending_options)
            options = {k: v for k, v in pending_options.items() if k != "cardinality"}
            key_quoted = bool(name_token.raw and str(name_token.raw).startswith('"'))
            value_quoted = bool(field_type.raw and str(field_type.raw).startswith('"'))
            options_meta = self._build_field_options(
                pending_options,
                key_quoted=key_quoted,
                value_quoted=value_quoted,
                comparison=False,
            )
            field = CWTField(
                name=name_value,
                type=field_type,
                min_count=min_count,
                max_count=max_count,
                warn_only_min=warn_only_min,
                doc=pending_doc,
                options=options,
                options_meta=options_meta,
            )
            type_obj.fields.append(field)
            pending_options = {}
            pending_doc = None
            if self._match(TokenKind.LBRACE):
                inline_fields = self._parse_inline_block()
                field.inline_block = CWTInlineBlock(fields=inline_fields)

        self._expect(TokenKind.RBRACE, f"Expected '}}' to close type '{type_name}'")
        return type_obj

    def _parse_value_set_definition(self) -> None:
        name = self._parse_bracket_name()
        if name is None:
            self._skip_to_statement_end()
            return
        if not self._expect(TokenKind.EQUAL, "Expected '=' after value_set name"):
            self._skip_to_statement_end()
            return
        values = self._parse_value_list_block()
        self.spec.value_sets[name] = CWTValueSet(name=name, values=values)

    def _parse_alias_definition(self, *, single: bool) -> None:
        name = self._parse_bracket_name()
        if name is None:
            self._skip_to_statement_end()
            return
        if not self._expect(TokenKind.EQUAL, "Expected '=' after alias name"):
            self._skip_to_statement_end()
            return
        if not self._expect(TokenKind.LBRACE, "Expected '{' to start alias body"):
            self._skip_to_statement_end()
            return
        fields = self._parse_field_block()
        if single:
            self.spec.single_aliases[name] = CWTSingleAlias(name=name, fields=fields)
        else:
            self.spec.aliases[name] = CWTAlias(name=name, fields=fields)

    # Helpers -----------------------------------------------------------------
    def _parse_field_block(self) -> list[CWTField]:
        pending_doc: str | None = None
        pending_options: dict[str, str] = {}
        fields: list[CWTField] = []

        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            doc_update = self._consume_comments(pending_options)
            if doc_update is not None:
                if doc_update:
                    pending_doc = doc_update
                continue
            if self._peek().kind == TokenKind.RBRACE:
                break
            if self._peek().kind != TokenKind.IDENTIFIER:
                self._advance()
                continue
            name_tok = self._advance()
            name_value = str(name_tok.value)
            if self._check(TokenKind.LBRACKET):
                bracket = self._parse_bracket_name()
                if bracket is not None:
                    name_value = f"{name_value}[{bracket}]"
            if not self._expect(TokenKind.EQUAL, f"Expected '=' after field name '{name_value}'"):
                self._skip_to_statement_end()
                continue
            field_type = self._parse_field_type()
            min_count, max_count, warn_only_min = self._apply_cardinality(pending_options)
            options = {k: v for k, v in pending_options.items() if k != "cardinality"}
            key_quoted = bool(name_tok.raw and str(name_tok.raw).startswith('"'))
            value_quoted = bool(field_type.raw and str(field_type.raw).startswith('"'))
            options_meta = self._build_field_options(
                pending_options,
                key_quoted=key_quoted,
                value_quoted=value_quoted,
                comparison=False,
            )
            fields.append(
                CWTField(
                    name=name_value,
                    type=field_type,
                    min_count=min_count,
                    max_count=max_count,
                    warn_only_min=warn_only_min,
                    doc=pending_doc,
                    options=options,
                    options_meta=options_meta,
                )
            )
            pending_doc = None
            pending_options = {}
            if self._match(TokenKind.LBRACE):
                inline_fields = self._parse_inline_block()
                fields[-1].inline_block = CWTInlineBlock(fields=inline_fields)

        self._expect(TokenKind.RBRACE, "Expected '}' to close alias/value_set body")
        return fields

    def _parse_inline_block(self) -> list[CWTField]:
        # assumes opening brace already consumed
        fields: list[CWTField] = []
        pending_doc: str | None = None
        pending_options: dict[str, str] = {}

        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            doc_update = self._consume_comments(pending_options)
            if doc_update is not None:
                if doc_update:
                    pending_doc = doc_update
                continue
            tok = self._peek()
            if tok.kind == TokenKind.RBRACE:
                break
            if tok.kind != TokenKind.IDENTIFIER:
                self._advance()
                continue
            name_tok = self._advance()
            name_value = str(name_tok.value)
            if self._check(TokenKind.LBRACKET):
                bracket = self._parse_bracket_name()
                if bracket is not None:
                    name_value = f"{name_value}[{bracket}]"
            if not self._expect(TokenKind.EQUAL, f"Expected '=' after inline field '{name_value}'"):
                self._skip_to_statement_end()
                continue
            field_type = self._parse_field_type()
            min_count, max_count, warn_only_min = self._apply_cardinality(pending_options)
            options = {k: v for k, v in pending_options.items() if k != "cardinality"}
            key_quoted = bool(name_tok.raw and str(name_tok.raw).startswith('"'))
            value_quoted = bool(field_type.raw and str(field_type.raw).startswith('"'))
            options_meta = self._build_field_options(
                pending_options,
                key_quoted=key_quoted,
                value_quoted=value_quoted,
                comparison=False,
            )
            inline_field = CWTField(
                name=name_value,
                type=field_type,
                min_count=min_count,
                max_count=max_count,
                warn_only_min=warn_only_min,
                doc=pending_doc,
                options=options,
                options_meta=options_meta,
            )
            pending_doc = None
            pending_options = {}
            if self._match(TokenKind.LBRACE):
                inline_field.inline_block = CWTInlineBlock(fields=self._parse_inline_block())
            fields.append(inline_field)

        self._expect(TokenKind.RBRACE, "Expected '}' to close inline block")
        return fields

    def _parse_field_type(self) -> CWTFieldType:
        tok = self._peek()
        if tok.kind == TokenKind.LBRACE:
            return CWTFieldType(kind="unknown", name="", raw=None)
        if tok.kind == TokenKind.LT:
            self._advance()
            pieces: list[str] = []
            while not self._check(TokenKind.GT) and not self._check(TokenKind.EOF):
                inner_tok = self._advance()
                if inner_tok.raw is not None:
                    pieces.append(inner_tok.raw)
            self._expect(TokenKind.GT, "Expected '>' to close type reference")
            name = "".join(pieces).strip()
            return CWTFieldType(kind="type_ref", name=name, raw=f"<{name}>")

        if tok.kind == TokenKind.IDENTIFIER:
            word = str(tok.value)
            self._advance()
            # Complex type with prefix/suffix e.g., foo<bar>baz
            if self._check(TokenKind.LT):
                self._advance()
                inner: list[str] = []
                while not self._check(TokenKind.GT) and not self._check(TokenKind.EOF):
                    inner_tok = self._advance()
                    inner.append(inner_tok.raw if inner_tok.raw is not None else str(inner_tok.value))
                self._expect(TokenKind.GT, "Expected '>' to close type reference")
                suffix_parts: list[str] = []
                while self._peek().kind == TokenKind.IDENTIFIER:
                    suffix_parts.append(str(self._advance().value))
                inner_name = "".join(inner).strip()
                suffix = "".join(suffix_parts)
                raw_value = f"{word}<{inner_name}>{suffix}"
                return CWTFieldType(
                    kind="type_ref_complex",
                    name=inner_name,
                    raw=raw_value,
                    meta={"prefix": word, "suffix": suffix},
                )
            if self._check(TokenKind.LBRACKET):
                target_name = self._parse_bracket_name()
                raw_value = f"{word}[{target_name}]"
                if word == "enum":
                    return CWTFieldType(kind="enum_ref", name=target_name or "", raw=raw_value)
                if word in {"value_set", "value"}:
                    return CWTFieldType(kind="value_set", name=target_name or "", raw=raw_value)
                if word in {"single_alias_right", "alias_match_left", "alias_match_right"}:
                    return CWTFieldType(kind=word, name=target_name or "", raw=raw_value, meta={"direction": word})
                if word in {"scope", "scope_field"}:
                    return CWTFieldType(kind="scope_field", name=target_name or "", raw=raw_value)
                if word == "scope_group":
                    return CWTFieldType(kind="scope_group", name=target_name or "", raw=raw_value)
                if word == "event_target":
                    return CWTFieldType(kind="event_target", name=target_name or "", raw=raw_value)
                if word == "filepath":
                    meta: dict[str, str] = {}
                    if "," in (target_name or ""):
                        folder, ext = (target_name or "").split(",", 1)
                        meta = {"folder": folder.strip(), "extension": ext.strip()}
                    else:
                        meta = {"folder": target_name or ""}
                    return CWTFieldType(kind="filepath", name=target_name or "", raw=raw_value, meta=meta)
                if word == "icon":
                    return CWTFieldType(
                        kind="icon", name=target_name or "", raw=raw_value, meta={"folder": target_name or ""}
                    )
                if word in {
                    "variable_field",
                    "int_variable_field",
                    "value_field",
                    "int_value_field",
                    "variable_field_32",
                    "int_variable_field_32",
                }:
                    min_val, max_val = _parse_range_text(target_name or "")
                    meta: dict[str, str] = {}
                    if min_val is not None:
                        meta["min"] = str(min_val)
                    if max_val is not None:
                        meta["max"] = str(max_val)
                    if "int" in word:
                        meta["integer"] = "true"
                    if word.endswith("_32"):
                        meta["bits"] = "32"
                    return CWTFieldType(kind="value_marker", name=word, raw=raw_value, meta=meta)
                return CWTFieldType(kind="alias_ref", name=target_name or "", raw=raw_value)
            if word == "enum":
                return CWTFieldType(kind="enum_ref", name="", raw=tok.raw)
            if word in {
                "colour_field",
                "color_field",
            }:
                return CWTFieldType(kind="colour_field", name=word, raw=tok.raw or word)
            if word == "ignore_field":
                return CWTFieldType(kind="ignore_field", name=word, raw=tok.raw or word)
            if word in {"scope_field", "scope"}:
                return CWTFieldType(kind="scope_field", name=word, raw=tok.raw)
            if word in {
                "variable_field",
                "int_variable_field",
                "value_field",
                "int_value_field",
                "variable_field_32",
                "int_variable_field_32",
            }:
                return CWTFieldType(kind="value_marker", name=word, raw=tok.raw)
            if word in PRIMITIVE_KINDS:
                return CWTFieldType(kind="primitive", name=word, raw=tok.raw)
            return CWTFieldType(kind="unknown", name=word, raw=tok.raw)

        if tok.kind in {TokenKind.STRING, TokenKind.NUMBER}:
            self._advance()
            return CWTFieldType(kind="unknown", name=str(tok.value), raw=tok.raw)

        self.diagnostics.append(
            Diagnostic("Unexpected token while parsing field type", tok.line, tok.column, self.source)
        )
        self._advance()
        return CWTFieldType(kind="unknown", name="", raw=None)

    def _parse_simple_value(self) -> str | None:
        tok = self._peek()
        if tok.kind in {TokenKind.IDENTIFIER, TokenKind.STRING, TokenKind.NUMBER}:
            self._advance()
            return tok.raw if tok.raw is not None else str(tok.value)
        if tok.kind == TokenKind.LT:
            self._advance()
            pieces: list[str] = []
            while not self._check(TokenKind.GT) and not self._check(TokenKind.EOF):
                inner_tok = self._advance()
                pieces.append(inner_tok.raw if inner_tok.raw is not None else str(inner_tok.value))
            self._expect(TokenKind.GT, "Expected '>' to close value")
            return "<" + "".join(pieces).strip() + ">"
        if tok.kind == TokenKind.LBRACE:
            self._skip_block()
            return "{}"
        return None

    def _parse_complex_enum_body(self) -> dict[str, str]:
        options: dict[str, str] = {}
        if not self._expect(TokenKind.LBRACE, "Expected '{' to start complex_enum body"):
            return options
        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            if self._consume_comments(options):
                continue
            tok = self._peek()
            if tok.kind != TokenKind.IDENTIFIER:
                self._advance()
                continue
            key = str(self._advance().value)
            if not self._expect(TokenKind.EQUAL, f"Expected '=' after '{key}' in complex_enum"):
                self._skip_to_statement_end()
                continue
            if self._check(TokenKind.LBRACE):
                self._skip_block()
                continue
            value = self._parse_simple_value()
            if value is not None:
                options[key] = value
        self._expect(TokenKind.RBRACE, "Expected '}' to close complex_enum body")
        return options

    def _parse_value_list_block(self) -> list[str]:
        values: list[str] = []
        if not self._expect(TokenKind.LBRACE, "Expected '{' to start value list"):
            return values
        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            if self._consume_comments():
                continue
            tok = self._peek()
            if tok.kind in {TokenKind.IDENTIFIER, TokenKind.STRING, TokenKind.NUMBER}:
                head = tok.raw if tok.raw is not None else str(tok.value)
                self._advance()
                # Merge placeholder tails like foo@<bar> into a single value.
                if self._check(TokenKind.LT):
                    self._advance()
                    pieces: list[str] = []
                    while not self._check(TokenKind.GT) and not self._check(TokenKind.EOF):
                        inner_tok = self._advance()
                        pieces.append(inner_tok.raw if inner_tok.raw is not None else str(inner_tok.value))
                    self._expect(TokenKind.GT, "Expected '>' to close placeholder")
                    tail = "".join(pieces).strip()
                    values.append(f"{head}<{tail}>")
                elif self._check(TokenKind.LBRACKET):
                    tail = self._parse_bracket_name()
                    values.append(f"{head}[{tail}]")
                else:
                    values.append(head)
                continue
            if tok.kind == TokenKind.LBRACE:
                self._skip_block()
                continue
            if tok.kind == TokenKind.RBRACE:
                break
            self._advance()
        self._expect(TokenKind.RBRACE, "Expected '}' to close value list")
        return values

    def _parse_bracket_name(self) -> str | None:
        if not self._expect(TokenKind.LBRACKET, "Expected '['"):
            return None
        pieces: list[str] = []
        while not self._check(TokenKind.RBRACKET) and not self._check(TokenKind.EOF):
            tok = self._advance()
            if tok.raw:
                pieces.append(tok.raw)
            else:
                pieces.append(str(tok.value))
        if not self._expect(TokenKind.RBRACKET, "Expected ']'"):
            return None
        return "".join(pieces).strip()

    def _apply_cardinality(self, options: dict[str, str]) -> tuple[int, int | None, bool]:
        raw = options.get("cardinality")
        warn_only_min = False
        if raw is None:
            return 0, None, warn_only_min
        text = raw.strip()
        if text.startswith("~"):
            warn_only_min = True
            text = text[1:].strip()
        if ".." in text:
            min_raw, max_raw = text.split("..", 1)
            min_count = self._parse_int(min_raw.strip(), fallback=0) or 0
            max_count = (
                None if max_raw.strip() in {"inf", "infinity"} else self._parse_int(max_raw.strip(), fallback=None)
            )
            return min_count, max_count, warn_only_min
        count = self._parse_int(text, fallback=0) or 0
        return count, count, warn_only_min

    def _parse_int(self, text: str, fallback: int | None) -> int | None:
        try:
            return int(text)
        except ValueError:
            return fallback

    # Comment handling --------------------------------------------------------
    def _consume_comments(self, options: dict[str, str] | None = None) -> str | None:
        if self._peek().kind != TokenKind.COMMENT:
            return None
        text = str(self._advance().value or "")
        stripped = text.lstrip("#").strip()
        if text.startswith("###"):
            return stripped
        if text.startswith("##") and options is not None:
            if "=" in stripped:
                key, value = stripped.split("=", 1)
                options[key.strip()] = value.strip()
            elif stripped:
                options[stripped] = ""
        return ""

    # Navigation --------------------------------------------------------------
    def _peek(self, ahead: int = 0) -> Token:
        index = self._pos + ahead
        if index >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[index]

    def _advance(self) -> Token:
        tok = self._peek()
        self._pos = min(self._pos + 1, len(self.tokens) - 1)
        return tok

    def _check(self, kind: TokenKind) -> bool:
        return self._peek().kind == kind

    def _match(self, kind: TokenKind) -> bool:
        if self._check(kind):
            self._advance()
            return True
        return False

    def _match_identifier(self, value: str) -> bool:
        tok = self._peek()
        if tok.kind == TokenKind.IDENTIFIER and str(tok.value) == value:
            self._advance()
            return True
        return False

    def _expect(self, kind: TokenKind, message: str) -> bool:
        if self._check(kind):
            self._advance()
            return True
        tok = self._peek()
        self.diagnostics.append(Diagnostic(message, tok.line, tok.column, source=self.source))
        return False

    def _skip_block(self) -> None:
        depth = 1
        while depth > 0 and not self._check(TokenKind.EOF):
            tok = self._advance()
            if tok.kind == TokenKind.LBRACE:
                depth += 1
            elif tok.kind == TokenKind.RBRACE:
                depth -= 1

    def _skip_to_block_end(self) -> None:
        while not self._check(TokenKind.RBRACE) and not self._check(TokenKind.EOF):
            self._advance()
        if self._check(TokenKind.RBRACE):
            self._advance()

    def _skip_to_statement_end(self) -> None:
        while not self._check(TokenKind.EOF) and self._peek().kind not in {TokenKind.RBRACE}:
            if self._peek().kind == TokenKind.COMMENT:
                self._advance()
                continue
            if self._peek().kind == TokenKind.LBRACE:
                self._skip_block()
                break
            self._advance()

    # Rewrites ---------------------------------------------------------------
    def _apply_rewrites(self) -> None:
        seen_fields: set[int] = set()
        seen_inline_blocks: set[int] = set()

        def rewrite_fields_iter(fields: list[CWTField]) -> None:
            stack = list(fields)
            while stack:
                field = stack.pop()
                if id(field) in seen_fields:
                    continue
                seen_fields.add(id(field))
                if field.type.kind == "single_alias_right":
                    target = field.type.name
                    alias = self.spec.single_aliases.get(target) or self.spec.aliases.get(target)
                    if alias:
                        inlined_fields = deepcopy(alias.fields)
                        field.inline_block = CWTInlineBlock(fields=inlined_fields)
                        field.type = CWTFieldType(
                            kind="alias_ref", name=target, raw=field.type.raw, meta=field.type.meta
                        )
                        field.options_meta.extra["inlined_single_alias"] = target
                if field.type.kind == "colour_field":
                    field.options_meta.extra["colour_field"] = True
                if field.type.kind == "ignore_field":
                    field.options_meta.extra["ignore_field"] = True
                if field.type.kind == "value_marker":
                    is_int = "int" in field.type.name
                    base_kind = "int" if is_int else "float"
                    field.type = CWTFieldType(
                        kind="primitive",
                        name=base_kind,
                        raw=field.type.raw,
                        meta=dict(field.type.meta),
                    )
                if field.inline_block and id(field.inline_block) not in seen_inline_blocks:
                    seen_inline_blocks.add(id(field.inline_block))
                    stack.extend(field.inline_block.fields)

        for type_def in self.spec.types.values():
            rewrite_fields_iter(type_def.fields)
        for alias in self.spec.aliases.values():
            rewrite_fields_iter(alias.fields)
        for single_alias in self.spec.single_aliases.values():
            rewrite_fields_iter(single_alias.fields)

    def _is_type_body_start(self, name: str) -> bool:
        if not self._check(TokenKind.IDENTIFIER):
            return False
        if name in {"enums", "types", "value_set", "alias_name", "single_alias"}:
            return False
        return self._peek(1).kind == TokenKind.EQUAL and self._peek(2).kind == TokenKind.LBRACE

    def _merge_type_def(self, target: CWTType, incoming: CWTType) -> None:
        target.fields.extend(incoming.fields)
        target.raw_options.update(incoming.raw_options)
        target.subtypes.extend(incoming.subtypes)
        target.path_options.update(incoming.path_options)
        if incoming.skip_root_key:
            target.skip_root_key.extend(v for v in incoming.skip_root_key if v not in target.skip_root_key)
        if incoming.starts_with:
            target.starts_with = target.starts_with or incoming.starts_with
        if incoming.type_key_filter and not target.type_key_filter:
            target.type_key_filter = incoming.type_key_filter
        target.unique = target.unique or incoming.unique
        target.should_be_used = target.should_be_used or incoming.should_be_used
        if incoming.key_prefix and not target.key_prefix:
            target.key_prefix = incoming.key_prefix
        if incoming.name_field and not target.name_field:
            target.name_field = incoming.name_field
        if incoming.graph_related_types:
            target.graph_related_types.extend(
                v for v in incoming.graph_related_types if v not in target.graph_related_types
            )
        if incoming.display_name and not target.display_name:
            target.display_name = incoming.display_name


def merge_specs(specs: Iterable[CWTSpec]) -> CWTSpec:
    merged = CWTSpec(enums={}, types={}, aliases={}, single_aliases={}, value_sets={}, specials=CWTSpecials())
    merged_modifier_map: dict[str, CWTModifier] = {}
    for spec in specs:
        merged.enums.update(spec.enums)
        for name, type_def in spec.types.items():
            if name in merged.types:
                merged.types[name].fields.extend(type_def.fields)
                merged.types[name].raw_options.update(type_def.raw_options)
                merged.types[name].subtypes.extend(type_def.subtypes)
                merged.types[name].path_options.update(type_def.path_options)
                if type_def.skip_root_key:
                    merged.types[name].skip_root_key.extend(
                        v for v in type_def.skip_root_key if v not in merged.types[name].skip_root_key
                    )
                if type_def.starts_with:
                    merged.types[name].starts_with = merged.types[name].starts_with or type_def.starts_with
                if type_def.type_key_filter and not merged.types[name].type_key_filter:
                    merged.types[name].type_key_filter = type_def.type_key_filter
                merged.types[name].unique = merged.types[name].unique or type_def.unique
                merged.types[name].should_be_used = merged.types[name].should_be_used or type_def.should_be_used
                if type_def.key_prefix and not merged.types[name].key_prefix:
                    merged.types[name].key_prefix = type_def.key_prefix
                if type_def.name_field and not merged.types[name].name_field:
                    merged.types[name].name_field = type_def.name_field
                if type_def.graph_related_types:
                    merged.types[name].graph_related_types.extend(
                        v for v in type_def.graph_related_types if v not in merged.types[name].graph_related_types
                    )
                if type_def.display_name and not merged.types[name].display_name:
                    merged.types[name].display_name = type_def.display_name
            else:
                merged.types[name] = type_def
        merged.aliases.update(spec.aliases)
        merged.single_aliases.update(spec.single_aliases)
        for name, vs in spec.value_sets.items():
            if name in merged.value_sets:
                merged.value_sets[name].values.extend(v for v in vs.values if v not in merged.value_sets[name].values)
            else:
                merged.value_sets[name] = vs
        merged.specials.scopes.update(spec.specials.scopes)
        merged.specials.links.update(spec.specials.links)
        for folder in spec.specials.folders:
            if folder not in merged.specials.folders:
                merged.specials.folders.append(folder)
        for modifier in spec.specials.modifiers:
            merged_modifier_map[modifier.name] = modifier
        for name, vs in spec.specials.values.items():
            if name in merged.specials.values:
                merged.specials.values[name].values.extend(
                    v for v in vs.values if v not in merged.specials.values[name].values
                )
            else:
                merged.specials.values[name] = vs
        merged.specials.localisation_commands.update(spec.specials.localisation_commands)
    merged.specials.modifiers = list(merged_modifier_map.values())
    return merged
