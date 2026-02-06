from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jominipy.legacy.models.ir import (
    CWTEnum,
    CWTLink,
    CWTLocalisationCommand,
    CWTModifier,
    CWTScopeDef,
    CWTSpec,
    CWTSpecials,
    CWTValueSet,
)

from .errors import Diagnostic
from .lexer import Lexer
from .tokens import Token, TokenKind


def _empty_spec() -> CWTSpec:
    return CWTSpec(enums={}, types={}, aliases={}, single_aliases={}, value_sets={}, specials=CWTSpecials())


@dataclass
class MagicStream:
    tokens: list[Token]
    diagnostics: list[Diagnostic]
    source: Path | None
    _pos: int = 0

    # Navigation helpers -----------------------------------------------------
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
        depth = 0
        if self._match(TokenKind.LBRACE):
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

    # Comment and value helpers ---------------------------------------------
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
                if inner_tok.raw is not None:
                    pieces.append(inner_tok.raw)
                else:
                    pieces.append(str(inner_tok.value))
            self._expect(TokenKind.GT, "Expected '>' to close value")
            return "<" + "".join(pieces).strip() + ">"
        if tok.kind == TokenKind.LBRACE:
            self._skip_block()
            return "{}"
        return None

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

    def _seek_identifier(self, value: str) -> bool:
        while not self._check(TokenKind.EOF):
            tok = self._peek()
            if tok.kind == TokenKind.IDENTIFIER and str(tok.value) == value:
                return True
            self._advance()
        return False

    def _parse_scopes_field(self) -> list[str] | None:
        tok = self._peek()
        if tok.kind == TokenKind.IDENTIFIER and str(tok.value) == "any":
            self._advance()
            return []
        if tok.kind == TokenKind.LBRACE:
            return self._parse_value_list_block()
        if tok.kind in {TokenKind.IDENTIFIER, TokenKind.STRING}:
            self._advance()
            return [str(tok.value)]
        return None

    @property
    def identifier_set(self) -> set[str]:
        return {str(t.value) for t in self.tokens if t.kind == TokenKind.IDENTIFIER}


# Parsers --------------------------------------------------------------------
def parse_magic_file(text: str, *, source: Path | None = None) -> CWTSpec | None:
    lexer = Lexer(text, source=source)
    tokens, diagnostics = lexer.lex()
    stream = MagicStream(tokens, diagnostics, source)
    name = source.name.lower() if source else ""
    base = name[:-4] if name.endswith(".cwt") else name

    def name_matches(prefix: str) -> bool:
        return base == prefix or base.startswith(f"{prefix}_")

    identifiers = stream.identifier_set

    if name_matches("scopes") or "scopes" in identifiers:
        return _parse_scopes(stream)
    if name_matches("links") or "links" in identifiers:
        return _parse_links(stream)
    if name_matches("folders"):
        return _parse_folders(stream)
    if name_matches("modifier_categories") or "modifier_categories" in identifiers:
        return _parse_modifier_categories(stream)
    if name_matches("modifiers") or "modifiers" in identifiers:
        return _parse_modifiers(stream)
    if base in {"values", "variables"} or name_matches("values") or "values" in identifiers:
        return _parse_values(stream)
    if name_matches("localisation") or "localisation_commands" in identifiers:
        return _parse_localisation(stream)
    if name_matches("shared_enums") or "shared_enums" in identifiers:
        return _parse_shared_enums(stream)
    return None


def _parse_scopes(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    if not stream._seek_identifier("scopes"):
        return spec
    if not stream._expect(TokenKind.IDENTIFIER, "Expected 'scopes'"):
        return spec
    if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'scopes'"):
        return spec
    if not stream._expect(TokenKind.LBRACE, "Expected '{' to start scopes block"):
        return spec

    while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
        doc_update = stream._consume_comments()
        if doc_update is not None:
            continue
        tok = stream._peek()
        if tok.kind not in {TokenKind.IDENTIFIER, TokenKind.STRING}:
            stream._advance()
            continue
        name_tok = stream._advance()
        scope_name = str(name_tok.value)
        if not stream._expect(TokenKind.EQUAL, f"Expected '=' after scope name '{scope_name}'"):
            stream._skip_to_block_end()
            continue
        if not stream._expect(TokenKind.LBRACE, "Expected '{' to start scope body"):
            stream._skip_to_block_end()
            continue

        aliases: list[str] = []
        data_type_name: str | None = None
        is_subscope_of: list[str] = []

        while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
            doc_update = stream._consume_comments()
            if doc_update is not None:
                continue
            inner = stream._peek()
            if inner.kind != TokenKind.IDENTIFIER:
                stream._advance()
                continue
            field_name = str(stream._advance().value)
            if not stream._expect(TokenKind.EQUAL, f"Expected '=' after '{field_name}' in scope '{scope_name}'"):
                stream._skip_to_statement_end()
                continue
            if field_name == "aliases":
                aliases = stream._parse_value_list_block()
            elif field_name == "data_type_name":
                value = stream._parse_simple_value()
                if value is not None:
                    data_type_name = value
            elif field_name == "is_subscope_of":
                is_subscope_of = stream._parse_value_list_block()
            else:
                stream._skip_to_statement_end()

        stream._expect(TokenKind.RBRACE, f"Expected '}}' to close scope '{scope_name}'")
        scope_def = CWTScopeDef(
            display_name=scope_name, aliases=aliases, data_type_name=data_type_name, is_subscope_of=is_subscope_of
        )
        spec.specials.scopes[scope_name] = scope_def

    stream._expect(TokenKind.RBRACE, "Expected '}' to close scopes block")
    return spec


def _parse_links(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    if not stream._seek_identifier("links"):
        return spec
    if not stream._expect(TokenKind.IDENTIFIER, "Expected 'links'"):
        return spec
    if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'links'"):
        return spec
    if not stream._expect(TokenKind.LBRACE, "Expected '{' to start links block"):
        return spec

    while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
        pending_doc: str | None = None
        doc_update = stream._consume_comments()
        if doc_update is not None:
            if doc_update:
                pending_doc = doc_update
            continue
        tok = stream._peek()
        if tok.kind != TokenKind.IDENTIFIER:
            stream._advance()
            continue
        name_tok = stream._advance()
        link_name = str(name_tok.value)
        if not stream._expect(TokenKind.EQUAL, f"Expected '=' after link name '{link_name}'"):
            stream._skip_to_block_end()
            continue
        if not stream._expect(TokenKind.LBRACE, "Expected '{' to start link body"):
            stream._skip_to_block_end()
            continue

        link = CWTLink(name=link_name, desc=pending_doc)
        while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
            inner_doc = stream._consume_comments()
            if inner_doc is not None:
                if inner_doc:
                    link.desc = inner_doc
                continue
            inner = stream._peek()
            if inner.kind != TokenKind.IDENTIFIER:
                stream._advance()
                continue
            field_name = str(stream._advance().value)
            if not stream._expect(TokenKind.EQUAL, f"Expected '=' after '{field_name}' in link '{link_name}'"):
                stream._skip_to_statement_end()
                continue
            if field_name == "desc":
                value = stream._parse_simple_value()
                if value is not None:
                    link.desc = value
            elif field_name == "from_data":
                value = stream._parse_simple_value()
                link.from_data = str(value).lower() in {"yes", "true", "1"} if value is not None else False
            elif field_name == "type":
                value = stream._parse_simple_value()
                if value is not None:
                    link.type = value
            elif field_name == "data_source":
                value = stream._parse_simple_value()
                if value is not None:
                    link.data_source = value
            elif field_name == "prefix":
                value = stream._parse_simple_value()
                if value is not None:
                    link.prefix = value
            elif field_name == "input_scopes":
                scopes = stream._parse_scopes_field()
                if scopes is not None:
                    link.input_scopes = scopes
            elif field_name == "output_scope":
                value = stream._parse_simple_value()
                if value is not None:
                    link.output_scope = value
            else:
                stream._skip_to_statement_end()

        stream._expect(TokenKind.RBRACE, f"Expected '}}' to close link '{link_name}'")
        spec.specials.links[link_name] = link

    stream._expect(TokenKind.RBRACE, "Expected '}' to close links block")
    return spec


def _parse_folders(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    while not stream._check(TokenKind.EOF):
        if stream._consume_comments():
            continue
        tok = stream._peek()
        if tok.kind in {TokenKind.IDENTIFIER, TokenKind.STRING}:
            spec.specials.folders.append(str(tok.value))
        stream._advance()
    return spec


def _parse_modifier_categories(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    category_scopes: dict[str, list[str]] = {}
    if not stream._seek_identifier("modifier_categories"):
        return spec
    stream._advance()  # consume identifier
    if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'modifier_categories'"):
        return spec
    if not stream._expect(TokenKind.LBRACE, "Expected '{' to start modifier_categories block"):
        return spec

    while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
        if stream._consume_comments():
            continue
        tok = stream._peek()
        if tok.kind not in {TokenKind.IDENTIFIER, TokenKind.STRING}:
            stream._advance()
            continue
        cat_name = str(stream._advance().value)
        if not stream._expect(TokenKind.EQUAL, f"Expected '=' after modifier category '{cat_name}'"):
            stream._skip_to_block_end()
            continue
        if not stream._expect(TokenKind.LBRACE, "Expected '{' to start modifier category body"):
            stream._skip_to_block_end()
            continue
        scopes: list[str] = []
        while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
            if stream._consume_comments():
                continue
            inner = stream._peek()
            if inner.kind != TokenKind.IDENTIFIER:
                stream._advance()
                continue
            field_name = str(stream._advance().value)
            if not stream._expect(
                TokenKind.EQUAL, f"Expected '=' after '{field_name}' in modifier category '{cat_name}'"
            ):
                stream._skip_to_statement_end()
                continue
            if field_name == "supported_scopes":
                scopes = stream._parse_value_list_block()
            else:
                stream._skip_to_statement_end()
        stream._expect(TokenKind.RBRACE, f"Expected '}}' to close modifier category '{cat_name}'")
        category_scopes[cat_name] = scopes

    stream._expect(TokenKind.RBRACE, "Expected '}' to close modifier_categories block")
    setattr(spec, "_modifier_categories", category_scopes)
    return spec


def _parse_modifiers(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    if not stream._seek_identifier("modifiers"):
        return spec
    stream._advance()  # consume identifier
    if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'modifiers'"):
        return spec
    if not stream._expect(TokenKind.LBRACE, "Expected '{' to start modifiers block"):
        return spec

    while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
        if stream._consume_comments():
            continue
        tok = stream._peek()
        if tok.kind not in {TokenKind.IDENTIFIER, TokenKind.STRING}:
            stream._advance()
            continue
        mod_name = str(stream._advance().value)
        if not stream._expect(TokenKind.EQUAL, f"Expected '=' after modifier name '{mod_name}'"):
            stream._skip_to_statement_end()
            continue
        category_value = stream._parse_simple_value()
        if category_value is None:
            stream._skip_to_statement_end()
            continue
        modifier = CWTModifier(name=mod_name, scope_group=str(category_value))
        spec.specials.modifiers.append(modifier)
    stream._expect(TokenKind.RBRACE, "Expected '}' to close modifiers block")
    return spec


def _parse_values(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    # Some files wrap in values = { value[...] = { ... } }, others may start directly.
    has_outer = False
    if stream._seek_identifier("values"):
        stream._advance()
        has_outer = True
        if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'values'"):
            return spec
        if not stream._expect(TokenKind.LBRACE, "Expected '{' to start values block"):
            return spec
    while not stream._check(TokenKind.EOF):
        if stream._consume_comments():
            continue
        tok = stream._peek()
        if tok.kind != TokenKind.IDENTIFIER or str(tok.value) != "value":
            stream._advance()
            continue
        stream._advance()
        set_name = stream._parse_bracket_name()
        if not set_name:
            stream._skip_to_statement_end()
            continue
        if not stream._expect(TokenKind.EQUAL, "Expected '=' after value[...] name"):
            stream._skip_to_statement_end()
            continue
        values = stream._parse_value_list_block()
        existing = spec.specials.values.get(set_name)
        if existing:
            existing.values.extend(v for v in values if v not in existing.values)
        else:
            spec.specials.values[set_name] = CWTValueSet(name=set_name, values=values)
        if has_outer and stream._check(TokenKind.RBRACE):
            break
    if has_outer:
        stream._expect(TokenKind.RBRACE, "Expected '}' to close values block")
    return spec


def _parse_shared_enums(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    has_outer = False
    if stream._seek_identifier("enums"):
        stream._advance()
        has_outer = True
        if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'enums'"):
            return spec
        if not stream._expect(TokenKind.LBRACE, "Expected '{' to start enums block"):
            return spec

    while not stream._check(TokenKind.EOF):
        if stream._consume_comments():
            continue
        tok = stream._peek()
        if tok.kind != TokenKind.IDENTIFIER or str(tok.value) != "enum":
            stream._advance()
            continue
        stream._advance()
        enum_name = stream._parse_bracket_name()
        if not enum_name:
            stream._skip_to_statement_end()
            continue
        if not stream._expect(TokenKind.EQUAL, "Expected '=' after enum[...] name"):
            stream._skip_to_statement_end()
            continue
        raw_values = stream._parse_value_list_block()
        values: list[str] = []
        seen_values: set[str] = set()
        for v in raw_values:
            if v in seen_values:
                continue
            seen_values.add(v)
            values.append(v)
        existing = spec.enums.get(enum_name)
        if existing:
            for v in values:
                if v not in existing.values:
                    existing.values.append(v)
        else:
            spec.enums[enum_name] = CWTEnum(
                name=enum_name,
                values=values,
                is_complex=False,
                source_path=str(stream.source) if stream.source else None,
                options={},
            )
        if has_outer and stream._check(TokenKind.RBRACE):
            break

    if has_outer:
        stream._expect(TokenKind.RBRACE, "Expected '}' to close enums block")
    return spec


def _parse_localisation(stream: MagicStream) -> CWTSpec:
    spec = _empty_spec()
    if not stream._seek_identifier("localisation_commands"):
        return spec
    stream._advance()
    if not stream._expect(TokenKind.EQUAL, "Expected '=' after 'localisation_commands'"):
        return spec
    if not stream._expect(TokenKind.LBRACE, "Expected '{' to start localisation_commands block"):
        return spec

    while not stream._check(TokenKind.RBRACE) and not stream._check(TokenKind.EOF):
        doc = stream._consume_comments()
        if doc is not None:
            continue
        tok = stream._peek()
        if tok.kind not in {TokenKind.IDENTIFIER, TokenKind.STRING}:
            stream._advance()
            continue
        name = str(stream._advance().value)
        if not stream._expect(TokenKind.EQUAL, f"Expected '=' after localisation command '{name}'"):
            stream._skip_to_statement_end()
            continue
        scopes: list[str] = []
        if stream._check(TokenKind.LBRACE):
            scopes = stream._parse_value_list_block()
        else:
            value = stream._parse_simple_value()
            if value is not None and value != "any":
                scopes = [value]
        spec.specials.localisation_commands[name] = CWTLocalisationCommand(name=name, scopes=scopes)
    stream._expect(TokenKind.RBRACE, "Expected '}' to close localisation_commands block")
    return spec
