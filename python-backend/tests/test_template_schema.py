"""Tests for template schema validation models.

Covers requirements: TMPL-01, TMPL-02, TMPL-03, TMPL-07, TMPL-08, TMPL-09,
FWRK-03, FWRK-04. Decision traceability noted in test docstrings.
"""

import pytest
import frontmatter
from pydantic import ValidationError

from lib.template_schema import (
    FieldDefinition,
    FieldGroup,
    GroupPartial,
    TemplateSchema,
    StudyTypeClassification,
    create_findings_model,
    validate_body_placeholders,
    NOT_DOCUMENTED,
)


# ===== Helpers =====


def _valid_schema_data(**overrides):
    """Build minimal valid TemplateSchema kwargs, with optional overrides."""
    data = {
        "study_name": "Test",
        "aliases": ["test"],
        "fields": [FieldDefinition(name="liver", normal="Normal liver.")],
        "technique": "CT performed.",
    }
    data.update(overrides)
    return data


# ===== Positive Tests: Template Loading =====


def test_load_template_file(sample_template_path):
    """TMPL-01: Template loads via python-frontmatter and validates."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    assert schema.study_name == "Test CT Abdomen"
    assert len(schema.fields) == 4
    assert len(schema.groups) == 1


def test_field_order_preserved(sample_template_path):
    """TMPL-02: Field list order matches YAML order (craniocaudal)."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    names = [f.name for f in schema.fields]
    assert names == ["liver", "spleen", "pancreas", "uterus"]


def test_field_normal_text(sample_template_path):
    """TMPL-03: Each field has a non-empty normal string."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    for field in schema.fields:
        assert len(field.normal) > 0, f"Field '{field.name}' has empty normal text"
    assert schema.fields[0].normal == (
        "The liver is normal in size and attenuation. No focal lesion."
    )


def test_field_groups(sample_template_path):
    """TMPL-07: Group with members validates, joint_normal present."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    group = schema.groups[0]
    assert group.name == "spleen_pancreas"
    assert group.members == ["spleen", "pancreas"]
    assert group.joint_normal == "The spleen and pancreas are unremarkable."
    assert isinstance(group.partials, list)


def test_technique_section(sample_template_path):
    """TMPL-08: Technique string is non-empty and matches expected boilerplate."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    assert schema.technique.startswith("CT of the abdomen")
    assert len(schema.technique) > 0


def test_guidance_section_optional():
    """TMPL-09: TemplateSchema validates without guidance in frontmatter."""
    data = _valid_schema_data()
    schema = TemplateSchema(**data)
    assert schema.study_name == "Test"


def test_guidance_section_present_in_body(sample_template_path, sample_template_body):
    """TMPL-09: Sample fixture body contains Guidance section and schema still validates."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    assert schema.study_name == "Test CT Abdomen"
    assert "## Guidance" in sample_template_body
    assert "enhancement pattern" in sample_template_body


# ===== Positive Tests: Findings Model =====


def test_findings_model(sample_template_path):
    """FWRK-04, D-16, D-17: Dynamic findings model has correct fields."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    FindingsModel = create_findings_model(schema)
    assert "liver" in FindingsModel.model_fields
    assert "spleen" in FindingsModel.model_fields
    assert "pancreas" in FindingsModel.model_fields
    assert "uterus" in FindingsModel.model_fields
    findings = FindingsModel(liver="Hepatomegaly")
    assert findings.liver == "Hepatomegaly"
    assert findings.spleen is None


def test_findings_model_with_technique_fields():
    """D-20: create_findings_model with technique_fields adds those fields."""
    data = _valid_schema_data()
    schema = TemplateSchema(**data)
    FindingsModel = create_findings_model(schema, technique_fields=["phase", "contrast"])
    assert "phase" in FindingsModel.model_fields
    assert "contrast" in FindingsModel.model_fields
    assert "liver" in FindingsModel.model_fields


def test_findings_model_rejects_unknown_fields(sample_template_path):
    """Findings model with extra='forbid' rejects unknown field names."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    FindingsModel = create_findings_model(schema)
    with pytest.raises(ValidationError, match="bogus_field"):
        FindingsModel(bogus_field="should fail")


# ===== Positive Tests: Study Type Classification =====


def test_study_type_classification():
    """StudyTypeClassification with valid study_type and confidence validates."""
    result = StudyTypeClassification(study_type="ct abdomen", confidence=0.95)
    assert result.study_type == "ct abdomen"
    assert result.confidence == 0.95


# ===== Positive Tests: Body Placeholder Validation =====


def test_validate_body_placeholders_clean(sample_template_path, sample_template_body):
    """D-28: No warnings when all fields have body placeholders."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    issues = validate_body_placeholders(schema, sample_template_body)
    # All 4 fields (liver, spleen, pancreas, uterus) have {{field}} placeholders
    field_missing_issues = [i for i in issues if "defined in frontmatter" in i]
    assert len(field_missing_issues) == 0


# ===== Positive Tests: Defaults =====


def test_interpolate_normal_defaults_false():
    """TemplateSchema without explicit interpolate_normal has it False."""
    data = _valid_schema_data()
    schema = TemplateSchema(**data)
    assert schema.interpolate_normal is False


def test_impression_defaults_true():
    """TemplateSchema without explicit impression has it True."""
    data = _valid_schema_data()
    schema = TemplateSchema(**data)
    assert schema.impression is True


def test_important_first_defaults_false():
    """TemplateSchema without explicit important_first has it False."""
    data = _valid_schema_data()
    schema = TemplateSchema(**data)
    assert schema.important_first is False


# ===== Positive Tests: Sex-Dependent Fields =====


def test_sex_dependent_field(sample_template_path):
    """D-12: Field with sex='female' validates correctly."""
    post = frontmatter.load(str(sample_template_path))
    schema = TemplateSchema(**post.metadata)
    uterus = [f for f in schema.fields if f.name == "uterus"][0]
    assert uterus.sex == "female"
    assert uterus.normal == "The uterus is normal in size and morphology."


# ===== Positive Tests: NOT_DOCUMENTED Sentinel =====


def test_not_documented_sentinel():
    """NOT_DOCUMENTED constant is the expected sentinel string."""
    assert NOT_DOCUMENTED == "__NOT_DOCUMENTED__"


# ===== Negative Tests: Strict Validation =====


def test_strict_validation_rejects_unknown_keys():
    """FWRK-03, D-26: Extra key in frontmatter raises ValidationError."""
    data = _valid_schema_data(bogus_key="fail")
    with pytest.raises(ValidationError, match="bogus_key"):
        TemplateSchema(**data)


# ===== Negative Tests: Group Validation =====


def test_group_member_not_in_fields():
    """D-06: Group referencing nonexistent field raises ValidationError."""
    data = _valid_schema_data(
        groups=[
            FieldGroup(
                name="bad_group",
                members=["liver", "kidneys"],
                joint_normal="Normal.",
            )
        ]
    )
    with pytest.raises(ValidationError, match="kidneys"):
        TemplateSchema(**data)


def test_field_in_multiple_groups():
    """D-07: Field in two groups raises ValidationError."""
    data = _valid_schema_data(
        fields=[
            FieldDefinition(name="liver", normal="Normal."),
            FieldDefinition(name="spleen", normal="Normal."),
            FieldDefinition(name="pancreas", normal="Normal."),
        ],
        groups=[
            FieldGroup(
                name="group_a",
                members=["liver", "spleen"],
                joint_normal="Normal.",
            ),
            FieldGroup(
                name="group_b",
                members=["liver", "pancreas"],
                joint_normal="Normal.",
            ),
        ],
    )
    with pytest.raises(ValidationError, match="multiple groups"):
        TemplateSchema(**data)


def test_group_minimum_members():
    """Group with 1 member raises ValidationError."""
    with pytest.raises(ValidationError, match="at least 2 members"):
        FieldGroup(
            name="solo",
            members=["liver"],
            joint_normal="Normal.",
        )


def test_group_partial_members_not_in_group():
    """Partial with member not in group raises ValidationError."""
    with pytest.raises(ValidationError, match="not in group"):
        FieldGroup(
            name="test_group",
            members=["liver", "spleen"],
            joint_normal="Normal.",
            partials=[
                GroupPartial(members=["liver", "kidneys"], text="Normal.")
            ],
        )


# ===== Negative Tests: Field Name Validation =====


def test_field_name_python_keyword():
    """Pitfall 2: Field named 'class' raises ValidationError."""
    with pytest.raises(ValidationError, match="not a Python keyword"):
        FieldDefinition(name="class", normal="Normal.")


def test_field_name_invalid_format():
    """Field named 'Liver' or '123abc' raises ValidationError."""
    with pytest.raises(ValidationError, match="lowercase snake_case"):
        FieldDefinition(name="Liver", normal="Normal.")
    with pytest.raises(ValidationError, match="lowercase snake_case"):
        FieldDefinition(name="123abc", normal="Normal.")


# ===== Negative Tests: Sex Validation =====


def test_invalid_sex_value():
    """Field with sex='other' raises ValidationError."""
    with pytest.raises(ValidationError, match="male.*female"):
        FieldDefinition(name="organ", normal="Normal.", sex="other")


# ===== Negative Tests: Study Type Classification =====


def test_study_type_confidence_out_of_range():
    """Confidence > 1.0 or < 0.0 raises ValidationError."""
    with pytest.raises(ValidationError):
        StudyTypeClassification(study_type="ct", confidence=1.5)
    with pytest.raises(ValidationError):
        StudyTypeClassification(study_type="ct", confidence=-0.1)


# ===== Negative Tests: Body Placeholder Validation =====


def test_validate_body_field_in_frontmatter_not_body():
    """D-28: Field in schema but no body placeholder produces warning."""
    data = _valid_schema_data(
        fields=[
            FieldDefinition(name="liver", normal="Normal."),
            FieldDefinition(name="kidneys", normal="Normal."),
        ]
    )
    schema = TemplateSchema(**data)
    body = "{{liver}}"
    issues = validate_body_placeholders(schema, body)
    matching = [i for i in issues if "kidneys" in i]
    assert len(matching) > 0


def test_validate_body_placeholder_not_in_frontmatter():
    """D-28: Body placeholder with no schema field produces error."""
    data = _valid_schema_data()
    schema = TemplateSchema(**data)
    body = "{{liver}}\n{{kidneys}}"
    issues = validate_body_placeholders(schema, body)
    matching = [i for i in issues if "kidneys" in i]
    assert len(matching) > 0


# ===== Negative Tests: Template-Level Validation =====


def test_duplicate_field_names():
    """Two fields with same name raises ValidationError."""
    data = _valid_schema_data(
        fields=[
            FieldDefinition(name="liver", normal="Normal."),
            FieldDefinition(name="liver", normal="Also normal."),
        ]
    )
    with pytest.raises(ValidationError, match="Duplicate field name"):
        TemplateSchema(**data)


def test_empty_aliases_rejected():
    """aliases=[] raises ValidationError."""
    data = _valid_schema_data(aliases=[])
    with pytest.raises(ValidationError, match="At least one alias"):
        TemplateSchema(**data)


def test_empty_fields_rejected():
    """fields=[] raises ValidationError."""
    data = _valid_schema_data(fields=[])
    with pytest.raises(ValidationError, match="At least one field"):
        TemplateSchema(**data)
