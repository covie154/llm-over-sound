"""
lib.templates -- template loading, validation, and registry sub-package.
"""

from .schema import (
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
from .exceptions import (
    TemplateLoadError,
    TemplateValidationError,
    TemplateNotFoundError,
)
from .loader import LoadedTemplate, load_template, discover_templates

__all__ = [
    # Schema models
    "FieldDefinition",
    "GroupPartial",
    "FieldGroup",
    "TemplateSchema",
    "StudyTypeClassification",
    "create_findings_model",
    "validate_body_placeholders",
    "NOT_DOCUMENTED",
    "PLACEHOLDER_PATTERN",
    "FIELD_NAME_PATTERN",
    # Exceptions
    "TemplateLoadError",
    "TemplateValidationError",
    "TemplateNotFoundError",
    # Loader
    "LoadedTemplate",
    "load_template",
    "discover_templates",
]
