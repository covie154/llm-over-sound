"""Tests for defaults.py: build_guidance and build_default_payload.

Covers:
- Guidance extraction for atomic and composite (including nested) templates.
- Default payload shape for atomic and composite templates.
- Placeholder collection rules (measurement/technique only, dedup, groups).
- Cycle detection on malformed composable_from chains.
"""

import pathlib

import pytest

from lib.templates.defaults import build_default_payload, build_guidance
from lib.templates.exceptions import TemplateValidationError
from lib.templates.loader import load_template


FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
DEFAULTS_DIR = FIXTURES_DIR / "defaults"


@pytest.fixture
def templates_dir() -> pathlib.Path:
    """Root the helpers use to resolve composable_from relative paths."""
    return FIXTURES_DIR


def _load(relpath: str):
    return load_template(FIXTURES_DIR / relpath)


# =====================================================================
# build_guidance
# =====================================================================


def test_guidance_atomic_no_section_returns_empty(templates_dir):
    template = _load("defaults/atomic_plain.rpt.md")
    assert build_guidance(template, templates_dir) == ""


def test_guidance_atomic_strips_heading(templates_dir):
    template = _load("defaults/us_hbs_reference.rpt.md")
    result = build_guidance(template, templates_dir)
    assert result == "When reporting gallbladder findings, note wall thickness above 3 mm."


def test_guidance_composite_concatenates_in_order(templates_dir):
    template = _load("defaults/composite_xy.rpt.md")
    result = build_guidance(template, templates_dir)
    assert result == (
        "X guidance: measure organ X across its long axis.\n\n"
        "Composite XY guidance: reconcile findings across both organs."
    )


def test_guidance_composite_skips_empty_bases_silently(templates_dir):
    template = _load("defaults/composite_xy.rpt.md")
    result = build_guidance(template, templates_dir)
    assert "\n\n\n\n" not in result
    assert "X guidance" in result
    assert "Composite XY guidance" in result


def test_guidance_nested_composite_preserves_order(templates_dir):
    template = _load("defaults/composite_nested.rpt.md")
    result = build_guidance(template, templates_dir)
    assert result == (
        "X guidance: measure organ X across its long axis.\n\n"
        "Composite XY guidance: reconcile findings across both organs.\n\n"
        "Z guidance: organ Z should be assessed in two planes."
    )


def test_guidance_composite_all_empty_returns_empty(templates_dir):
    template = _load("defaults/composite_all_empty.rpt.md")
    assert build_guidance(template, templates_dir) == ""


def test_guidance_detects_cycle(templates_dir):
    template = _load("defaults/cycle_a.rpt.md")
    with pytest.raises(TemplateValidationError) as excinfo:
        build_guidance(template, templates_dir)
    assert "Circular" in str(excinfo.value)


# =====================================================================
# build_default_payload
# =====================================================================


def test_payload_shape_has_technique_and_findings(templates_dir):
    template = _load("defaults/atomic_plain.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert set(result.keys()) == {"technique", "findings"}
    assert isinstance(result["technique"], dict)
    assert isinstance(result["findings"], dict)


def test_payload_atomic_no_placeholders(templates_dir):
    template = _load("defaults/atomic_plain.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["technique"] == {}
    assert result["findings"] == {
        "liver": "The liver is normal.",
        "spleen": "The spleen is normal.",
    }


def test_payload_preserves_field_order(templates_dir):
    template = _load("defaults/us_hbs_reference.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert list(result["findings"].keys()) == [
        "liver",
        "gallbladder_cbd",
        "spleen",
        "pancreas",
    ]


def test_payload_findings_preserve_placeholders_verbatim(templates_dir):
    template = _load("defaults/us_hbs_reference.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert "{{measurement:cbd_diameter_cm}}" in result["findings"]["gallbladder_cbd"]
    assert "{{measurement:spleen_length_cm}}" in result["findings"]["spleen"]


def test_payload_measurement_placeholders_collected(templates_dir):
    template = _load("defaults/us_hbs_reference.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["technique"] == {
        "cbd_diameter_cm": "{{measurement:cbd_diameter_cm}}",
        "spleen_length_cm": "{{measurement:spleen_length_cm}}",
    }


def test_payload_technique_placeholders_collected(templates_dir):
    template = _load("defaults/technique_placeholder.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["technique"] == {"phase": "{{technique:phase}}"}


def test_payload_plain_field_refs_not_in_technique(templates_dir):
    template = _load("defaults/atomic_plain.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["technique"] == {}


def test_payload_dedup_measurement(templates_dir):
    template = _load("defaults/dup_measurement.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["technique"] == {"size_cm": "{{measurement:size_cm}}"}


def test_payload_group_joint_and_partials_contribute(templates_dir):
    template = _load("defaults/group_measurements.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["technique"] == {
        "spleen_length_cm": "{{measurement:spleen_length_cm}}",
        "adrenal_size_cm": "{{measurement:adrenal_size_cm}}",
    }


def test_payload_composite_field_order(templates_dir):
    template = _load("composite/composite_ab.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert list(result["findings"].keys()) == [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
    ]


def test_payload_composite_merges_base_fields(templates_dir):
    template = _load("composite/composite_ab.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert result["findings"]["alpha"] == "Alpha is normal."
    assert result["findings"]["zeta"] == "Zeta is normal."


def test_payload_composite_nested_fields(templates_dir):
    template = _load("defaults/composite_nested.rpt.md")
    result = build_default_payload(template, templates_dir)
    assert list(result["findings"].keys()) == ["organ_x", "organ_y", "organ_z"]
