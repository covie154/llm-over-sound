"""Pydantic models for radiology report template validation and LLM output schemas."""

from __future__ import annotations

import keyword
import re
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    field_validator,
    model_validator,
)

# ===== Constants =====

NOT_DOCUMENTED = "__NOT_DOCUMENTED__"
"""Sentinel value for unreported fields (per D-29)."""

PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+(?::\w+)?)\}\}")
"""Regex matching {{field_name}} and {{type:name}} placeholders (per D-01 through D-04)."""

FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
"""Lowercase snake_case field names starting with a letter (per Pitfall 2 in research)."""


# ===== Field-Level Models =====


class FieldDefinition(BaseModel):
    """A single template field (organ-level finding).

    Each field has a name (used as placeholder token and Pydantic field name),
    default normal text authored by the radiologist, and an optional sex tag
    for sex-dependent anatomy (e.g. prostate vs uterus).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    normal: str
    sex: Optional[str] = None
    optional: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure field name is lowercase snake_case and not a Python keyword."""
        if not FIELD_NAME_PATTERN.match(v):
            raise ValueError(
                f"Field name '{v}' must be lowercase snake_case starting with a letter"
                f" and not a Python keyword"
            )
        if keyword.iskeyword(v):
            raise ValueError(
                f"Field name '{v}' must be lowercase snake_case starting with a letter"
                f" and not a Python keyword"
            )
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: Optional[str]) -> Optional[str]:
        """Ensure sex is one of None, 'male', or 'female'."""
        if v is not None and v not in ("male", "female"):
            raise ValueError(f"sex must be 'male', 'female', or null, got '{v}'")
        return v


# ===== Group Models =====


class GroupPartial(BaseModel):
    """A pre-authored partial normal text for a subset of group members.

    When a group partially expands (some members abnormal, some normal),
    the normal members can use this combined text instead of individual
    normal text strings.
    """

    model_config = ConfigDict(extra="forbid")

    members: list[str]
    text: str


class FieldGroup(BaseModel):
    """A group of fields with joint normal text.

    Groups allow collapsing multiple normal findings into a single sentence
    (e.g. 'The spleen, adrenal glands and pancreas are unremarkable.').
    Each group must have at least 2 members, and each member must reference
    a field defined in the template's fields list.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    members: list[str]
    joint_normal: str
    partials: list[GroupPartial] = []

    @field_validator("members")
    @classmethod
    def validate_members_count(cls, v: list[str]) -> list[str]:
        """Ensure group has at least 2 members."""
        if len(v) < 2:
            raise ValueError(f"Group must have at least 2 members, got {len(v)}")
        return v

    @model_validator(mode="after")
    def validate_partial_members(self) -> FieldGroup:
        """Ensure each partial's members are a subset of group members."""
        group_members = set(self.members)
        for partial in self.partials:
            invalid = set(partial.members) - group_members
            if invalid:
                raise ValueError(
                    f"Partial members {invalid} not in group '{self.name}' members"
                )
        return self


# ===== Template Schema =====


class TemplateSchema(BaseModel):
    """Complete template metadata from YAML frontmatter.

    Validates the full template structure including study identification,
    ordered field definitions, field groups, technique text, and renderer
    flags. Uses strict validation (extra='forbid') to catch typos and
    invalid keys in template YAML per D-26.
    """

    model_config = ConfigDict(extra="forbid")

    study_name: str
    aliases: list[str]
    fields: list[FieldDefinition]
    groups: list[FieldGroup] = []
    technique: str
    interpolate_normal: bool = False
    impression: bool = True
    important_first: bool = False
    variant: Literal["freeform", "structured"] = "freeform"

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        """Ensure at least one alias is provided."""
        if len(v) < 1:
            raise ValueError("At least one alias is required")
        return v

    @field_validator("fields")
    @classmethod
    def validate_fields_nonempty(cls, v: list[FieldDefinition]) -> list[FieldDefinition]:
        """Ensure at least one field is defined."""
        if len(v) < 1:
            raise ValueError("At least one field is required")
        return v

    @model_validator(mode="after")
    def validate_groups_against_fields(self) -> TemplateSchema:
        """Cross-validate groups against fields list.

        Checks:
        1. Every group member references a defined field.
        2. No field appears in multiple groups.
        3. No duplicate field names in the fields list.
        """
        field_names = {f.name for f in self.fields}

        # Check for duplicate field names
        seen_names: set[str] = set()
        for f in self.fields:
            if f.name in seen_names:
                raise ValueError(f"Duplicate field name: '{f.name}'")
            seen_names.add(f.name)

        # Check group members
        seen_in_groups: set[str] = set()
        for group in self.groups:
            for member in group.members:
                if member not in field_names:
                    raise ValueError(
                        f"Group '{group.name}' references field '{member}' "
                        f"which is not in the fields list. "
                        f"Available fields: {sorted(field_names)}"
                    )
                if member in seen_in_groups:
                    raise ValueError(
                        f"Field '{member}' appears in multiple groups. "
                        f"Each field can belong to at most one group."
                    )
                seen_in_groups.add(member)

        return self


# ===== LLM Output Models =====


class StudyTypeClassification(BaseModel):
    """LLM output model for stage 1: study type classification.

    The study_type must match a known alias from the template registry.
    Confidence is a float between 0.0 and 1.0 for future threshold-based
    clarification requests.
    """

    model_config = ConfigDict(extra="forbid")

    study_type: str
    confidence: float = Field(ge=0.0, le=1.0)


# ===== Utility Functions =====


def create_findings_model(
    schema: TemplateSchema,
    technique_fields: list[str] | None = None,
) -> type[BaseModel]:
    """Generate a dynamic Pydantic model from a template's field list.

    Each template field becomes an Optional[str] field defaulting to None.
    None means unreported (maps to __NOT_DOCUMENTED__ or normal text
    depending on interpolate_normal). Technique fields are included
    alongside anatomical fields per D-20.

    Args:
        schema: Validated template schema.
        technique_fields: Optional list of technique placeholder field names
            extracted from the template body.

    Returns:
        A Pydantic model class with one Optional[str] field per template field.
    """
    field_definitions: dict = {}
    for field_def in schema.fields:
        field_definitions[field_def.name] = (Optional[str], None)

    if technique_fields:
        for tech_field in technique_fields:
            field_definitions[tech_field] = (Optional[str], None)

    model_name = f"{schema.study_name.replace(' ', '')}Findings"
    model = create_model(
        model_name,
        __config__=ConfigDict(extra="forbid"),
        **field_definitions,
    )
    return model


def validate_body_placeholders(schema: TemplateSchema, body: str) -> list[str]:
    """Cross-validate frontmatter fields against body placeholders.

    Returns a list of warning/error strings. Empty list means no issues.

    Checks:
    1. Fields defined in frontmatter but not referenced in body.
    2. Plain placeholders in body that have no matching field in frontmatter.

    Typed placeholders (measurement:, technique:) are not checked against
    the fields list since they are a different namespace.

    Args:
        schema: Validated template schema.
        body: The markdown template body text.

    Returns:
        List of warning/error strings. Empty means all clear.
    """
    issues: list[str] = []

    # Extract all placeholders from body
    all_placeholders = PLACEHOLDER_PATTERN.findall(body)

    # Separate plain field placeholders from typed placeholders
    plain_placeholders: set[str] = set()
    for placeholder in all_placeholders:
        if ":" not in placeholder:
            plain_placeholders.add(placeholder)

    schema_field_names = {f.name for f in schema.fields}

    # Check 1: Fields in schema but not in body
    for name in schema_field_names:
        if name not in plain_placeholders:
            issues.append(
                f"Field '{name}' defined in frontmatter but has no placeholder"
                f" in template body"
            )

    # Check 2: Plain placeholders in body not in schema
    for name in plain_placeholders:
        if name not in schema_field_names:
            issues.append(
                f"Placeholder '{{{{{name}}}}}' in template body has no matching"
                f" field in frontmatter"
            )

    return issues
