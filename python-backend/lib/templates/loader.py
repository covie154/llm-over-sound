"""Template file discovery and parsing.

Scans directories for *.rpt.md files (per D-16), parses each with
python-frontmatter, validates with TemplateSchema, and enforces
body placeholder cross-validation as a fatal error (per D-03).
"""

import pathlib
from dataclasses import dataclass

import frontmatter

from .schema import TemplateSchema, validate_body_placeholders
from .exceptions import TemplateValidationError, TemplateLoadError


@dataclass(frozen=True)
class LoadedTemplate:
    """A fully parsed and validated template, ready for pipeline use.

    Per D-10: Contains validated schema, body text, and source file path.
    Templates are parsed once at startup and cached by the registry.
    """
    schema: TemplateSchema
    body: str
    file_path: str


def discover_templates(templates_dir: pathlib.Path) -> list[pathlib.Path]:
    """Find all *.rpt.md files recursively under templates_dir.

    Per D-15: Recurses into subdirectories (ct/, us/, mri/).
    Per D-16: Only *.rpt.md files are treated as templates.

    Args:
        templates_dir: Root directory to scan.

    Returns:
        Sorted list of template file paths (deterministic order).

    Raises:
        TemplateValidationError: If directory doesn't exist (per D-04).
    """
    if not templates_dir.is_dir():
        raise TemplateValidationError(
            [TemplateLoadError(str(templates_dir), "Templates directory does not exist")]
        )
    return sorted(templates_dir.rglob("*.rpt.md"))


def load_template(path: pathlib.Path) -> LoadedTemplate:
    """Parse and validate a single template file.

    Uses python-frontmatter to split YAML frontmatter from markdown body.
    Validates frontmatter via TemplateSchema (Pydantic, extra='forbid').
    Cross-validates body placeholders against field list (per D-03: fatal).

    Args:
        path: Path to a *.rpt.md template file.

    Returns:
        LoadedTemplate with validated schema and body.

    Raises:
        TemplateValidationError: If parsing or validation fails.
    """
    try:
        post = frontmatter.load(str(path))
    except Exception as e:
        raise TemplateValidationError(
            [TemplateLoadError(str(path), f"Failed to parse frontmatter: {e}")]
        )

    try:
        schema = TemplateSchema(**post.metadata)
    except Exception as e:
        raise TemplateValidationError(
            [TemplateLoadError(str(path), f"Schema validation failed: {e}")]
        )

    body = post.content

    # D-03: Body placeholder cross-validation is fatal at load time.
    # Skip for composite templates -- their body references fields from bases
    # that are not in the composite's own frontmatter fields list.
    # Validation runs after composition instead (Pitfall 5).
    if schema.composable_from is not None:
        pass  # Defer validation to compose_template()
    else:
        issues = validate_body_placeholders(schema, body)
        if issues:
            raise TemplateValidationError(
                [TemplateLoadError(str(path), issue) for issue in issues]
            )

    return LoadedTemplate(schema=schema, body=body, file_path=str(path))
