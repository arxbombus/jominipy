from jominipy.pipeline import run_typecheck
from jominipy.rules import (
    RuleFieldConstraint,
    RuleValueSpec,
    TypeDefinition,
    build_type_memberships_from_file_texts,
    extract_type_definitions,
    load_hoi4_schema_graph,
)
from jominipy.typecheck import build_typecheck_services_from_file_texts
from jominipy.typecheck.rules import FieldReferenceConstraintRule


def test_build_type_memberships_from_file_texts_is_generic_by_type_key() -> None:
    type_definitions = {
        "spriteType": (
            TypeDefinition(
                type_key="spriteType",
                path="game/interface",
                name_field="name",
                skip_root_key="spriteTypes",
                path_extension=".gfx",
            ),
        ),
        "technology": (
            TypeDefinition(
                type_key="technology",
                path="game/common/technologies",
                skip_root_key="technologies",
            ),
        ),
    }
    files = {
        "game/interface/example.gfx": (
            "spriteTypes={\n"
            '  spriteType={ name="GFX_focus_test" textureFile="gfx/interface/x.dds" }\n'
            '  frameAnimatedSpriteType={ name=GFX_focus_alt textureFile="gfx/interface/y.dds" }\n'
            "}\n"
        ),
        "game/common/technologies/example.txt": (
            "technologies={\n"
            "  basic_machine_tools={ cost=1 }\n"
            "}\n"
        ),
    }

    memberships = build_type_memberships_from_file_texts(
        file_texts_by_path=files,
        type_definitions_by_key=type_definitions,
    )

    assert memberships["spriteType"] == frozenset({"GFX_focus_test", "GFX_focus_alt"})
    assert memberships["technology"] == frozenset({"basic_machine_tools"})


def test_extract_type_definitions_includes_sprite_type_without_special_case() -> None:
    schema = load_hoi4_schema_graph()
    definitions = extract_type_definitions(schema)

    assert "spriteType" in definitions
    assert any(definition.name_field == "name" for definition in definitions["spriteType"])
    assert any(definition.skip_root_key == "spriteTypes" for definition in definitions["spriteType"])


def test_typecheck_services_from_file_texts_power_generic_type_ref_validation() -> None:
    files = {
        "game/interface/example.gfx": (
            "spriteTypes={\n"
            '  spriteType={ name="GFX_focus_test" textureFile="gfx/interface/x.dds" }\n'
            "}\n"
        )
    }
    services = build_typecheck_services_from_file_texts(file_texts_by_path=files)
    rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "icon": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="type_ref", raw="<spriteType>", argument="spriteType"),),
                )
            }
        },
        known_type_keys=frozenset({"spriteType"}),
        type_memberships_by_key=services.type_memberships_by_key,
        policy=services.policy,
    )

    invalid = run_typecheck("technology={ icon = GFX_missing }\n", rules=(rule,))
    valid = run_typecheck("technology={ icon = GFX_focus_test }\n", rules=(rule,))

    assert [diagnostic.code for diagnostic in invalid.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]
    assert valid.diagnostics == []
