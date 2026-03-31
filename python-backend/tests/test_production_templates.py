"""Integration tests for production radiology report templates.

Validates that all production templates load correctly through the
template loader and schema validation pipeline, with correct field
counts, ordering, sex tags, optional flags, groups, and guidance content.
"""

import pathlib

import pytest

from lib.templates.loader import load_template, discover_templates
from lib.templates.registry import TemplateRegistry

# Production templates root directory
TEMPLATES_ROOT = pathlib.Path(__file__).parent.parent / "rpt_templates"


# ===== Helper =====


def _load(relative_path: str):
    """Load a production template by relative path from templates root."""
    return load_template(TEMPLATES_ROOT / relative_path)


# ===== CT AP Freeform Tests =====


def test_ct_ap_loads():
    """CT AP freeform template loads and validates without error."""
    t = _load("ct/ct_ap.rpt.md")
    assert t.schema.study_name == "CT Abdomen and Pelvis"
    assert len(t.schema.fields) == 18
    assert "ct ap" in t.schema.aliases


def test_ct_ap_field_order():
    """CT AP fields are in craniocaudal anatomical order."""
    t = _load("ct/ct_ap.rpt.md")
    field_names = [f.name for f in t.schema.fields]
    assert field_names == [
        "liver",
        "gallbladder",
        "cbd",
        "spleen",
        "adrenals",
        "pancreas",
        "kidneys",
        "bowel",
        "mesentery",
        "lymph_nodes",
        "bladder",
        "uterus_ovaries",
        "prostate",
        "vessels",
        "lung_bases",
        "free_fluid",
        "bones",
        "soft_tissues",
    ]


def test_ct_ap_sex_fields():
    """CT AP has sex-dependent pelvis fields (FLDS-01)."""
    t = _load("ct/ct_ap.rpt.md")
    fields_by_name = {f.name: f for f in t.schema.fields}

    assert fields_by_name["uterus_ovaries"].sex == "female"
    assert fields_by_name["prostate"].sex == "male"

    # No other fields should have a sex tag
    sex_fields = [f.name for f in t.schema.fields if f.sex is not None]
    assert set(sex_fields) == {"uterus_ovaries", "prostate"}


def test_ct_ap_optional_fields():
    """CT AP vessels field is optional; all others are not."""
    t = _load("ct/ct_ap.rpt.md")
    fields_by_name = {f.name: f for f in t.schema.fields}

    assert fields_by_name["vessels"].optional is True

    optional_fields = [f.name for f in t.schema.fields if f.optional is True]
    assert optional_fields == ["vessels"]


def test_ct_ap_groups():
    """CT AP has 2 field groups with correct members and partials."""
    t = _load("ct/ct_ap.rpt.md")
    assert len(t.schema.groups) == 2

    groups_by_name = {g.name: g for g in t.schema.groups}

    gb_cbd = groups_by_name["gallbladder_cbd"]
    assert gb_cbd.members == ["gallbladder", "cbd"]

    sap = groups_by_name["spleen_adrenals_pancreas"]
    assert sap.members == ["spleen", "adrenals", "pancreas"]
    assert len(sap.partials) == 3


def test_ct_ap_guidance():
    """CT AP body contains a Guidance section with clinical thresholds."""
    t = _load("ct/ct_ap.rpt.md")
    assert "## Guidance" in t.body
    assert "Bosniak" in t.body
    assert "aorta" in t.body


# ===== CT AP Structured Tests =====


@pytest.mark.skipif(
    not (TEMPLATES_ROOT / "ct/ct_ap_structured.rpt.md").exists(),
    reason="CT AP structured template not yet authored",
)
def test_ct_ap_structured_loads():
    """CT AP structured template loads with correct study name and aliases."""
    t = _load("ct/ct_ap_structured.rpt.md")
    assert t.schema.study_name == "CT Abdomen and Pelvis (Structured)"
    assert "ct ap structured" in t.schema.aliases
    assert "ct ap" not in t.schema.aliases


# ===== CT Thorax Tests =====


@pytest.mark.skipif(
    not (TEMPLATES_ROOT / "ct/ct_thorax.rpt.md").exists(),
    reason="CT thorax template not yet authored",
)
def test_ct_thorax_loads():
    """CT thorax template loads with correct field count and names."""
    t = _load("ct/ct_thorax.rpt.md")
    assert t.schema.study_name == "CT Thorax"
    assert len(t.schema.fields) == 8
    field_names = [f.name for f in t.schema.fields]
    assert field_names == [
        "lungs",
        "pleura",
        "airways",
        "thyroid",
        "mediastinum",
        "heart_great_vessels",
        "limited_abdomen",
        "bones",
    ]


@pytest.mark.skipif(
    not (TEMPLATES_ROOT / "ct/ct_thorax.rpt.md").exists(),
    reason="CT thorax template not yet authored",
)
def test_ct_thorax_optional_fields():
    """CT thorax airways and thyroid fields are optional."""
    t = _load("ct/ct_thorax.rpt.md")
    fields_by_name = {f.name: f for f in t.schema.fields}

    assert fields_by_name["airways"].optional is True
    assert fields_by_name["thyroid"].optional is True

    optional_fields = {f.name for f in t.schema.fields if f.optional is True}
    assert optional_fields == {"airways", "thyroid"}


# ===== CT TAP Composite Tests =====


def test_ct_tap_loads():
    """CT TAP composite template loads via registry with correct study name."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    assert t.schema.study_name == "CT Thorax, Abdomen and Pelvis"
    assert "ct tap" in t.schema.aliases


def test_ct_tap_field_count():
    """CT TAP has 23 merged fields: 6 thorax + 16 AP + 1 composite bones."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    assert len(t.schema.fields) == 23


def test_ct_tap_field_order():
    """CT TAP fields are thorax first, then AP, then composite bones."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    field_names = [f.name for f in t.schema.fields]
    # Thorax fields (minus bones, limited_abdomen)
    assert field_names[:6] == [
        "lungs", "pleura", "airways", "thyroid",
        "mediastinum", "heart_great_vessels",
    ]
    # AP fields (minus bones, lung_bases) -- 16 fields
    assert field_names[6:22] == [
        "liver", "gallbladder", "cbd", "spleen",
        "adrenals", "pancreas", "kidneys", "bowel",
        "mesentery", "lymph_nodes", "bladder",
        "uterus_ovaries", "prostate", "vessels",
        "free_fluid", "soft_tissues",
    ]
    # Composite bones
    assert field_names[22] == "bones"


def test_ct_tap_no_excluded_fields():
    """CT TAP does not contain lung_bases, limited_abdomen, or duplicate bones."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    field_names = [f.name for f in t.schema.fields]
    assert "lung_bases" not in field_names
    assert "limited_abdomen" not in field_names
    assert field_names.count("bones") == 1


def test_ct_tap_groups_carried_forward():
    """CT TAP carries forward gallbladder_cbd and spleen_adrenals_pancreas groups from CT AP."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    group_names = {g.name for g in t.schema.groups}
    assert "gallbladder_cbd" in group_names
    assert "spleen_adrenals_pancreas" in group_names


def test_ct_tap_sex_fields():
    """CT TAP preserves sex-dependent pelvis fields from CT AP."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    fields_by_name = {f.name: f for f in t.schema.fields}
    assert fields_by_name["uterus_ovaries"].sex == "female"
    assert fields_by_name["prostate"].sex == "male"


def test_ct_tap_renders():
    """CT TAP renders a complete report via render_report()."""
    from lib.templates.renderer import render_report
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    findings = {"lungs": "Right lower lobe consolidation.", "liver": "Hepatomegaly."}
    technique = {}
    report = render_report(t, findings, technique)
    assert "### Thorax" in report or "Thorax" in report
    assert "### Abdomen and Pelvis" in report or "Abdomen and Pelvis" in report
    assert "Right lower lobe consolidation" in report
    assert "Hepatomegaly" in report


def test_ct_tap_composite_bones():
    """CT TAP bones field has composite normal text covering full skeleton survey."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    t = registry.get_template("ct tap")
    bones = next(f for f in t.schema.fields if f.name == "bones")
    assert "No suspicious osseous lesion" in bones.normal
    assert "No acute fracture" in bones.normal


# ===== US HBS Tests =====


@pytest.mark.skipif(
    not (TEMPLATES_ROOT / "us/us_hbs.rpt.md").exists(),
    reason="US HBS template not yet authored",
)
def test_us_hbs_loads():
    """US HBS template loads with correct study name and field count."""
    t = _load("us/us_hbs.rpt.md")
    assert t.schema.study_name == "US Hepatobiliary"
    assert len(t.schema.fields) == 5
    assert "us hbs" in t.schema.aliases


@pytest.mark.skipif(
    not (TEMPLATES_ROOT / "us/us_hbs.rpt.md").exists(),
    reason="US HBS template not yet authored",
)
def test_us_hbs_measurements():
    """US HBS body contains measurement placeholders (FLDS-02)."""
    t = _load("us/us_hbs.rpt.md")
    assert "{{measurement:liver_span_cm}}" in t.body
    assert "{{measurement:cbd_diameter_mm}}" in t.body
    assert "{{measurement:spleen_length_cm}}" in t.body


@pytest.mark.skipif(
    not (TEMPLATES_ROOT / "us/us_hbs.rpt.md").exists(),
    reason="US HBS template not yet authored",
)
def test_us_hbs_optional_fields():
    """US HBS others field is optional; all others are not."""
    t = _load("us/us_hbs.rpt.md")
    fields_by_name = {f.name: f for f in t.schema.fields}

    assert fields_by_name["others"].optional is True

    optional_fields = [f.name for f in t.schema.fields if f.optional is True]
    assert optional_fields == ["others"]


# ===== Cross-Template Validation =====


def test_all_production_templates_load():
    """All production templates discover and load without errors."""
    paths = discover_templates(TEMPLATES_ROOT)
    assert len(paths) == 5  # 3 base + 1 structured + 1 composite (ct_tap)

    for path in paths:
        t = load_template(path)
        assert t.schema.study_name  # non-empty study name
