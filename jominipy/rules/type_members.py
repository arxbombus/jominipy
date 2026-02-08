"""Generic type-member discovery from CWTools type declarations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from jominipy.ast import AstBlock, AstKeyValue, AstScalar
from jominipy.parser import parse_result
from jominipy.rules.schema_graph import RuleSchemaGraph


@dataclass(frozen=True, slots=True)
class TypeDefinition:
    """Normalized subset of a CWTools `type[...]` declaration."""

    type_key: str
    path: str | None = None
    name_field: str | None = None
    skip_root_key: str | None = None
    path_extension: str | None = None
    path_file: str | None = None


def extract_type_definitions(schema: RuleSchemaGraph) -> dict[str, tuple[TypeDefinition, ...]]:
    """Extract normalized type definitions from schema graph declarations."""
    by_key: dict[str, list[TypeDefinition]] = {}
    for type_key, declarations in schema.types_by_key.items():
        bucket = by_key.setdefault(type_key, [])
        for declaration in declarations:
            statement = declaration.statement
            if statement.value.kind != "block":
                continue
            options = _extract_type_options(statement.value.block)
            bucket.append(
                TypeDefinition(
                    type_key=type_key,
                    path=options.get("path"),
                    name_field=options.get("name_field"),
                    skip_root_key=options.get("skip_root_key"),
                    path_extension=options.get("path_extension"),
                    path_file=options.get("path_file"),
                )
            )
    return {key: tuple(items) for key, items in by_key.items()}


def build_type_memberships_from_file_texts(
    *,
    file_texts_by_path: Mapping[str, str],
    type_definitions_by_key: Mapping[str, tuple[TypeDefinition, ...]],
) -> dict[str, frozenset[str]]:
    """Discover member names for each type key from provided script files."""
    members: dict[str, set[str]] = {}
    normalized_files = { _normalize_path(path): text for path, text in file_texts_by_path.items() }

    for type_key, definitions in type_definitions_by_key.items():
        bucket = members.setdefault(type_key, set())
        for definition in definitions:
            for file_path, text in normalized_files.items():
                if not _matches_type_path(file_path, definition):
                    continue
                bucket.update(_discover_members_in_file(text=text, definition=definition))

    return {key: frozenset(values) for key, values in members.items() if values}


def collect_file_texts_under_root(project_root: str) -> dict[str, str]:
    """Collect file texts under a project root for membership discovery."""
    root = Path(project_root)
    file_texts: dict[str, str] = {}
    if not root.exists():
        return file_texts
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Jomini/script content is usually text-based and extension-flexible.
        if path.suffix.lower() in {".dds", ".png", ".tga", ".jpg", ".jpeg", ".webp"}:
            continue
        try:
            file_texts[_normalize_path(str(path.relative_to(root)))] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return file_texts


def _extract_type_options(statements: tuple[object, ...]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in statements:
        if not hasattr(item, "kind") or getattr(item, "kind") != "key_value":
            continue
        key = getattr(item, "key", None)
        value = getattr(item, "value", None)
        if not isinstance(key, str):
            continue
        if not (hasattr(value, "kind") and getattr(value, "kind") == "scalar"):
            continue
        raw = (getattr(value, "text", "") or "").strip()
        if not raw:
            continue
        options[key] = _strip_quotes(raw)
    return options


def _matches_type_path(file_path: str, definition: TypeDefinition) -> bool:
    normalized = _normalize_path(file_path)
    if definition.path_file:
        if Path(normalized).name != Path(definition.path_file).name:
            return False
    if definition.path_extension:
        if not normalized.endswith(definition.path_extension):
            return False
    if definition.path:
        declared = _normalize_path(definition.path)
        candidates = {declared}
        if declared.startswith("game/"):
            candidates.add(declared[len("game/"):])
        if not any(_is_within_path(normalized, candidate) for candidate in candidates):
            return False
    return True


def _discover_members_in_file(*, text: str, definition: TypeDefinition) -> set[str]:
    parsed = parse_result(text)
    source = parsed.ast_root()
    top_level = [statement for statement in source.statements if isinstance(statement, AstKeyValue)]
    entities = _select_entities(top_level=top_level, skip_root_key=definition.skip_root_key)

    members: set[str] = set()
    for entity in entities:
        name = _extract_entity_name(entity=entity, name_field=definition.name_field)
        if name:
            members.add(name)
    return members


def _select_entities(*, top_level: list[AstKeyValue], skip_root_key: str | None) -> list[AstKeyValue]:
    if skip_root_key is None:
        return top_level

    lowered = skip_root_key.strip().lower()
    selected: list[AstKeyValue] = []
    if lowered == "any":
        for statement in top_level:
            selected.extend(_nested_entities(statement))
        return selected

    for statement in top_level:
        if statement.key.raw_text != skip_root_key:
            continue
        selected.extend(_nested_entities(statement))
    return selected


def _nested_entities(statement: AstKeyValue) -> list[AstKeyValue]:
    if not isinstance(statement.value, AstBlock):
        return []
    if not statement.value.is_object_like:
        return []
    return [item for item in statement.value.statements if isinstance(item, AstKeyValue)]


def _extract_entity_name(*, entity: AstKeyValue, name_field: str | None) -> str | None:
    if name_field is None:
        return entity.key.raw_text or None
    if not isinstance(entity.value, AstBlock):
        return None
    if not entity.value.is_object_like:
        return None
    for child in entity.value.statements:
        if not isinstance(child, AstKeyValue):
            continue
        if child.key.raw_text != name_field:
            continue
        if not isinstance(child.value, AstScalar):
            return None
        text = _strip_quotes(child.value.raw_text.strip())
        return text or None
    return None


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _is_within_path(file_path: str, declared_path: str) -> bool:
    candidate = declared_path.rstrip("/")
    if not candidate:
        return True
    return file_path.startswith(candidate + "/") or file_path == candidate
