"""Template composition engine for combining base templates into composites.

Resolves composable_from references, merges fields with deduplication,
carries forward groups (dropping those with excluded members per D-11),
and produces a single LoadedTemplate ready for the rendering pipeline.
"""

from __future__ import annotations

from .schema import (
    TemplateSchema,
    FieldDefinition,
    FieldGroup,
    validate_body_placeholders,
)
from .loader import LoadedTemplate
from .exceptions import TemplateLoadError, TemplateValidationError


def compose_template(
    composite: LoadedTemplate,
    bases: dict[str, LoadedTemplate],
    resolution_chain: set[str] | None = None,
) -> LoadedTemplate:
    """Compose a composite template from its base templates.

    Takes a raw-parsed composite LoadedTemplate (body placeholder validation
    skipped at load time), a dict of already-loaded base templates keyed by
    relative path, and an optional resolution_chain for circular detection.

    Args:
        composite: The composite template (parsed from frontmatter only).
        bases: Dict mapping relative paths to loaded base templates.
        resolution_chain: Set of file_paths already in the resolution stack
            (for circular detection).

    Returns:
        A fully composed LoadedTemplate with merged fields and groups.

    Raises:
        TemplateValidationError: On circular composition, missing bases,
            invalid exclusions, field collisions, or body placeholder mismatches.
    """
    if resolution_chain is None:
        resolution_chain = set()

    # 1. Circular detection
    if composite.file_path in resolution_chain:
        raise TemplateValidationError(
            [TemplateLoadError(
                composite.file_path,
                f"Circular composition detected: {composite.file_path} "
                f"already in resolution chain {sorted(resolution_chain)}"
            )]
        )
    resolution_chain = resolution_chain | {composite.file_path}

    # 2. Resolve base templates
    if composite.schema.composable_from is None:
        raise TemplateValidationError(
            [TemplateLoadError(
                composite.file_path,
                "compose_template called on non-composite template "
                "(composable_from is None)"
            )]
        )

    resolved_bases: list[tuple[str, LoadedTemplate]] = []
    for ref_path in composite.schema.composable_from:
        if ref_path not in bases:
            raise TemplateValidationError(
                [TemplateLoadError(
                    composite.file_path,
                    f"Base template not found: {ref_path}"
                )]
            )
        base = bases[ref_path]
        # Recursively compose if base is itself a composite
        if base.schema.composable_from is not None:
            base = compose_template(base, bases, resolution_chain)
        resolved_bases.append((ref_path, base))

    # 3. Validate exclusions
    _validate_exclusions(
        composite.schema.exclude_fields,
        resolved_bases,
        composite.file_path,
    )

    # 4. Merge fields
    merged_fields = _merge_fields(
        resolved_bases,
        composite.schema.exclude_fields,
        composite.schema.fields,
        composite.file_path,
    )

    # 5. Merge groups
    merged_field_names = {f.name for f in merged_fields}
    merged_groups = _merge_groups(
        resolved_bases,
        composite.schema.exclude_fields,
        merged_field_names,
        composite.schema.groups,
    )

    # 6. Build composed TemplateSchema
    composed_schema = TemplateSchema(
        study_name=composite.schema.study_name,
        aliases=composite.schema.aliases,
        technique=composite.schema.technique,
        interpolate_normal=composite.schema.interpolate_normal,
        impression=composite.schema.impression,
        important_first=composite.schema.important_first,
        variant=composite.schema.variant,
        fields=merged_fields,
        groups=merged_groups,
        composable_from=None,
        exclude_fields=None,
    )

    # 7. Validate body placeholders against merged fields
    issues = validate_body_placeholders(composed_schema, composite.body)
    if issues:
        raise TemplateValidationError(
            [TemplateLoadError(composite.file_path, issue) for issue in issues]
        )

    # 8. Return composed template
    return LoadedTemplate(
        schema=composed_schema,
        body=composite.body,
        file_path=composite.file_path,
    )


def _validate_exclusions(
    exclude_fields: dict[str, list[str]] | None,
    resolved_bases: list[tuple[str, LoadedTemplate]],
    composite_path: str,
) -> None:
    """Validate that all exclusion references are valid.

    Checks that:
    - Every key in exclude_fields is a path in resolved_bases.
    - Every excluded field name actually exists in its base template.

    Args:
        exclude_fields: Dict mapping base paths to lists of field names to exclude.
        resolved_bases: Ordered list of (path, LoadedTemplate) tuples.
        composite_path: Path of the composite template (for error messages).

    Raises:
        TemplateValidationError: On invalid exclusion references.
    """
    if exclude_fields is None:
        return

    base_paths = {path for path, _ in resolved_bases}
    base_by_path = {path: tmpl for path, tmpl in resolved_bases}

    for ref_path, field_names in exclude_fields.items():
        if ref_path not in base_paths:
            raise TemplateValidationError(
                [TemplateLoadError(
                    composite_path,
                    f"exclude_fields references '{ref_path}' which is not "
                    f"in composable_from"
                )]
            )

        base_field_names = {f.name for f in base_by_path[ref_path].schema.fields}
        for name in field_names:
            if name not in base_field_names:
                raise TemplateValidationError(
                    [TemplateLoadError(
                        composite_path,
                        f"Excluded field '{name}' does not exist in base "
                        f"template '{ref_path}'"
                    )]
                )


def _merge_fields(
    resolved_bases: list[tuple[str, LoadedTemplate]],
    exclude_fields: dict[str, list[str]] | None,
    composite_fields: list[FieldDefinition],
    composite_path: str,
) -> list[FieldDefinition]:
    """Merge fields from bases and composite in order.

    Order: base1 fields, base2 fields (minus exclusions), ..., composite fields.
    Collisions (same field name from different bases after exclusion) are fatal.

    Args:
        resolved_bases: Ordered list of (path, LoadedTemplate) tuples.
        exclude_fields: Dict mapping base paths to excluded field names.
        composite_fields: The composite template's own fields.
        composite_path: Path of the composite template (for error messages).

    Returns:
        Ordered list of merged FieldDefinition objects.

    Raises:
        TemplateValidationError: On field name collisions.
    """
    exclusion_map = exclude_fields or {}
    merged: list[FieldDefinition] = []
    seen_names: set[str] = set()

    # Iterate bases in order
    for ref_path, base in resolved_bases:
        excluded = set(exclusion_map.get(ref_path, []))
        for field in base.schema.fields:
            if field.name in excluded:
                continue
            if field.name in seen_names:
                raise TemplateValidationError(
                    [TemplateLoadError(
                        composite_path,
                        f"Field name collision: '{field.name}' appears in "
                        f"multiple base templates after exclusion"
                    )]
                )
            seen_names.add(field.name)
            merged.append(field)

    # Append composite's own fields
    for field in composite_fields:
        if field.name in seen_names:
            raise TemplateValidationError(
                [TemplateLoadError(
                    composite_path,
                    f"Field name collision: composite field '{field.name}' "
                    f"conflicts with a base template field"
                )]
            )
        seen_names.add(field.name)
        merged.append(field)

    return merged


def _merge_groups(
    resolved_bases: list[tuple[str, LoadedTemplate]],
    exclude_fields: dict[str, list[str]] | None,
    merged_field_names: set[str],
    composite_groups: list[FieldGroup],
) -> list[FieldGroup]:
    """Merge groups from bases, dropping those with excluded members.

    Per D-11: if ANY member of a group is in that base's exclusion set,
    the entire group is dropped. Also verifies remaining members exist
    in the merged field set.

    Args:
        resolved_bases: Ordered list of (path, LoadedTemplate) tuples.
        exclude_fields: Dict mapping base paths to excluded field names.
        merged_field_names: Set of all field names in the merged result.
        composite_groups: The composite template's own groups.

    Returns:
        Ordered list of merged FieldGroup objects.
    """
    exclusion_map = exclude_fields or {}
    merged: list[FieldGroup] = []

    for ref_path, base in resolved_bases:
        excluded = set(exclusion_map.get(ref_path, []))
        for group in base.schema.groups:
            # D-11: drop group if any member is excluded
            if any(member in excluded for member in group.members):
                continue
            # Verify all members exist in merged fields
            if all(member in merged_field_names for member in group.members):
                merged.append(group)

    # Append composite's own groups
    merged.extend(composite_groups)

    return merged
