"""Integration tests for production radiology report templates.

Validates that all production templates load correctly through the
template loader and schema validation pipeline, with correct field
counts, ordering, sex tags, optional flags, groups, and guidance content.
"""

import pathlib

import pytest

from lib.templates.loader import load_template, discover_templates

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
    assert len(paths) == 4

    for path in paths:
        t = load_template(path)
        assert t.schema.study_name  # non-empty study name
