"""Report renderer: assembles formatted plain text reports from templates and findings.

Implements a base ReportRenderer with shared logic and two subclass variants:
FreeformRenderer (prose-style) and StructuredRenderer (colon-separated table + Key/Other sections).
A render_report() factory function dispatches based on template variant field.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from .loader import LoadedTemplate
from .schema import (
    FieldDefinition,
    FieldGroup,
    NOT_DOCUMENTED,
    PLACEHOLDER_PATTERN,
    TemplateSchema,
)

logger = logging.getLogger(__name__)

# ===== Constants =====

GUIDANCE_PATTERN = re.compile(
    r"^## Guidance\s*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

SECTION_HEADER_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)

BLANK_LINE_PATTERN = re.compile(r"\n{4,}")

TABLE_ROW_PATTERN = re.compile(r"\|\s*(.+?)\s*\|\s*\{\{(\w+)\}\}\s*\|")

TECHNIQUE_PATTERN = re.compile(r"\{\{technique:(\w+)\}\}")

MEASUREMENT_PATTERN = re.compile(r"\{\{measurement:(\w+)\}\}")


# ===== Base Renderer =====


class ReportRenderer:
    """Base renderer with shared logic for all template variants.

    Handles: field resolution, group collapse, technique/measurement substitution,
    guidance stripping, impression handling, header conversion, blank line cleanup,
    and post-render validation.
    """

    def render(
        self,
        template: LoadedTemplate,
        findings: dict,
        technique: dict,
        important_fields: list[str] | None = None,
        rest_normal: bool = False,
        generate_impression: Callable[[str, str], str] | None = None,
    ) -> str:
        """Render a report from a loaded template and findings dict.

        Args:
            template: Loaded and validated template.
            findings: Dict mapping field names to finding text (None = unreported).
            technique: Dict with technique values (phase, clinical_indication, comparison, measurements).
            important_fields: Optional list of field names to prioritise in output.
            rest_normal: If True, overrides interpolate_normal for this render call.
            generate_impression: Optional callable for impression generation.

        Returns:
            Formatted plain text report string.
        """
        schema = template.schema
        body = template.body

        # Determine effective interpolation flag (per D-04)
        interpolate = schema.interpolate_normal or rest_normal

        # Resolve field values from findings + interpolation
        field_values = self._resolve_field_values(schema, findings, interpolate)

        # Apply group collapse logic
        field_values = self._resolve_groups(schema, field_values, findings, interpolate)

        # Substitute technique placeholders (first pass)
        body = self._substitute_technique(body, technique)

        # Assemble body with field values (subclass override)
        body = self._assemble_body(body, field_values, important_fields)

        # Substitute measurement placeholders (second pass -- per two-pass approach)
        body = self._substitute_measurements(body, technique)

        # Strip guidance section
        body = self._strip_guidance(body)

        # Handle impression / COMMENT section
        body = self._handle_impression(
            body, schema, findings, technique, generate_impression
        )

        # Convert markdown headers to plain text UPPERCASE
        body = self._convert_headers(body)

        # Clean up blank lines
        body = self._cleanup_blank_lines(body)

        # Post-render validation (warn on remaining placeholders)
        body = self._post_render_validate(body)

        return body.strip()

    def _resolve_field_values(
        self,
        schema: TemplateSchema,
        findings: dict,
        interpolate: bool,
    ) -> dict[str, str | None]:
        """Map each template field to its resolved value.

        Args:
            schema: Template schema with field definitions.
            findings: Dict from LLM extraction (field_name -> text or None).
            interpolate: Whether to fill unreported fields with normal text.

        Returns:
            Dict mapping field_name -> resolved text, or None for omitted fields.
        """
        field_values: dict[str, str | None] = {}
        for field_def in schema.fields:
            finding = findings.get(field_def.name)
            if finding is not None:
                # LLM provided a value -- use it directly (per D-04)
                field_values[field_def.name] = finding
            elif interpolate:
                # Fill with template normal text
                field_values[field_def.name] = field_def.normal
            elif field_def.optional:
                # Optional field with no finding -- omit (placeholder line removed)
                field_values[field_def.name] = None
            else:
                # Required field, no interpolation -- NOT_DOCUMENTED
                field_values[field_def.name] = NOT_DOCUMENTED
        return field_values

    def _resolve_groups(
        self,
        schema: TemplateSchema,
        field_values: dict[str, str | None],
        findings: dict,
        interpolate: bool,
    ) -> dict[str, str | None]:
        """Apply group collapse logic for unreported fields.

        Only activates when interpolate is True (per D-03).

        Args:
            schema: Template schema with group definitions.
            field_values: Current field value mappings.
            findings: Original findings dict for checking unreported status.
            interpolate: Whether interpolation is active.

        Returns:
            Updated field_values with group collapse applied.
        """
        if not interpolate:
            return field_values

        for group in schema.groups:
            # Find unreported members (those where LLM returned None)
            unreported = [m for m in group.members if findings.get(m) is None]

            if len(unreported) == len(group.members):
                # ALL members unreported -- use joint_normal (per D-01)
                first = True
                for member in group.members:
                    if first:
                        field_values[member] = group.joint_normal
                        first = False
                    else:
                        field_values[member] = ""
            elif len(unreported) > 0:
                # Partially unreported -- search for matching partial (per D-02)
                unreported_set = set(unreported)
                matched_partial = None
                for partial in group.partials:
                    if set(partial.members) == unreported_set:
                        matched_partial = partial
                        break

                if matched_partial is not None:
                    first = True
                    for member in unreported:
                        if first:
                            field_values[member] = matched_partial.text
                            first = False
                        else:
                            field_values[member] = ""
                # If no partial match, leave individual normals in place

        return field_values

    def _substitute_technique(self, body: str, technique: dict) -> str:
        """Replace {{technique:key}} placeholders with technique dict values.

        Args:
            body: Template body text.
            technique: Dict with technique values.

        Returns:
            Body with technique placeholders substituted.
        """
        def _replace_technique(match: re.Match) -> str:
            key = match.group(1)
            value = technique.get(key)
            if value is not None:
                return value
            # Default for comparison (per D-29)
            if key == "comparison":
                return "None available."
            return NOT_DOCUMENTED

        return TECHNIQUE_PATTERN.sub(_replace_technique, body)

    def _substitute_measurements(self, body: str, technique: dict) -> str:
        """Replace {{measurement:key}} placeholders with values from technique dict.

        Second pass -- runs after field substitution so measurements within
        interpolated normal text are also resolved.

        Args:
            body: Body text after field substitution.
            technique: Dict containing measurement values.

        Returns:
            Body with measurement placeholders substituted.
        """
        def _replace_measurement(match: re.Match) -> str:
            key = match.group(1)
            value = technique.get(key)
            if value is not None:
                return str(value)
            return NOT_DOCUMENTED

        return MEASUREMENT_PATTERN.sub(_replace_measurement, body)

    def _strip_guidance(self, body: str) -> str:
        """Remove the Guidance section from the body."""
        return GUIDANCE_PATTERN.sub("", body)

    def _handle_impression(
        self,
        body: str,
        schema: TemplateSchema,
        findings: dict,
        technique: dict,
        generate_impression: Callable[[str, str], str] | None,
    ) -> str:
        """Handle the COMMENT/impression section.

        When impression=false, strip entire COMMENT section (per D-22).
        When impression=true with callable, generate and insert (per D-18/D-23).
        When impression=true without callable, insert placeholder (per D-21).

        Args:
            body: Body text after all field substitutions.
            schema: Template schema.
            findings: Original findings dict.
            technique: Technique dict (for clinical_indication).
            generate_impression: Optional callable for impression generation.

        Returns:
            Body with COMMENT section handled.
        """
        if not schema.impression:
            # Strip entire COMMENT section (per D-22)
            body = re.sub(
                r"^## COMMENT\s*\n?.*",
                "",
                body,
                flags=re.MULTILINE | re.DOTALL,
            )
            return body

        # Extract findings text (between FINDINGS header and next ## header)
        findings_match = re.search(
            r"^## FINDINGS\s*\n(.*?)(?=^## |\Z)",
            body,
            re.MULTILINE | re.DOTALL,
        )
        findings_text = findings_match.group(1).strip() if findings_match else ""

        clinical_history = technique.get("clinical_indication", "")

        if generate_impression is not None:
            impression_text = generate_impression(findings_text, clinical_history)
            # Log for medico-legal audit trail (per D-23)
            logger.info(
                "[IMPRESSION] Input findings: %s",
                findings_text[:200] if len(findings_text) > 200 else findings_text,
            )
            logger.info("[IMPRESSION] Generated: %s", impression_text)
        else:
            impression_text = "(impression not generated)"

        # Replace COMMENT section content
        body = re.sub(
            r"(^## COMMENT\s*\n).*",
            rf"\g<1>\n{impression_text}\n",
            body,
            flags=re.MULTILINE | re.DOTALL,
        )

        return body

    def _convert_headers(self, body: str) -> str:
        """Strip ## prefix from section headers, keeping text UPPERCASE (per D-24)."""
        return SECTION_HEADER_PATTERN.sub(r"\1", body)

    def _cleanup_blank_lines(self, body: str) -> str:
        """Collapse 3+ consecutive blank lines to 2 (per D-27)."""
        # First remove lines that are only whitespace (from omitted fields)
        lines = body.split("\n")
        cleaned_lines = []
        for line in lines:
            if line.strip() == "":
                cleaned_lines.append("")
            else:
                cleaned_lines.append(line)
        body = "\n".join(cleaned_lines)

        # Collapse 4+ newlines to 3 (which = 2 blank lines between text)
        return BLANK_LINE_PATTERN.sub("\n\n\n", body)

    def _post_render_validate(self, body: str) -> str:
        """Scan for remaining {{...}} placeholders and log warnings (per D-28)."""
        remaining = PLACEHOLDER_PATTERN.findall(body)
        for p in remaining:
            logger.warning("Unresolved placeholder remaining in output: {{%s}}", p)
        return body

    def _assemble_body(
        self,
        body: str,
        field_values: dict[str, str | None],
        important_fields: list[str] | None,
    ) -> str:
        """Assemble the body with field values. Overridden by subclasses."""
        raise NotImplementedError


# ===== Freeform Renderer =====


class FreeformRenderer(ReportRenderer):
    """Freeform prose-style renderer.

    Substitutes {{field_name}} placeholders directly with finding text.
    Supports important_first reordering within the FINDINGS section.
    """

    def _assemble_body(
        self,
        body: str,
        field_values: dict[str, str | None],
        important_fields: list[str] | None,
    ) -> str:
        """Substitute field placeholders in freeform prose body.

        If important_fields is provided, reorders placeholder lines in the
        FINDINGS section so important fields appear first.
        """
        if important_fields:
            body = self._reorder_important(body, important_fields)

        # Substitute each field placeholder
        for field_name, value in field_values.items():
            placeholder = "{{" + field_name + "}}"
            if value is None or value == "":
                # Remove the entire line containing the placeholder
                body = re.sub(
                    r"^[^\S\n]*" + re.escape(placeholder) + r"[^\S\n]*\n?",
                    "",
                    body,
                    flags=re.MULTILINE,
                )
            else:
                body = body.replace(placeholder, value)

        return body

    def _reorder_important(self, body: str, important_fields: list[str]) -> str:
        """Reorder placeholder lines in FINDINGS so important fields come first.

        Args:
            body: Template body text.
            important_fields: Field names to prioritise.

        Returns:
            Body with FINDINGS section placeholder lines reordered.
        """
        # Find the FINDINGS section
        findings_match = re.search(
            r"(^## FINDINGS\s*\n)(.*?)(?=^## |\Z)",
            body,
            re.MULTILINE | re.DOTALL,
        )
        if not findings_match:
            return body

        header = findings_match.group(1)
        content = findings_match.group(2)

        # Split content into lines
        lines = content.split("\n")

        # Categorise lines by which field placeholder they contain
        important_lines: list[str] = []
        other_lines: list[str] = []
        important_set = set(important_fields)

        for line in lines:
            # Check if line contains a field placeholder
            match = re.search(r"\{\{(\w+)\}\}", line)
            if match and match.group(1) in important_set:
                important_lines.append(line)
            else:
                other_lines.append(line)

        # Reconstruct: important lines first, then others
        new_content = "\n".join(important_lines + other_lines)

        # Replace the original FINDINGS content
        start = findings_match.start(2)
        end = findings_match.end(2)
        body = body[:start] + new_content + body[end:]

        return body


# ===== Structured Renderer =====


class StructuredRenderer(ReportRenderer):
    """Structured table-style renderer.

    Converts markdown table rows to colon-separated plain text lines.
    Routes findings to Key Findings / Other Findings sections based on
    important_fields classification.
    """

    def _assemble_body(
        self,
        body: str,
        field_values: dict[str, str | None],
        important_fields: list[str] | None,
    ) -> str:
        """Convert structured template body to plain text with status labels.

        Replaces the markdown table with colon-separated status lines and
        populates Key/Other Findings sections with detailed finding text.
        """
        schema = self._current_schema

        # Build a lookup for field normal text
        field_normals = {f.name: f.normal for f in schema.fields}

        # Parse table rows
        table_rows = TABLE_ROW_PATTERN.findall(body)

        # Build status lines and collect findings for Key/Other sections
        status_lines: list[str] = []
        key_findings: list[str] = []
        other_findings: list[str] = []
        important_set = set(important_fields) if important_fields else set()

        for label, field_name in table_rows:
            value = field_values.get(field_name)

            if value is None:
                # Omitted field (optional/sex-filtered) -- skip entirely
                continue

            if value == "":
                # Collapsed group member -- skip
                continue

            # Determine status label
            if value == NOT_DOCUMENTED:
                status = NOT_DOCUMENTED
            elif value == field_normals.get(field_name):
                # Interpolated as normal (per D-11)
                status = "Normal"
            else:
                # Has findings -- mark as "See below"
                status = "See below"

            label_clean = label.strip()
            status_lines.append(f"{label_clean}: {status}")

            # Route findings text to Key/Other sections
            if status == "See below":
                entry = f"{label_clean}: {value}"
                if important_set and field_name in important_set:
                    key_findings.append(entry)
                elif important_set:
                    other_findings.append(entry)
                else:
                    # No important_fields specified -- all go to Key (per D-17)
                    key_findings.append(entry)

        # Build the replacement content for FINDINGS section
        status_block = "\n".join(status_lines)

        key_text = "\n\n".join(key_findings) if key_findings else ""
        other_text = "\n\n".join(other_findings) if other_findings else ""

        # Remove the markdown table (header row, separator, data rows)
        body = re.sub(
            r"\|[^\n]*Organ[^\n]*\|\s*\n\|[-|\s]*\|\s*\n(?:\|[^\n]*\|\s*\n)*",
            status_block + "\n\n",
            body,
        )

        # Replace Key Findings section content
        body = re.sub(
            r"(### Key Findings\s*\n)\s*\([^)]*\)",
            r"\g<1>" + key_text if key_text else r"\g<1>",
            body,
        )

        # Replace Other Findings section content
        body = re.sub(
            r"(### Other Findings\s*\n)\s*\([^)]*\)",
            r"\g<1>" + other_text if other_text else r"\g<1>",
            body,
        )

        # Substitute any remaining field placeholders (shouldn't normally be left)
        for field_name, value in field_values.items():
            placeholder = "{{" + field_name + "}}"
            if value is None or value == "":
                body = re.sub(
                    r"^[^\S\n]*" + re.escape(placeholder) + r"[^\S\n]*\n?",
                    "",
                    body,
                    flags=re.MULTILINE,
                )
            else:
                body = body.replace(placeholder, value)

        return body

    def render(
        self,
        template: LoadedTemplate,
        findings: dict,
        technique: dict,
        important_fields: list[str] | None = None,
        rest_normal: bool = False,
        generate_impression: Callable[[str, str], str] | None = None,
    ) -> str:
        """Override render to stash schema for _assemble_body access."""
        self._current_schema = template.schema
        return super().render(
            template, findings, technique,
            important_fields, rest_normal, generate_impression,
        )


# ===== Factory Function =====


def render_report(
    template: LoadedTemplate,
    findings: dict,
    technique: dict,
    important_fields: list[str] | None = None,
    rest_normal: bool = False,
    generate_impression: Callable[[str, str], str] | None = None,
) -> str:
    """Factory function that dispatches to the correct renderer based on template variant.

    Args:
        template: Loaded and validated template.
        findings: Dict mapping field names to finding text.
        technique: Dict with technique values and measurements.
        important_fields: Optional list of important field names.
        rest_normal: If True, overrides interpolate_normal for this call.
        generate_impression: Optional callable for impression generation.

    Returns:
        Formatted plain text report string.
    """
    variant = getattr(template.schema, "variant", "freeform")
    renderer_map: dict[str, type[ReportRenderer]] = {
        "freeform": FreeformRenderer,
        "structured": StructuredRenderer,
    }
    renderer_cls = renderer_map.get(variant, FreeformRenderer)
    renderer = renderer_cls()
    return renderer.render(
        template, findings, technique,
        important_fields, rest_normal, generate_impression,
    )
