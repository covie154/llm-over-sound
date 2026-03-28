"""Backward-compatibility shim -- real code lives in lib.templates.schema.

This file exists so that `from lib.template_schema import X` continues
to work. New code should import from `lib.templates` or `lib.templates.schema`.
"""

from .templates.schema import *  # noqa: F401, F403
from .templates.schema import (
    FieldDefinition,
    GroupPartial,
    FieldGroup,
    TemplateSchema,
    StudyTypeClassification,
    create_findings_model,
    validate_body_placeholders,
    NOT_DOCUMENTED,
    PLACEHOLDER_PATTERN,
    FIELD_NAME_PATTERN,
)
