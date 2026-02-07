from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, cast

from jominipy.legacy.models.ir import (
    CWTAlias,
    CWTEnum,
    CWTField,
    CWTFieldOptions,
    CWTFieldType,
    CWTSingleAlias,
    CWTSpec,
    CWTSpecials,
    CWTType,
    CWTValueSet,
)
from jominipy.legacy.parser.errors import Diagnostic
from openapi_schema_validator import OAS31Validator
from yamlium import from_dict as yaml_from_dict

PrimitiveSchema = dict[str, Any]


def _dedupe(seq: list[str]) -> list[str]:
    seen = set()
    deduped: list[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def spec_to_dict(
    spec: CWTSpec,
    *,
    include_diagnostics: bool = False,
    diagnostics: list[Diagnostic] | None = None,
) -> dict[str, Any]:
    """Normalize CWTSpec into a JSON-serializable dict."""

    def _field_type(ft: CWTFieldType) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": ft.kind, "name": ft.name}
        if ft.raw is not None:
            data["raw"] = ft.raw
        if getattr(ft, "meta", None):
            data["meta"] = dict(ft.meta)
        return data

    def _options_meta(options: CWTFieldOptions | None) -> dict[str, Any]:
        if not options:
            return {}
        payload: dict[str, Any] = {}
        if options.required_scopes:
            payload["required_scopes"] = list(options.required_scopes)
        if options.push_scope:
            payload["push_scope"] = options.push_scope
        if options.replace_scopes:
            payload["replace_scopes"] = {
                "root": options.replace_scopes.root,
                "this": options.replace_scopes.this,
                "froms": list(options.replace_scopes.froms),
                "prevs": list(options.replace_scopes.prevs),
            }
        if options.severity:
            payload["severity"] = options.severity
        if options.reference:
            payload["reference"] = dict(options.reference)
        if options.comparison:
            payload["comparison"] = True
        if options.key_quoted:
            payload["key_quoted"] = True
        if options.value_quoted:
            payload["value_quoted"] = True
        if options.error_if_only_match:
            payload["error_if_only_match"] = options.error_if_only_match
        if options.type_hint:
            payload["type_hint"] = options.type_hint
        if options.extra:
            payload["extra"] = dict(options.extra)
        return payload

    def _field(f: CWTField) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": f.name,
            "type": _field_type(f.type),
            "min_count": f.min_count,
            "max_count": f.max_count,
            "warn_only_min": f.warn_only_min,
            "options": dict(f.options),
        }
        if f.doc is not None:
            payload["doc"] = f.doc
        if f.inline_block:
            payload["inline_block"] = [_field(nf) for nf in f.inline_block.fields]
        opts_meta = _options_meta(f.options_meta)
        if opts_meta:
            payload["options_meta"] = opts_meta
        return payload

    def _type(t: CWTType) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": t.name,
            "fields": [_field(f) for f in t.fields],
            "subtypes": [{"name": st.name, "options": dict(st.options)} for st in t.subtypes],
            "raw_options": dict(t.raw_options),
        }
        if t.path_options:
            payload["path_options"] = dict(t.path_options)
        if t.skip_root_key:
            payload["skip_root_key"] = list(t.skip_root_key)
        if t.starts_with:
            payload["starts_with"] = t.starts_with
        if t.type_key_filter:
            payload["type_key_filter"] = dict(t.type_key_filter)
        if t.unique:
            payload["unique"] = True
        if t.should_be_used:
            payload["should_be_used"] = True
        if t.key_prefix:
            payload["key_prefix"] = t.key_prefix
        if t.name_field:
            payload["name_field"] = t.name_field
        if t.graph_related_types:
            payload["graph_related_types"] = list(t.graph_related_types)
        if t.display_name:
            payload["display_name"] = t.display_name
        if t.key_type is not None:
            payload["key_type"] = _field_type(t.key_type)
        return payload

    def _alias(a: CWTAlias | CWTSingleAlias) -> dict[str, Any]:
        return {"name": a.name, "fields": [_field(f) for f in a.fields]}

    def _enum(e: CWTEnum) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": e.name,
            "values": _dedupe([str(v) for v in e.values]),
            "is_complex": e.is_complex,
        }
        if e.source_path is not None:
            payload["source_path"] = e.source_path
        if e.options:
            payload["options"] = dict(e.options)
        if e.description:
            payload["description"] = e.description
        return payload

    def _value_set(vs: CWTValueSet) -> dict[str, Any]:
        return {"name": vs.name, "values": _dedupe([str(v) for v in vs.values])}

    def _specials(sp: CWTSpecials) -> dict[str, Any]:
        return {
            "scopes": {
                name: {
                    "display_name": value.display_name,
                    "aliases": _dedupe([str(a) for a in value.aliases]),
                    "data_type_name": value.data_type_name,
                    "is_subscope_of": _dedupe([str(s) for s in value.is_subscope_of]),
                }
                for name, value in sp.scopes.items()
            },
            "links": {
                name: {
                    "desc": link.desc,
                    "from_data": link.from_data,
                    "type": link.type,
                    "data_source": link.data_source,
                    "prefix": link.prefix,
                    "input_scopes": _dedupe([str(s) for s in link.input_scopes]),
                    "output_scope": link.output_scope,
                }
                for name, link in sp.links.items()
            },
            "folders": _dedupe([str(folder) for folder in sp.folders]),
            "modifiers": list({m.name: {"name": m.name, "scope_group": m.scope_group} for m in sp.modifiers}.values()),
            "values": {name: _value_set(v) for name, v in sp.values.items()},
            "localisation_commands": {
                name: {"name": lc.name, "scopes": _dedupe([str(scope) for scope in lc.scopes])}
                for name, lc in sp.localisation_commands.items()
            },
        }

    payload: dict[str, Any] = {
        "enums": {name: _enum(e) for name, e in spec.enums.items()},
        "types": {name: _type(t) for name, t in spec.types.items()},
        "aliases": {name: _alias(a) for name, a in spec.aliases.items()},
        "single_aliases": {name: _alias(a) for name, a in spec.single_aliases.items()},
        "value_sets": {name: _value_set(vs) for name, vs in spec.value_sets.items()},
        "specials": _specials(spec.specials),
    }

    modifier_categories = getattr(spec, "_modifier_categories", None)
    if modifier_categories:
        payload["modifier_categories"] = {
            name: {"supported_scopes": _dedupe(scopes)} for name, scopes in modifier_categories.items()
        }

    if include_diagnostics and diagnostics:
        payload["diagnostics"] = [
            {"message": d.message, "line": d.line, "column": d.column, "source": str(d.source) if d.source else None}
            for d in diagnostics
        ]

    return payload


def _primitive_schema(kind: str) -> PrimitiveSchema:
    mapping: dict[str, PrimitiveSchema] = {
        "bool": {"type": "boolean"},
        "int": {"type": "integer", "format": "int32"},
        "float": {"type": "number", "format": "float"},
        "scalar": {"type": "number"},
        "percentage_field": {"type": "number"},
        "localisation": {"type": "string"},
        "localisation_synced": {"type": "string"},
        "localisation_inline": {"type": "string"},
        "filepath": {"type": "string"},
        "icon": {"type": "string"},
        "date_field": {"type": "string", "format": "date"},
        "scope": {"type": "string"},
        "scope_field": {"type": "string"},
        "variable_field": {"type": "string"},
        "int_variable_field": {"type": "string"},
        "value_field": {"type": "string"},
        "int_value_field": {"type": "string"},
    }
    return mapping.get(kind, {"type": "string"})


def _component_ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _field_schema(field: dict[str, Any]) -> PrimitiveSchema:
    field_type = field["type"]
    kind = field_type["kind"]
    name = field_type["name"]
    raw_value = field_type.get("raw")
    raw_str = str(raw_value) if raw_value is not None else None
    placeholder = raw_str is not None and raw_str.startswith("<") and raw_str.endswith(">")
    meta = field_type.get("meta") or {}
    base: PrimitiveSchema
    inline_block = field.get("inline_block")
    if inline_block:
        base = _object_schema({"fields": inline_block})
    elif kind == "primitive":
        base = _primitive_schema(name)
        if meta.get("min") is not None:
            try:
                base["minimum"] = float(meta["min"])
            except ValueError:
                pass
        if meta.get("max") is not None:
            try:
                base["maximum"] = float(meta["max"])
            except ValueError:
                pass
    elif kind in {"enum_ref", "value_set"}:
        base = _component_ref(name)
    elif kind in {"type_ref", "alias_ref"}:
        base = _component_ref(name)
    elif kind == "type_ref_complex":
        base = _component_ref(name)
        base["x-complex-type"] = {"prefix": meta.get("prefix"), "suffix": meta.get("suffix")}
        if raw_str:
            base["x-raw"] = raw_str
    elif kind == "value_marker":
        base = {"type": "number"}
        if "int" in name:
            base = {"type": "integer", "format": "int32"}
        if meta.get("min") is not None:
            base["minimum"] = float(meta["min"])
        if meta.get("max") is not None:
            base["maximum"] = float(meta["max"])
        base["x-value-marker"] = True
    elif kind in {"alias_match_left", "alias_match_right", "single_alias_right"}:
        base = {
            "type": "string",
            "description": f"Alias reference ({kind.replace('_', ' ')})",
            "x-alias-ref": {"target": name, "kind": kind},
        }
        if meta:
            base["x-alias-ref"].update(meta)
        if raw_str:
            base["x-raw"] = raw_str
    elif kind == "scope_field":
        base = {"type": "string", "description": "Scope reference"}
        if name:
            base["x-scope-target"] = name
        if meta:
            base["x-scope-meta"] = meta
    elif kind == "scope_group":
        base = {"type": "string", "description": "Scope group reference", "x-scope-group": name}
    elif kind == "event_target":
        base = {"type": "string", "description": "Event target reference", "x-event-target": name}
    elif kind == "filepath":
        base = {"type": "string", "description": "File path"}
        if meta:
            base["x-filepath"] = meta
    elif kind == "icon":
        base = {"type": "string", "description": "Icon reference"}
        if meta:
            base["x-icon"] = meta
    elif kind == "colour_field":
        base = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 4, "x-colour-field": True}
    elif kind == "ignore_field":
        base = {"type": "object", "additionalProperties": True, "x-ignore-field": True}
    else:
        base = {"type": "string", "description": f"Unknown type '{name}'"}
        if raw_str:
            base["x-raw"] = raw_str

    min_count = field.get("min_count", 0)
    max_count = field.get("max_count")
    warn_only_min = field.get("warn_only_min", False)
    is_array = max_count is None or max_count > 1 or min_count > 1
    schema: PrimitiveSchema = base
    if is_array:
        schema = {"type": "array", "items": base}
        if min_count:
            schema["minItems"] = min_count
        if max_count is not None:
            schema["maxItems"] = max_count
        if warn_only_min:
            schema["x-warn-only-min"] = True

    if field.get("doc"):
        schema["description"] = field["doc"]
    if field.get("options"):
        schema["x-options"] = field["options"]
    opts_meta = field.get("options_meta") or {}
    if opts_meta.get("required_scopes"):
        schema["x-required-scopes"] = opts_meta["required_scopes"]
    if opts_meta.get("push_scope"):
        schema["x-push-scope"] = opts_meta["push_scope"]
    if opts_meta.get("replace_scopes"):
        schema["x-replace-scopes"] = opts_meta["replace_scopes"]
    if opts_meta.get("severity"):
        schema["x-severity"] = opts_meta["severity"]
    if opts_meta.get("reference"):
        schema["x-reference"] = opts_meta["reference"]
    if opts_meta.get("comparison"):
        schema["x-comparison"] = True
    if opts_meta.get("error_if_only_match"):
        schema["x-error-if-only-match"] = opts_meta["error_if_only_match"]
    if opts_meta.get("type_hint"):
        schema["x-type-hint"] = opts_meta["type_hint"]
    extra = opts_meta.get("extra")
    if extra:
        schema["x-extra"] = extra
    if placeholder and raw_str:
        schema["x-placeholder"] = raw_str
    return schema


def _object_schema(entry: dict[str, Any]) -> PrimitiveSchema:
    props: dict[str, Any] = {}
    required: list[str] = []
    for field in entry.get("fields", []):
        schema = _field_schema(field)
        props[field["name"]] = schema
        if field.get("warn_only_min"):
            continue
        min_count = field.get("min_count", 0)
        if schema.get("type") != "array" and min_count >= 1:
            required.append(field["name"])
        if schema.get("type") == "array" and min_count >= 1 and not schema.get("x-warn-only-min"):
            required.append(field["name"])
    payload: PrimitiveSchema = {"type": "object", "properties": props}
    if required:
        payload["required"] = required
    if entry.get("raw_options"):
        payload["x-raw-options"] = entry["raw_options"]
    if entry.get("subtypes"):
        payload["x-subtypes"] = entry["subtypes"]
    if entry.get("key_type"):
        payload["x-key-type"] = entry["key_type"]
    return payload


def dict_to_openapi(dto: dict[str, Any], *, title: str = "CWT Schema", version: str = "0.1.0") -> dict[str, Any]:
    """Map DTO into an OpenAPI 3.1 document."""
    components: dict[str, Any] = {"schemas": {}}
    schemas = components["schemas"]

    for name, enum in dto.get("enums", {}).items():
        schemas[name] = {
            "type": "string",
            "enum": _dedupe(enum.get("values", [])),
            "description": "Complex enum" if enum.get("is_complex") else "Enum",
        }
        if enum.get("source_path"):
            schemas[name]["x-source-path"] = enum["source_path"]
        if enum.get("options"):
            schemas[name]["x-options"] = enum["options"]

    for name, vs in dto.get("value_sets", {}).items():
        schemas[name] = {"type": "string", "enum": _dedupe(vs.get("values", [])), "description": "Value set"}

    for name, type_entry in dto.get("types", {}).items():
        schemas[name] = _object_schema(type_entry)

    for name, alias in dto.get("aliases", {}).items():
        schemas[name] = _object_schema(alias)

    for name, alias in dto.get("single_aliases", {}).items():
        schemas[name] = _object_schema(alias)

    specials = dto.get("specials", {})
    if specials:
        schemas["SpecialScopes"] = {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "display_name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "data_type_name": {"type": ["string", "null"]},
                    "is_subscope_of": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["display_name", "aliases", "is_subscope_of"],
            },
            "example": specials.get("scopes", {}),
        }
        schemas["SpecialLinks"] = {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "desc": {"type": ["string", "null"]},
                    "from_data": {"type": "boolean"},
                    "type": {"type": ["string", "null"]},
                    "data_source": {"type": ["string", "null"]},
                    "prefix": {"type": ["string", "null"]},
                    "input_scopes": {"type": "array", "items": {"type": "string"}},
                    "output_scope": {"type": ["string", "null"]},
                },
                "required": ["from_data", "input_scopes"],
            },
            "example": specials.get("links", {}),
        }
        schemas["SpecialFolders"] = {
            "type": "array",
            "items": {"type": "string"},
            "example": specials.get("folders", []),
        }
        schemas["SpecialModifiers"] = {
            "type": "array",
            "items": {"type": "object", "properties": {"name": {"type": "string"}, "scope_group": {"type": "string"}}},
            "example": specials.get("modifiers", []),
        }
        schemas["SpecialValues"] = {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
            "example": {k: _dedupe(v.get("values", [])) for k, v in specials.get("values", {}).items()},
        }
        schemas["SpecialLocalisationCommands"] = {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
            "example": {k: _dedupe(v.get("scopes", [])) for k, v in specials.get("localisation_commands", {}).items()},
        }
        if dto.get("modifier_categories"):
            schemas["ModifierCategories"] = {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {"supported_scopes": {"type": "array", "items": {"type": "string"}}},
                },
                "example": dto.get("modifier_categories"),
            }

    openapi: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version},
        "paths": {},
        "components": components,
        "x-cwt-dto": dto,
        "jsonSchemaDialect": "https://spec.openapis.org/oas/3.1/dialect/base",
    }
    return openapi


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    def _needs_quote(text: str) -> bool:
        return text.startswith("@") or ":" in text or text.startswith("<") or text.endswith(">")

    def _quote(text: str) -> str:
        escaped = text.replace("'", "''")
        return f"'{escaped}'"

    def _sanitize(obj: object) -> Any:
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        if isinstance(obj, str):
            if _needs_quote(obj):
                return _quote(obj)
            return obj
        return obj

    path.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = cast(dict[str, Any] | list[Any], _sanitize(payload))
    yml = yaml_from_dict(safe_payload)
    path.write_text(yml.to_yaml(), encoding="utf-8")


def emit_spec(
    spec: CWTSpec,
    out_dir: Path,
    *,
    formats: Iterable[str] = ("openapi-json", "openapi-yaml"),
    include_diagnostics: bool = False,
    diagnostics: list[Diagnostic] | None = None,
    split: bool = False,
    validate: bool = True,
    title: str = "CWT Schema",
    version: str = "0.1.0",
) -> dict[str, Path]:
    """Emit schema artifacts for a CWTSpec."""
    dto = spec_to_dict(spec, include_diagnostics=include_diagnostics, diagnostics=diagnostics)
    openapi_doc = dict_to_openapi(dto, title=title, version=version)

    if validate:
        OAS31Validator.check_schema(openapi_doc)

    written: dict[str, Path] = {}
    for fmt in formats:
        if fmt == "openapi-json":
            target = out_dir / "schema.json"
            _write_json(target, openapi_doc)
            written[fmt] = target
        elif fmt == "openapi-yaml":
            target = out_dir / "schema.yaml"
            _write_yaml(target, openapi_doc)
            written[fmt] = target
        elif fmt == "dto-json":
            target = out_dir / "dto.json"
            _write_json(target, dto)
            written[fmt] = target

    if split:
        split_dir = out_dir / "components"
        split_dir.mkdir(parents=True, exist_ok=True)
        _write_json(split_dir / "enums.json", dto.get("enums", {}))
        _write_json(split_dir / "types.json", dto.get("types", {}))
        _write_json(split_dir / "aliases.json", dto.get("aliases", {}))
        _write_json(split_dir / "single_aliases.json", dto.get("single_aliases", {}))
        _write_json(split_dir / "value_sets.json", dto.get("value_sets", {}))
        _write_json(split_dir / "specials.json", dto.get("specials", {}))
        if dto.get("modifier_categories"):
            _write_json(split_dir / "modifier_categories.json", dto.get("modifier_categories", {}))

    return written


__all__ = ["dict_to_openapi", "emit_spec", "spec_to_dict"]
