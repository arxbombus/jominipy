from pathlib import Path

from jominipy.parser import ParseMode, parse_result
from jominipy.pipeline import run_check, run_format, run_lint, run_typecheck
from jominipy.rules import RuleFieldConstraint, RuleValueSpec
from jominipy.typecheck.rules import FieldReferenceConstraintRule


def test_run_lint_reuses_provided_parse_result() -> None:
    source = "a=1\n"
    parsed = parse_result(source)

    result = run_lint("ignored", parse=parsed)

    assert result.parse is parsed
    assert result.diagnostics == parsed.diagnostics
    assert result.type_facts is not None


def test_run_lint_rejects_parse_with_mode_or_options() -> None:
    parsed = parse_result("a=1\n")

    try:
        run_lint("a=1\n", parse=parsed, mode=ParseMode.PERMISSIVE)
    except ValueError as exc:
        assert "Pass either parse or options/mode, not both" in str(exc)
    else:
        raise AssertionError("Expected ValueError when passing parse and mode together")


def test_run_format_scaffold_returns_original_source() -> None:
    source = "a=1\n"

    result = run_format(source)

    assert result.formatted_text == source
    assert result.changed is False
    assert result.diagnostics == []


def test_run_check_reports_parse_errors_through_lint_pipeline() -> None:
    source = 'a="x";\n'

    result = run_check(source)

    assert result.parse.source_text == source
    assert result.has_errors is True
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "PARSER_UNEXPECTED_TOKEN"


def test_run_typecheck_reuses_provided_parse_result() -> None:
    source = "a=1\n"
    parsed = parse_result(source)

    result = run_typecheck("ignored", parse=parsed)

    assert result.parse is parsed
    assert result.diagnostics == parsed.diagnostics


def test_run_typecheck_project_root_auto_builds_type_memberships(tmp_path: Path) -> None:
    interface_dir = tmp_path / "game" / "interface"
    interface_dir.mkdir(parents=True, exist_ok=True)
    (interface_dir / "example.gfx").write_text(
        "spriteTypes={\n"
        '  spriteType={ name="GFX_focus_test" textureFile="gfx/interface/x.dds" }\n'
        "}\n",
        encoding="utf-8",
    )
    source = "technology={ icon = GFX_missing }\n"
    rule = FieldReferenceConstraintRule(
        field_constraints_by_object={
            "technology": {
                "icon": RuleFieldConstraint(
                    required=False,
                    value_specs=(RuleValueSpec(kind="type_ref", raw="<spriteType>", argument="spriteType"),),
                ),
            }
        },
        known_type_keys=frozenset({"spriteType"}),
    )
    result = run_typecheck(source, rules=(rule,), project_root=str(tmp_path))

    assert [diagnostic.code for diagnostic in result.diagnostics] == ["TYPECHECK_INVALID_FIELD_REFERENCE"]


def test_run_check_accepts_typecheck_services_parameters(tmp_path: Path) -> None:
    interface_dir = tmp_path / "game" / "interface"
    interface_dir.mkdir(parents=True, exist_ok=True)
    (interface_dir / "example.gfx").write_text(
        "spriteTypes={\n"
        '  spriteType={ name="GFX_focus_test" textureFile="gfx/interface/x.dds" }\n'
        "}\n",
        encoding="utf-8",
    )
    source = "technology={ icon = GFX_missing }\n"

    result = run_check(source, project_root=str(tmp_path))

    assert result.parse.source_text == source
