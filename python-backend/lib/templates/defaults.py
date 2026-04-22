"""Default payload and guidance helpers for templates.

Two derivation utilities consumed by the LLM pipeline prompts:

- ``build_guidance`` returns the concatenated ``## Guidance`` section bodies
  from a template and (for composites) its constituents, for injection into
  extraction/rendering prompts.
- ``build_default_payload`` returns the baseline ``{technique, findings}``
  JSON payload with normal text filled in and ``{{measurement:...}}`` /
  ``{{technique:...}}`` placeholders preserved verbatim, for use as the
  f-string skeleton the caller later substitutes values into.
"""

from __future__ import annotations

import pathlib
import re

from .composer import compose_template
from .exceptions import TemplateLoadError, TemplateValidationError
from .loader import LoadedTemplate, load_template
from .schema import PLACEHOLDER_PATTERN


_GUIDANCE_BODY_PATTERN = re.compile(
    r"^## Guidance\s*\n(.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def build_guidance(
    template: LoadedTemplate,
    templates_dir: str | pathlib.Path,
) -> str:
    """Concatenate guidance-section bodies across a template and its bases.

    For composite templates (``schema.composable_from`` set), loads each
    constituent from disk via ``templates_dir``, recurses for nested
    composites, concatenates their guidance bodies in composition order,
    then appends the composite's own guidance body (if any). Sections are
    joined with ``"\\n\\n"``. The ``## Guidance`` heading itself is stripped;
    only body text is returned.

    Pass the RAW pre-composition template (from ``load_template``). A
    post-composition template (``composable_from`` cleared by
    ``compose_template``) returns only its own guidance because constituent
    info is no longer available.

    Empty guidance sections are filtered silently -- no blank separators
    are emitted.

    Args:
        template: Loaded template (preferably raw pre-composition).
        templates_dir: Root directory to resolve relative
            ``composable_from`` paths.

    Returns:
        Concatenated guidance body text, or empty string if none found.

    Raises:
        TemplateValidationError: On circular ``composable_from`` references.
    """
    return _build_guidance(template, pathlib.Path(templates_dir), set())


def _build_guidance(
    template: LoadedTemplate,
    root: pathlib.Path,
    seen: set[str],
) -> str:
    if template.file_path in seen:
        raise TemplateValidationError(
            [TemplateLoadError(
                template.file_path,
                f"Circular composable_from detected in guidance resolution; "
                f"chain: {sorted(seen)}",
            )]
        )
    seen = seen | {template.file_path}

    parts: list[str] = []
    if template.schema.composable_from is not None:
        for rel_path in template.schema.composable_from:
            base = load_template(root / rel_path)
            sub = _build_guidance(base, root, seen)
            if sub:
                parts.append(sub)

    own = _extract_guidance_body(template.body)
    if own:
        parts.append(own)
    return "\n\n".join(parts)


def _extract_guidance_body(body: str) -> str:
    match = _GUIDANCE_BODY_PATTERN.search(body)
    if not match:
        return ""
    return match.group(1).strip()


def build_default_payload(
    template: LoadedTemplate,
    templates_dir: str | pathlib.Path,
) -> dict[str, dict[str, str]]:
    """Build the default ``{technique, findings}`` JSON payload for a template.

    For composite templates (``schema.composable_from`` set), composes
    internally via ``compose_template`` to get merged fields (respecting
    ``exclude_fields``) in order. Post-composition templates are used as-is.

    ``findings`` entries preserve each field's normal text verbatim, including
    any ``{{measurement:...}}`` or ``{{technique:...}}`` placeholders -- no
    substitution happens here.

    ``technique`` entries collect every unique ``{{measurement:KEY}}`` and
    ``{{technique:KEY}}`` placeholder found in the body, field normals,
    group ``joint_normal`` text, and group partial texts. Each value is the
    placeholder string itself so callers can f-string-format the result
    after resolving values. Deduplicated by key (first occurrence wins).

    Args:
        template: Loaded template (raw or composed).
        templates_dir: Root templates directory; used only when the template
            is a raw composite that needs composition.

    Returns:
        ``{"technique": {...}, "findings": {...}}``.
    """
    if template.schema.composable_from is not None:
        bases = _load_bases_recursive(
            template, pathlib.Path(templates_dir), {}
        )
        effective = compose_template(template, bases)
    else:
        effective = template

    findings = {f.name: f.normal for f in effective.schema.fields}

    technique: dict[str, str] = {}
    sources: list[str] = [effective.body]
    sources.extend(f.normal for f in effective.schema.fields)
    for group in effective.schema.groups:
        sources.append(group.joint_normal)
        sources.extend(p.text for p in group.partials)

    for text in sources:
        for match in PLACEHOLDER_PATTERN.finditer(text):
            token = match.group(1)
            if ":" not in token:
                continue
            ptype, key = token.split(":", 1)
            if ptype not in ("measurement", "technique"):
                continue
            if key in technique:
                continue
            technique[key] = "{{" + token + "}}"

    return {"technique": technique, "findings": findings}


def _load_bases_recursive(
    composite: LoadedTemplate,
    root: pathlib.Path,
    acc: dict[str, LoadedTemplate],
) -> dict[str, LoadedTemplate]:
    """Load all bases referenced transitively by a composite.

    Keys are the relative paths exactly as they appear in ``composable_from``
    so ``compose_template`` can resolve them.
    """
    if composite.schema.composable_from is None:
        return acc
    for rel_path in composite.schema.composable_from:
        if rel_path in acc:
            continue
        base = load_template(root / rel_path)
        acc[rel_path] = base
        if base.schema.composable_from is not None:
            _load_bases_recursive(base, root, acc)
    return acc
