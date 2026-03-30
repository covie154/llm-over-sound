"""Comprehensive unit tests for report renderer behaviors."""

from __future__ import annotations

import logging

import pytest

from lib.templates import render_report, NOT_DOCUMENTED
from lib.templates.loader import LoadedTemplate
from lib.templates.schema import TemplateSchema


# ===== Helpers =====


STANDARD_TECHNIQUE = {
    "phase": "Test technique.",
    "clinical_indication": "Test indication.",
}


def _with_schema_overrides(template: LoadedTemplate, **overrides) -> LoadedTemplate:
    """Create a new LoadedTemplate with schema field overrides."""
    schema_data = template.schema.model_dump()
    schema_data.update(overrides)
    new_schema = TemplateSchema(**schema_data)
    return LoadedTemplate(schema=new_schema, body=template.body, file_path=template.file_path)


# ===== Freeform Basic Tests =====


def test_freeform_all_findings(freeform_template):
    """All fields populated -> output contains each finding text, no __NOT_DOCUMENTED__."""
    findings = {
        "liver": "Hepatomegaly with fatty infiltration.",
        "spleen": "Mild splenomegaly.",
        "kidneys": "Bilateral renal cysts.",
    }
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "Hepatomegaly with fatty infiltration." in result
    assert "Mild splenomegaly." in result
    assert "Bilateral renal cysts." in result
    assert NOT_DOCUMENTED not in result


def test_freeform_interpolate_false_unreported(freeform_template):
    """interpolate_normal=false, field unreported -> output contains __NOT_DOCUMENTED__."""
    findings = {"liver": "Hepatomegaly."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "Hepatomegaly." in result
    assert NOT_DOCUMENTED in result


def test_freeform_interpolate_true_unreported(freeform_template):
    """interpolate_normal=true, field unreported -> output contains field's normal text."""
    template = _with_schema_overrides(freeform_template, interpolate_normal=True)
    findings = {"liver": "Hepatomegaly."}
    result = render_report(template, findings, STANDARD_TECHNIQUE)
    assert "Hepatomegaly." in result
    assert "The spleen is normal." in result
    assert "The kidneys are normal." in result
    assert NOT_DOCUMENTED not in result


# ===== Rest-Normal Tests =====


def test_rest_normal_overrides_interpolation(freeform_template):
    """rest_normal=True, interpolate_normal=false, unreported field -> normal text."""
    findings = {"liver": "Hepatomegaly."}
    result = render_report(
        freeform_template, findings, STANDARD_TECHNIQUE, rest_normal=True
    )
    assert "Hepatomegaly." in result
    assert "The spleen is normal." in result
    assert "The kidneys are normal." in result
    assert NOT_DOCUMENTED not in result


def test_rest_normal_preserves_explicit_findings(freeform_template):
    """rest_normal=True, field has explicit value -> explicit value preserved."""
    findings = {
        "liver": "Hepatomegaly.",
        "spleen": "Splenomegaly measuring 15 cm.",
    }
    result = render_report(
        freeform_template, findings, STANDARD_TECHNIQUE, rest_normal=True
    )
    assert "Hepatomegaly." in result
    assert "Splenomegaly measuring 15 cm." in result
    # kidneys unreported -> should get normal text, not the finding
    assert "The kidneys are normal." in result
    # spleen should NOT be replaced with normal text
    assert "The spleen is normal." not in result


# ===== Group Tests =====


def test_group_all_unreported_interpolate_on(groups_template):
    """All group members unreported, interpolate=true -> joint_normal text."""
    template = _with_schema_overrides(groups_template, interpolate_normal=True)
    findings = {"liver": "Hepatomegaly.", "kidneys": "Renal cysts."}
    result = render_report(template, findings, STANDARD_TECHNIQUE)
    assert "The spleen and pancreas are unremarkable." in result
    # Individual normals should NOT appear
    assert "The spleen is normal." not in result
    assert "The pancreas is normal." not in result


def test_group_all_unreported_interpolate_off(groups_template):
    """All group members unreported, interpolate=false -> each shows __NOT_DOCUMENTED__."""
    findings = {"liver": "Hepatomegaly.", "kidneys": "Renal cysts."}
    result = render_report(groups_template, findings, STANDARD_TECHNIQUE)
    # Count NOT_DOCUMENTED occurrences -- should be 2 (spleen + pancreas)
    assert result.count(NOT_DOCUMENTED) == 2


def test_group_partial_abnormal(groups_template):
    """One group member has findings, interpolate=true -> abnormal shows finding."""
    template = _with_schema_overrides(groups_template, interpolate_normal=True)
    findings = {
        "liver": "Hepatomegaly.",
        "spleen": "Splenomegaly.",
        "kidneys": "Normal.",
    }
    # spleen is reported, pancreas is unreported -> pancreas gets individual normal
    result = render_report(template, findings, STANDARD_TECHNIQUE)
    assert "Splenomegaly." in result
    assert "The pancreas is normal." in result
    # Joint normal should NOT appear since not all unreported
    assert "The spleen and pancreas are unremarkable." not in result


# ===== Impression Tests =====


def test_impression_true_no_callable(freeform_template):
    """impression=true, no generate_impression -> placeholder text in output."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "(impression not generated)" in result


def test_impression_true_with_callable(freeform_template):
    """impression=true, callable provided -> callable's return value in COMMENT section."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}

    def mock_impression(findings_text, clinical_history):
        return "Hepatomegaly noted. Clinical correlation advised."

    result = render_report(
        freeform_template, findings, STANDARD_TECHNIQUE,
        generate_impression=mock_impression,
    )
    assert "Hepatomegaly noted. Clinical correlation advised." in result
    assert "COMMENT" in result


def test_impression_false(freeform_template):
    """impression=false -> output does NOT contain COMMENT section."""
    template = _with_schema_overrides(freeform_template, impression=False)
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(template, findings, STANDARD_TECHNIQUE)
    assert "COMMENT" not in result


# ===== Important-First Tests =====


def test_important_first_freeform(freeform_template):
    """important_fields=["kidneys"], freeform -> kidneys appears before liver/spleen in FINDINGS."""
    findings = {
        "liver": "Hepatomegaly.",
        "spleen": "Splenomegaly.",
        "kidneys": "Bilateral renal cysts.",
    }
    result = render_report(
        freeform_template, findings, STANDARD_TECHNIQUE,
        important_fields=["kidneys"],
    )
    # kidneys finding should appear before liver and spleen findings
    kidneys_pos = result.index("Bilateral renal cysts.")
    liver_pos = result.index("Hepatomegaly.")
    spleen_pos = result.index("Splenomegaly.")
    assert kidneys_pos < liver_pos
    assert kidneys_pos < spleen_pos


def test_important_first_empty(freeform_template):
    """important_fields=None -> template order preserved."""
    findings = {
        "liver": "Hepatomegaly.",
        "spleen": "Splenomegaly.",
        "kidneys": "Bilateral renal cysts.",
    }
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    liver_pos = result.index("Hepatomegaly.")
    spleen_pos = result.index("Splenomegaly.")
    kidneys_pos = result.index("Bilateral renal cysts.")
    assert liver_pos < spleen_pos < kidneys_pos


# ===== Output Format Tests =====


def test_guidance_stripped(freeform_template):
    """Output does NOT contain Guidance section or its content."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "Guidance" not in result
    assert "Test guidance content to be stripped." not in result


def test_section_headers_plain_text(freeform_template):
    """Output contains FINDINGS as plain text, not ## FINDINGS."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "FINDINGS" in result
    assert "## FINDINGS" not in result
    assert "CLINICAL HISTORY" in result
    assert "## CLINICAL HISTORY" not in result


def test_blank_line_cleanup(freeform_template):
    """Output does not contain 3+ consecutive blank lines."""
    template = _with_schema_overrides(freeform_template, impression=False)
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(template, findings, STANDARD_TECHNIQUE)
    # Check no 3+ consecutive blank lines (4+ newlines in a row)
    assert "\n\n\n\n" not in result


# ===== Technique & Comparison Tests =====


def test_technique_substitution(freeform_template):
    """Technique dict values appear in TECHNIQUE and CLINICAL HISTORY sections."""
    findings = {"liver": "Normal.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "Test technique." in result
    assert "Test indication." in result


def test_comparison_default(freeform_template):
    """No comparison in technique dict -> 'None available.' in output."""
    findings = {"liver": "Normal.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert "None available." in result


# ===== Measurement Tests =====


def test_measurement_substitution(measurements_template):
    """Measurement values in technique dict -> substituted in output."""
    findings = {"liver": "Fatty liver.", "spleen": "Splenomegaly."}
    technique = {
        **STANDARD_TECHNIQUE,
        "liver_span_cm": "16.5",
        "spleen_length_cm": "14.2",
    }
    result = render_report(measurements_template, findings, technique)
    assert "16.5" in result
    assert "14.2" in result


def test_measurement_missing(measurements_template):
    """Measurement placeholder with no value -> __NOT_DOCUMENTED__ in output."""
    findings = {"liver": "Fatty liver.", "spleen": "Splenomegaly."}
    result = render_report(measurements_template, findings, STANDARD_TECHNIQUE)
    # Measurement placeholders without values become NOT_DOCUMENTED
    assert NOT_DOCUMENTED in result


# ===== Optional Field Tests =====


def test_optional_field_omitted(measurements_template):
    """Optional field with no finding, interpolate=false -> placeholder line removed."""
    findings = {"liver": "Fatty liver.", "spleen": "Splenomegaly."}
    result = render_report(measurements_template, findings, STANDARD_TECHNIQUE)
    # 'others' is optional with no finding -- its placeholder should be gone
    assert "{{others}}" not in result


# ===== Post-Render Validation Tests =====


def test_post_render_warns_on_unresolved(freeform_template, caplog):
    """Template with unknown placeholder -> warning logged."""
    # Inject an unknown placeholder into the FINDINGS section of the body
    modified_body = freeform_template.body.replace(
        "{{kidneys}}", "{{kidneys}}\n\n{{unknown_field}}"
    )
    template = LoadedTemplate(
        schema=freeform_template.schema,
        body=modified_body,
        file_path=freeform_template.file_path,
    )
    findings = {"liver": "Normal.", "spleen": "Normal.", "kidneys": "Normal."}
    with caplog.at_level(logging.WARNING):
        result = render_report(template, findings, STANDARD_TECHNIQUE)
    assert "Unresolved placeholder remaining in output" in caplog.text
    assert "unknown_field" in caplog.text


# ===== Structured Renderer Tests =====


def test_structured_table_to_plain(structured_template):
    """Structured variant -> output contains colon-separated lines."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(structured_template, findings, STANDARD_TECHNIQUE)
    assert "Liver: See below" in result
    assert "|" not in result.split("FINDINGS")[1].split("COMMENT")[0] if "COMMENT" in result else True


def test_structured_normal_status(structured_template):
    """Structured + interpolate=true, unreported -> 'Liver: Normal'."""
    template = _with_schema_overrides(structured_template, interpolate_normal=True)
    findings = {"liver": "Hepatomegaly."}
    result = render_report(template, findings, STANDARD_TECHNIQUE)
    assert "Liver: See below" in result
    assert "Spleen: Normal" in result
    assert "Kidneys: Normal" in result


def test_structured_not_documented(structured_template):
    """Structured + interpolate=false, unreported -> '__NOT_DOCUMENTED__' status."""
    findings = {"liver": "Hepatomegaly."}
    result = render_report(structured_template, findings, STANDARD_TECHNIQUE)
    assert "Liver: See below" in result
    assert NOT_DOCUMENTED in result


def test_structured_key_other_sections(structured_template):
    """Structured + important_fields -> Key Findings has important, Other has rest."""
    findings = {
        "liver": "Hepatomegaly.",
        "spleen": "Splenomegaly.",
        "kidneys": "Bilateral cysts.",
    }
    result = render_report(
        structured_template, findings, STANDARD_TECHNIQUE,
        important_fields=["kidneys"],
    )
    # Key Findings should have kidneys
    key_section = result.split("Key Findings")[1].split("Other Findings")[0]
    other_section = result.split("Other Findings")[1]
    assert "Bilateral cysts." in key_section
    assert "Hepatomegaly." in other_section or "Splenomegaly." in other_section


# ===== Factory Tests =====


def test_render_report_factory_freeform(freeform_template):
    """render_report() with freeform template -> works correctly."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(freeform_template, findings, STANDARD_TECHNIQUE)
    assert isinstance(result, str)
    assert "Hepatomegaly." in result
    assert "FINDINGS" in result


def test_render_report_factory_structured(structured_template):
    """render_report() with structured template -> works correctly."""
    findings = {"liver": "Hepatomegaly.", "spleen": "Normal.", "kidneys": "Normal."}
    result = render_report(structured_template, findings, STANDARD_TECHNIQUE)
    assert isinstance(result, str)
    assert "Liver: See below" in result
