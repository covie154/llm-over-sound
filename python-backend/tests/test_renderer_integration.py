"""Integration tests: renderer with real production templates.

Per D-33: Integration tests use real clinical templates, not minimal fixtures.
These tests validate the renderer works end-to-end with actual template content,
real field names, real group configurations, and real measurement placeholders.
"""

from __future__ import annotations

import pathlib

import pytest

from lib.templates.loader import LoadedTemplate, load_template
from lib.templates.schema import NOT_DOCUMENTED, TemplateSchema
from lib.templates import render_report


# ===== Template Paths =====

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "rpt_templates"


# ===== Helpers =====


def _with_schema_overrides(template: LoadedTemplate, **overrides) -> LoadedTemplate:
    """Create a new LoadedTemplate with schema field overrides."""
    schema_data = template.schema.model_dump()
    schema_data.update(overrides)
    new_schema = TemplateSchema(**schema_data)
    return LoadedTemplate(schema=new_schema, body=template.body, file_path=template.file_path)


# ===== Fixtures =====


@pytest.fixture
def ct_ap_template():
    return load_template(TEMPLATES_DIR / "ct" / "ct_ap.rpt.md")


@pytest.fixture
def ct_ap_structured_template():
    return load_template(TEMPLATES_DIR / "ct" / "ct_ap_structured.rpt.md")


@pytest.fixture
def ct_thorax_template():
    return load_template(TEMPLATES_DIR / "ct" / "ct_thorax.rpt.md")


@pytest.fixture
def us_hbs_template():
    return load_template(TEMPLATES_DIR / "us" / "us_hbs.rpt.md")


# ===== Realistic Clinical Data =====


CT_AP_TECHNIQUE = {
    "phase": "CT of the abdomen and pelvis was performed with intravenous contrast in the portal venous phase.",
    "clinical_indication": "Abdominal pain. ?appendicitis.",
}

CT_AP_PARTIAL_FINDINGS = {
    "liver": "The liver contains a 3.2 cm hypodense lesion in segment VI, suspicious for metastasis.",
    "kidneys": "A 1.5 cm simple cyst is noted in the right kidney. Left kidney is unremarkable.",
    "bowel": "Mild wall thickening of the terminal ileum with surrounding fat stranding.",
}

CT_AP_ALL_FINDINGS = {
    "liver": "The liver contains a 3.2 cm hypodense lesion in segment VI, suspicious for metastasis.",
    "gallbladder": "The gallbladder is distended with wall thickening.",
    "cbd": "The CBD measures 8 mm, mildly dilated.",
    "spleen": "The spleen is mildly enlarged at 14 cm.",
    "adrenals": "A 1.2 cm left adrenal nodule, indeterminate.",
    "pancreas": "The pancreas is atrophic but otherwise unremarkable.",
    "kidneys": "A 1.5 cm simple cyst is noted in the right kidney. Left kidney is unremarkable.",
    "bowel": "Mild wall thickening of the terminal ileum with surrounding fat stranding.",
    "mesentery": "Mesenteric fat stranding adjacent to the terminal ileum.",
    "lymph_nodes": "A 1.1 cm mesenteric lymph node noted adjacent to the terminal ileum.",
    "bladder": "The urinary bladder is normal.",
    "uterus_ovaries": "The uterus is anteverted. A 2.5 cm left ovarian cyst.",
    "vessels": "The abdominal aorta is ectatic at 2.4 cm.",
    "lung_bases": "Bibasal atelectasis.",
    "free_fluid": "A small amount of free fluid in the pelvis.",
    "bones": "Degenerative changes of the lumbar spine.",
    "soft_tissues": "No abdominal wall hernia.",
}

CT_THORAX_TECHNIQUE = {
    "phase": "CT of the thorax was performed with intravenous contrast in the arterial phase.",
    "clinical_indication": "Cough and dyspnoea. ?PE.",
}

CT_THORAX_PARTIAL_FINDINGS = {
    "lungs": "A 6 mm ground-glass nodule in the right upper lobe.",
    "pleura": "Small bilateral pleural effusions.",
    "mediastinum": "No pathological mediastinal or hilar lymphadenopathy.",
}

US_HBS_TECHNIQUE = {
    "phase": "Ultrasound of the hepatobiliary system was performed.",
    "clinical_indication": "RUQ pain. ?gallstones.",
    "liver_span_cm": "14.2",
    "cbd_diameter_mm": "4",
    "spleen_length_cm": "11.5",
}

US_HBS_FINDINGS = {
    "liver": "The liver is normal in echotexture. No focal lesion.",
    "gallbladder_cbd": "The gallbladder contains a 4mm echogenic focus with posterior acoustic shadowing, consistent with a gallstone. The CBD is normal in calibre.",
}


# ===== CT AP Freeform Tests =====


def test_ct_ap_freeform_all_findings(ct_ap_template):
    """CT AP template with all fields populated -> output contains all finding texts."""
    result = render_report(ct_ap_template, CT_AP_ALL_FINDINGS, CT_AP_TECHNIQUE)
    # Spot-check key findings text
    assert "3.2 cm hypodense lesion in segment VI" in result
    assert "wall thickening of the terminal ileum" in result
    assert "2.5 cm left ovarian cyst" in result
    assert "ectatic at 2.4 cm" in result
    assert "Bibasal atelectasis" in result
    # Should have FINDINGS and TECHNIQUE sections
    assert "FINDINGS" in result
    assert "TECHNIQUE" in result
    # No guidance should leak through
    assert "Guidance" not in result


def test_ct_ap_freeform_no_findings_no_interpolation(ct_ap_template):
    """CT AP, no findings, interpolate=false -> non-optional fields show __NOT_DOCUMENTED__."""
    result = render_report(ct_ap_template, {}, CT_AP_TECHNIQUE)
    # Required fields should all be NOT_DOCUMENTED (18 fields, minus optional vessels
    # and sex-dependent uterus_ovaries/prostate which are optional-like)
    assert NOT_DOCUMENTED in result
    # Specific field normals should NOT appear (interpolate is off)
    assert "The liver is normal in size and attenuation" not in result
    assert "The kidneys are normal in size and enhancement" not in result


def test_ct_ap_freeform_interpolate_normal(ct_ap_template):
    """CT AP, no findings, interpolate=true -> normal text for each field, groups use joint_normal."""
    template = _with_schema_overrides(ct_ap_template, interpolate_normal=True)
    result = render_report(template, {}, CT_AP_TECHNIQUE)
    # Individual normals for non-grouped fields
    assert "The liver is normal in size and attenuation" in result
    assert "The kidneys are normal in size and enhancement" in result
    # Group joint_normal should be used since ALL members are unreported
    assert "The gallbladder and common bile duct are normal" in result
    assert "The spleen, adrenal glands and pancreas are unremarkable" in result
    # NOT_DOCUMENTED should NOT appear
    assert NOT_DOCUMENTED not in result


def test_ct_ap_freeform_partial_group(ct_ap_template):
    """CT AP, spleen has finding but adrenals/pancreas unreported, interpolate=true -> partial text."""
    template = _with_schema_overrides(ct_ap_template, interpolate_normal=True)
    findings = {
        "spleen": "The spleen is enlarged at 15 cm.",
    }
    result = render_report(template, findings, CT_AP_TECHNIQUE)
    # Spleen has an explicit finding
    assert "The spleen is enlarged at 15 cm." in result
    # Adrenals + pancreas should get partial text
    assert "The adrenal glands and pancreas are unremarkable." in result
    # Joint normal should NOT appear since not all members unreported
    assert "The spleen, adrenal glands and pancreas are unremarkable" not in result


def test_ct_ap_freeform_rest_normal(ct_ap_template):
    """CT AP, partial findings, rest_normal=True -> reported show findings, rest show normal."""
    result = render_report(
        ct_ap_template, CT_AP_PARTIAL_FINDINGS, CT_AP_TECHNIQUE, rest_normal=True
    )
    # Explicit findings preserved
    assert "3.2 cm hypodense lesion in segment VI" in result
    assert "1.5 cm simple cyst" in result
    assert "wall thickening of the terminal ileum" in result
    # Unreported fields should have normal text, not NOT_DOCUMENTED
    assert NOT_DOCUMENTED not in result
    # Group collapse should apply for unreported group members
    assert "The gallbladder and common bile duct are normal" in result
    assert "The spleen, adrenal glands and pancreas are unremarkable" in result


def test_ct_ap_freeform_impression_with_callable(ct_ap_template):
    """CT AP, impression=true, callable -> COMMENT section contains callable output."""
    def mock_impression(findings_text, clinical_history):
        return "Focal liver lesion suspicious for metastasis. Clinical correlation recommended."

    result = render_report(
        ct_ap_template, CT_AP_PARTIAL_FINDINGS, CT_AP_TECHNIQUE,
        generate_impression=mock_impression,
    )
    assert "Focal liver lesion suspicious for metastasis" in result
    assert "COMMENT" in result


def test_ct_ap_freeform_impression_false(ct_ap_template):
    """CT AP, impression=false -> no COMMENT in output."""
    template = _with_schema_overrides(ct_ap_template, impression=False)
    result = render_report(template, CT_AP_PARTIAL_FINDINGS, CT_AP_TECHNIQUE)
    assert "COMMENT" not in result


def test_ct_ap_freeform_important_first(ct_ap_template):
    """CT AP, important_fields -> kidneys and bowel appear before liver in FINDINGS section."""
    template = _with_schema_overrides(ct_ap_template, important_first=True)
    result = render_report(
        template, CT_AP_PARTIAL_FINDINGS, CT_AP_TECHNIQUE,
        important_fields=["kidneys", "bowel"],
    )
    findings_section = result.split("FINDINGS")[1]
    kidneys_pos = findings_section.index("1.5 cm simple cyst")
    bowel_pos = findings_section.index("wall thickening of the terminal ileum")
    liver_pos = findings_section.index("3.2 cm hypodense lesion")
    assert kidneys_pos < liver_pos
    assert bowel_pos < liver_pos


# ===== CT AP Structured Tests =====


def test_ct_ap_structured_basic(ct_ap_structured_template):
    """CT AP structured, some findings -> colon-separated table lines, Key/Other sections."""
    findings = {
        "liver": "The liver contains a 3.2 cm hypodense lesion in segment VI.",
        "kidneys": "A 1.5 cm simple cyst in the right kidney.",
        "bowel": "Mild wall thickening of the terminal ileum.",
    }
    result = render_report(ct_ap_structured_template, findings, CT_AP_TECHNIQUE)
    # Colon-separated status lines
    assert "Liver: See below" in result
    assert "Kidneys: See below" in result
    assert "Bowel: See below" in result
    # Unreported fields should have NOT_DOCUMENTED status (interpolate=false)
    assert NOT_DOCUMENTED in result
    # Key Findings should contain the detailed text
    assert "3.2 cm hypodense lesion" in result
    # No markdown table pipes in the findings section
    findings_section = result.split("FINDINGS")[1]
    comment_split = findings_section.split("COMMENT")
    findings_before_comment = comment_split[0] if len(comment_split) > 1 else findings_section
    # Status lines should not have pipe characters
    status_area = findings_before_comment.split("Key Findings")[0]
    assert "|" not in status_area


def test_ct_ap_structured_interpolate_normal(ct_ap_structured_template):
    """CT AP structured, interpolate=true, no findings -> table shows Normal for each field."""
    template = _with_schema_overrides(ct_ap_structured_template, interpolate_normal=True)
    result = render_report(template, {}, CT_AP_TECHNIQUE)
    assert "Liver: Normal" in result
    assert "Kidneys: Normal" in result
    assert NOT_DOCUMENTED not in result


# ===== CT Thorax Tests =====


def test_ct_thorax_basic(ct_thorax_template):
    """CT thorax, partial findings -> renders correctly with freeform variant."""
    result = render_report(ct_thorax_template, CT_THORAX_PARTIAL_FINDINGS, CT_THORAX_TECHNIQUE)
    assert "6 mm ground-glass nodule" in result
    assert "bilateral pleural effusions" in result
    assert "No pathological mediastinal or hilar lymphadenopathy" in result
    # Unreported fields should be NOT_DOCUMENTED (interpolate=false)
    assert NOT_DOCUMENTED in result
    # Section headers
    assert "FINDINGS" in result
    assert "TECHNIQUE" in result
    assert "CLINICAL HISTORY" in result
    # Clinical indication
    assert "Cough and dyspnoea" in result


# ===== US HBS Tests =====


def test_us_hbs_with_measurements(us_hbs_template):
    """US HBS, findings + measurements -> measurement values substituted in body text."""
    result = render_report(us_hbs_template, US_HBS_FINDINGS, US_HBS_TECHNIQUE)
    # Finding text preserved
    assert "4mm echogenic focus with posterior acoustic shadowing" in result
    # Measurement values substituted in body measurement lines (two-pass)
    assert "14.2" in result  # liver_span_cm
    assert "4" in result     # cbd_diameter_mm (appears in measurement line)
    assert "11.5" in result  # spleen_length_cm
    # No remaining measurement placeholders
    assert "{{measurement:" not in result


def test_us_hbs_missing_measurements(us_hbs_template):
    """US HBS, no measurements in technique -> measurement placeholders become __NOT_DOCUMENTED__."""
    technique_no_measurements = {
        "phase": "Ultrasound of the hepatobiliary system was performed.",
        "clinical_indication": "RUQ pain. ?gallstones.",
    }
    result = render_report(us_hbs_template, US_HBS_FINDINGS, technique_no_measurements)
    # Measurement placeholders should be replaced with NOT_DOCUMENTED
    assert NOT_DOCUMENTED in result
    assert "{{measurement:" not in result


def test_us_hbs_interpolate_normal_with_measurements(us_hbs_template):
    """US HBS, interpolate=true, no findings -> normal text with measurements substituted."""
    template = _with_schema_overrides(us_hbs_template, interpolate_normal=True)
    result = render_report(template, {}, US_HBS_TECHNIQUE)
    # Normal text contains measurement placeholders that should be resolved
    # e.g. "measuring {{measurement:liver_span_cm}} cm" -> "measuring 14.2 cm"
    assert "14.2" in result
    assert "4" in result     # cbd_diameter_mm
    assert "11.5" in result  # spleen_length_cm
    assert NOT_DOCUMENTED not in result
    assert "{{measurement:" not in result


# ===== Cross-Template Tests =====


@pytest.fixture(params=["ct_ap", "ct_ap_structured", "ct_thorax", "us_hbs"])
def all_templates(request, ct_ap_template, ct_ap_structured_template, ct_thorax_template, us_hbs_template):
    """Parametrized fixture yielding each template."""
    templates = {
        "ct_ap": ct_ap_template,
        "ct_ap_structured": ct_ap_structured_template,
        "ct_thorax": ct_thorax_template,
        "us_hbs": us_hbs_template,
    }
    return templates[request.param]


def test_all_templates_no_guidance_in_output(all_templates):
    """All 4 templates -> output never contains Guidance section header or guidance content."""
    technique = {
        "phase": "Test technique.",
        "clinical_indication": "Test indication.",
    }
    result = render_report(all_templates, {}, technique)
    assert "Guidance" not in result
    assert "## Guidance" not in result


def test_all_templates_plain_text_headers(all_templates):
    """All 4 templates -> output has UPPERCASE section headers without ## prefix."""
    technique = {
        "phase": "Test technique.",
        "clinical_indication": "Test indication.",
    }
    result = render_report(all_templates, {}, technique)
    # Top-level ## headers should be converted to plain text
    assert "## FINDINGS" not in result
    assert "## TECHNIQUE" not in result
    assert "## CLINICAL HISTORY" not in result
    assert "## COMPARISON" not in result
    assert "## COMMENT" not in result
    # At least FINDINGS and TECHNIQUE should exist as plain text
    assert "FINDINGS" in result
    assert "TECHNIQUE" in result
