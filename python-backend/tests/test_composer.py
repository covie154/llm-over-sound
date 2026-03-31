"""Tests for template composition engine (composer.py).

Covers: COMP-01 (resolution), COMP-02 (field ordering), COMP-03 (flag override),
COMP-04 (exclude_fields), D-11 (group drop), D-26 (circular), D-27 (missing base),
D-28 (invalid exclusion), body placeholder validation.
"""

import pathlib

import pytest

from lib.templates.composer import compose_template
from lib.templates.loader import LoadedTemplate, load_template
from lib.templates.schema import (
    TemplateSchema,
    FieldDefinition,
    FieldGroup,
    validate_body_placeholders,
)
from lib.templates.exceptions import TemplateValidationError


# ===== Helpers =====


def _make_loaded_template(
    study_name: str = "Test",
    aliases: list[str] | None = None,
    technique: str = "Test technique.",
    fields: list[dict] | None = None,
    groups: list[dict] | None = None,
    composable_from: list[str] | None = None,
    exclude_fields: dict[str, list[str]] | None = None,
    body: str = "",
    file_path: str = "test.rpt.md",
    impression: bool = True,
    interpolate_normal: bool = False,
    important_first: bool = False,
) -> LoadedTemplate:
    """Build a LoadedTemplate for testing without file I/O."""
    if aliases is None:
        aliases = [study_name.lower()]
    if fields is None:
        fields = [{"name": "placeholder", "normal": "Normal."}]

    schema = TemplateSchema(
        study_name=study_name,
        aliases=aliases,
        technique=technique,
        fields=[FieldDefinition(**f) for f in fields],
        groups=[FieldGroup(**g) for g in (groups or [])],
        composable_from=composable_from,
        exclude_fields=exclude_fields,
        impression=impression,
        interpolate_normal=interpolate_normal,
        important_first=important_first,
    )
    return LoadedTemplate(schema=schema, body=body, file_path=file_path)


# ===== COMP-01: composable_from resolves bases =====


def test_composable_from_resolves_bases(raw_composite, composite_bases):
    """COMP-01: compose_template resolves bases into a single LoadedTemplate."""
    result = compose_template(raw_composite, composite_bases)
    assert isinstance(result, LoadedTemplate)
    assert result.schema.study_name == "Composite AB"


# ===== COMP-02: field merge order =====


def test_field_merge_order(raw_composite, composite_bases):
    """COMP-02: fields are base_a fields, base_b fields minus exclusions, composite fields."""
    result = compose_template(raw_composite, composite_bases)
    field_names = [f.name for f in result.schema.fields]
    assert field_names == ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"]


# ===== COMP-03: composite flags override bases =====


def test_composite_flags_override_bases(composite_bases):
    """COMP-03: composed template flags match composite, not bases."""
    composite = _make_loaded_template(
        study_name="Flag Test",
        composable_from=["composite/base_a.rpt.md", "composite/base_b.rpt.md"],
        exclude_fields={"composite/base_b.rpt.md": ["gamma"]},
        fields=[],
        impression=False,
        interpolate_normal=True,
        important_first=True,
        technique="Custom technique.",
        body="## FINDINGS\n\n{{alpha}}\n\n{{beta}}\n\n{{gamma}}\n\n{{delta}}\n\n{{epsilon}}\n\n## COMMENT",
        file_path="flag_test.rpt.md",
    )
    result = compose_template(composite, composite_bases)
    assert result.schema.impression is False
    assert result.schema.interpolate_normal is True
    assert result.schema.important_first is True
    assert result.schema.technique == "Custom technique."


# ===== COMP-04: exclude_fields =====


def test_exclude_fields_dedup(raw_composite, composite_bases):
    """COMP-04: gamma excluded from base_b, only one gamma in result (from base_a)."""
    result = compose_template(raw_composite, composite_bases)
    gamma_fields = [f for f in result.schema.fields if f.name == "gamma"]
    assert len(gamma_fields) == 1
    # It should be from base_a
    assert gamma_fields[0].normal == "Gamma is normal."


def test_collision_after_exclusion_raises(composite_bases):
    """COMP-04: both bases have gamma, not excluded from either -> collision error."""
    composite = _make_loaded_template(
        study_name="Collision Test",
        composable_from=["composite/base_a.rpt.md", "composite/base_b.rpt.md"],
        exclude_fields=None,  # No exclusions -> gamma collides
        fields=[],
        body="## FINDINGS\n\n{{alpha}}\n\n{{beta}}\n\n{{gamma}}\n\n{{delta}}\n\n{{epsilon}}\n\n## COMMENT",
        file_path="collision_test.rpt.md",
    )
    with pytest.raises(TemplateValidationError, match="Field name collision"):
        compose_template(composite, composite_bases)


# ===== D-28: excluding nonexistent field =====


def test_exclude_nonexistent_field_raises(composite_bases):
    """D-28: excluding a field that doesn't exist in the base raises error."""
    composite = _make_loaded_template(
        study_name="Bad Exclude",
        composable_from=["composite/base_a.rpt.md"],
        exclude_fields={"composite/base_a.rpt.md": ["nonexistent"]},
        fields=[],
        body="## FINDINGS\n\n{{alpha}}\n\n{{beta}}\n\n{{gamma}}\n\n## COMMENT",
        file_path="bad_exclude.rpt.md",
    )
    with pytest.raises(TemplateValidationError, match="does not exist in base template"):
        compose_template(composite, composite_bases)


# ===== D-27: missing base template =====


def test_missing_base_raises(composite_bases):
    """D-27: referencing a base that isn't in the bases dict raises error."""
    composite = _make_loaded_template(
        study_name="Missing Base",
        composable_from=["composite/missing.rpt.md"],
        fields=[],
        body="## FINDINGS\n\n## COMMENT",
        file_path="missing_base.rpt.md",
    )
    with pytest.raises(TemplateValidationError, match="Base template not found"):
        compose_template(composite, composite_bases)


# ===== D-26: circular composition =====


def test_circular_composition_raises(composite_fixtures_dir):
    """D-26: circular composable_from references raise error."""
    circular_a = load_template(composite_fixtures_dir / "circular_a.rpt.md")
    circular_b = load_template(composite_fixtures_dir / "circular_b.rpt.md")
    bases = {
        "composite/circular_a.rpt.md": circular_a,
        "composite/circular_b.rpt.md": circular_b,
    }
    with pytest.raises(TemplateValidationError, match="Circular"):
        compose_template(circular_a, bases)


# ===== Group carry-forward =====


def test_group_carried_forward(raw_composite, composite_bases):
    """Groups from bases carry forward into composed template."""
    result = compose_template(raw_composite, composite_bases)
    group_names = [g.name for g in result.schema.groups]
    assert "alpha_beta" in group_names


# ===== D-11: group dropped when member excluded =====


def test_group_dropped_when_member_excluded(composite_bases):
    """D-11: if a group member is excluded, the whole group is dropped."""
    # Exclude alpha from base_a -- alpha_beta group should be dropped
    composite = _make_loaded_template(
        study_name="Group Drop Test",
        composable_from=["composite/base_a.rpt.md", "composite/base_b.rpt.md"],
        exclude_fields={
            "composite/base_a.rpt.md": ["alpha"],
            "composite/base_b.rpt.md": ["gamma"],
        },
        fields=[],
        body="## FINDINGS\n\n{{beta}}\n\n{{gamma}}\n\n{{delta}}\n\n{{epsilon}}\n\n## COMMENT",
        file_path="group_drop.rpt.md",
    )
    result = compose_template(composite, composite_bases)
    group_names = [g.name for g in result.schema.groups]
    assert "alpha_beta" not in group_names


# ===== Body handling =====


def test_body_passed_through(raw_composite, composite_bases):
    """Composed template body is the composite's own body (not base bodies)."""
    result = compose_template(raw_composite, composite_bases)
    assert result.body == raw_composite.body
    assert "### Part A" in result.body
    assert "### Part B" in result.body


def test_body_placeholder_validation(raw_composite, composite_bases):
    """Body placeholders validated against merged fields -- no issues."""
    result = compose_template(raw_composite, composite_bases)
    issues = validate_body_placeholders(result.schema, result.body)
    assert issues == []


# ===== Composed schema state =====


def test_composed_schema_has_no_composable_from(raw_composite, composite_bases):
    """The composed LoadedTemplate schema has composable_from=None (resolved)."""
    result = compose_template(raw_composite, composite_bases)
    assert result.schema.composable_from is None
    assert result.schema.exclude_fields is None
