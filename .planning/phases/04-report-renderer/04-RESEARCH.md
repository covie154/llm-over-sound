# Phase 4: Report Renderer - Research

**Researched:** 2026-03-29
**Domain:** Python template rendering, string interpolation, radiology report formatting
**Confidence:** HIGH

## Summary

Phase 4 implements the report renderer -- the module that takes a `LoadedTemplate` (from Phase 2) and an extracted findings dict (from the LLM pipeline) and produces a correctly formatted plain text radiology report. The renderer must handle interpolation flags, impression generation, field ordering, group collapse logic, measurement two-pass substitution, guidance stripping, and output cleanup.

The existing codebase provides a solid foundation: `TemplateSchema` already defines `interpolate_normal`, `impression`, and `important_first` flags; `FieldDefinition` has `name`, `normal`, `sex`, `optional` fields; `FieldGroup` has `members`, `joint_normal`, and `partials`. The `PLACEHOLDER_PATTERN` regex and `NOT_DOCUMENTED` constant are ready to use. The renderer adds a new file (`renderer.py`) in the existing `python-backend/lib/templates/` package, a `variant` field to `TemplateSchema`, and comprehensive tests.

**Primary recommendation:** Build a base `ReportRenderer` class with shared logic (placeholder substitution, group handling, interpolation, guidance stripping, blank line cleanup, technique substitution, measurement two-pass, post-render validation), with `FreeformRenderer` and `StructuredRenderer` subclasses that override body assembly. A `render_report()` factory function dispatches based on the template's `variant` field.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** When `interpolate_normal=true` and ALL group members are unreported, use the group's `joint_normal` text (not individual field normals)
- **D-02:** When `interpolate_normal=true` and a group is partially abnormal, use authored partial text for the normal subset. If no matching partial exists, fall back to individual field normals
- **D-03:** When `interpolate_normal=false` (default), groups do NOT collapse -- every unreported field shows `__NOT_DOCUMENTED__` individually. Groups only activate when `interpolate_normal=true`
- **D-04:** Per-request `rest_normal=True` override sets `interpolate_normal=true` for that single render call only. It ONLY affects fields where the LLM returned `None` (unreported). If the LLM explicitly set a field value, that value is preserved regardless of `rest_normal`
- **D-05:** Base `ReportRenderer` class with shared logic: placeholder substitution, group handling, interpolation, measurement two-pass, technique substitution, guidance stripping, blank line cleanup
- **D-06:** `FreeformRenderer` subclass: overrides body assembly -- straightforward placeholder substitution in prose
- **D-07:** `StructuredRenderer` subclass: overrides body assembly -- renders table with short status labels, populates Key/Other Findings sections
- **D-08:** A top-level `render_report()` factory function inspects the template's `variant` field and dispatches to the correct subclass
- **D-09:** New `variant` field added to `TemplateSchema`: `Literal['freeform', 'structured']`, default `'freeform'`. All 4 existing templates updated with explicit variant values
- **D-10:** Table cells show short status labels: `Normal`, `Abnormal` / `See below`, `__NOT_DOCUMENTED__`
- **D-11:** When `interpolate_normal=true` and field unreported, table shows `Normal`. No detailed text in Key/Other sections
- **D-12:** LLM classifies findings as key/other at extraction time (stage 3). Renderer receives pre-classified text blocks
- **D-13:** Rendered in plain text as colon-separated lines: `Liver: Normal`
- **D-14:** Both FreeformRenderer and StructuredRenderer support `important_first`
- **D-15:** FreeformRenderer: reorders field placeholders so important fields appear first
- **D-16:** StructuredRenderer: routes important findings to Key Findings section, others to Other Findings
- **D-17:** `important_fields: list[str]` is optional parameter -- when None/empty, template order preserved (freeform) or all go to Key Findings (structured)
- **D-18:** Renderer triggers impression generation by calling an injected `generate_impression` callable
- **D-19:** Callable signature: `generate_impression(findings_text: str, clinical_history: str) -> str`
- **D-20:** Callable is sync-only in Phase 4
- **D-21:** When `impression=true` but no callable provided, render `(impression not generated)` placeholder
- **D-22:** When `impression=false`, entire COMMENT section (header + content) stripped
- **D-23:** Renderer logs impression input/output for audit trail
- **D-24:** Output is plain text. Section headers render as UPPERCASE on own line (strip `## ` prefix)
- **D-25:** Structured table as colon-separated plain text lines
- **D-26:** Guidance section stripped from output
- **D-27:** Blank line cleanup: collapse 3+ consecutive blank lines to 2
- **D-28:** Post-render validation: scan for remaining `{{...}}` placeholders, log warning
- **D-29:** Comparison via technique dict `{{technique:comparison}}`, default "None available."
- **D-30:** Stateless `render()` method with all parameters
- **D-31:** Accepts `LoadedTemplate` directly
- **D-32:** Returns plain string, warnings via logger
- **D-33:** Unit tests with inline expected strings, integration tests with snapshot files
- **D-34:** No impression callable in unit tests
- **D-35:** Both minimal fixtures and real clinical templates used

### Claude's Discretion
- Internal method structure within base and subclass renderers
- Exact blank line collapsing algorithm implementation
- How the factory function dispatches (dict lookup, if/elif, etc.)
- Test fixture template content and findings dict structure
- Logger message formatting for audit trail entries
- How FreeformRenderer reorders fields for important_first (string manipulation vs template re-parsing)

### Deferred Ideas (OUT OF SCOPE)
- Configurable output format (markdown vs plain text) -- v2
- LLM-generated partial normal text for groups
- Post-render LLM restructure for important_first
- Async impression callable -- Phase 6 if needed
- Structured renderer column alignment
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TMPL-04 | `interpolate_normal` flag controls whether unreported fields get normal text or `__NOT_DOCUMENTED__` | Renderer base class implements interpolation logic with group-aware handling (D-01 through D-04). `TemplateSchema` already has the flag. Group collapse uses `FieldGroup.joint_normal` and `GroupPartial` models |
| TMPL-05 | `impression` flag controls whether COMMENT/impression section is generated | Renderer checks flag: when true, calls injected callable or renders placeholder; when false, strips COMMENT section entirely (D-18 through D-23) |
| TMPL-06 | `important_first` flag moves clinically important findings to top of findings section | Both subclasses support via `important_fields` parameter. Freeform reorders placeholders; structured routes to Key/Other sections (D-14 through D-17) |
| TMPL-10 | Unreported fields not interpolated must output `__NOT_DOCUMENTED__` | Base class substitution: when `interpolate_normal=false`, all unreported fields get `NOT_DOCUMENTED` constant from `schema.py`. Already defined as `"__NOT_DOCUMENTED__"` |
| FLDS-03 | Per-request "rest normal" override sets `interpolate_normal=true` for that request only | `rest_normal: bool = False` parameter on `render()`. When true, overrides interpolation for fields where LLM returned None (D-04) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.5 | Runtime | Already installed on dev machine |
| Pydantic | 2.11.7 | Schema validation, model definitions | Already used for TemplateSchema, FieldDefinition, etc. |
| pytest | 8.3.4 | Test framework | Already used for 68 existing tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-frontmatter | installed | YAML+markdown parsing | Template loading (already used by loader.py) |
| re (stdlib) | -- | Regex for placeholder matching, guidance stripping | PLACEHOLDER_PATTERN already defined in schema.py |
| logging (stdlib) | -- | Audit trail logging | Module-level logger from lib.config |
| typing (stdlib) | -- | Type hints including Literal, Callable, Optional | render() signature, variant field |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| String replace/regex | Jinja2 | Overkill -- templates are simple placeholder substitution, Jinja adds dependency and complexity |
| Manual string building | Template strings (stdlib) | stdlib Template uses `$var` syntax, incompatible with existing `{{var}}` convention |

No new packages needed. Phase 4 uses only existing dependencies plus stdlib.

## Architecture Patterns

### Recommended Project Structure
```
python-backend/lib/templates/
    __init__.py          # Add renderer exports
    schema.py            # Add variant field to TemplateSchema
    loader.py            # No changes needed
    registry.py          # No changes needed
    exceptions.py        # No changes needed
    renderer.py          # NEW: ReportRenderer, FreeformRenderer, StructuredRenderer, render_report()

python-backend/tests/
    test_renderer.py               # NEW: Unit tests with inline expectations
    test_renderer_integration.py   # NEW: Integration tests with real templates
    fixtures/
        renderer/                  # NEW: Fixture templates for renderer tests
```

### Pattern 1: Base + Subclass Renderer Architecture
**What:** Abstract base `ReportRenderer` with shared logic, concrete `FreeformRenderer` and `StructuredRenderer` subclasses
**When to use:** Always -- this is the locked decision (D-05 through D-08)

```python
from typing import Callable, Literal
import logging
import re

from .schema import (
    TemplateSchema,
    FieldDefinition,
    FieldGroup,
    NOT_DOCUMENTED,
    PLACEHOLDER_PATTERN,
)
from .loader import LoadedTemplate

logger = logging.getLogger(__name__)


class ReportRenderer:
    """Base renderer with shared logic."""

    def render(
        self,
        template: LoadedTemplate,
        findings: dict,
        technique: dict,
        important_fields: list[str] | None = None,
        rest_normal: bool = False,
        generate_impression: Callable[[str, str], str] | None = None,
    ) -> str:
        # Determine effective interpolation
        # Build field value map (findings + interpolation + groups)
        # Call subclass body assembly
        # Handle technique substitution
        # Handle measurement two-pass
        # Strip guidance section
        # Handle impression/COMMENT section
        # Strip markdown section headers to plain text
        # Blank line cleanup
        # Post-render validation
        ...

    def _resolve_field_values(
        self,
        schema: TemplateSchema,
        findings: dict,
        interpolate: bool,
    ) -> dict[str, str]:
        """Map each field to its rendered value."""
        ...

    def _resolve_groups(
        self,
        schema: TemplateSchema,
        field_values: dict[str, str],
        findings: dict,
        interpolate: bool,
    ) -> dict[str, str]:
        """Apply group collapse logic when interpolation is on."""
        ...

    def _assemble_body(
        self,
        body: str,
        field_values: dict[str, str],
        important_fields: list[str] | None,
    ) -> str:
        """Override in subclasses for variant-specific body assembly."""
        raise NotImplementedError


class FreeformRenderer(ReportRenderer):
    """Prose-style report body -- placeholder substitution in template text."""

    def _assemble_body(self, body, field_values, important_fields):
        # If important_fields: reorder placeholder lines
        # Substitute {{field_name}} with values
        ...


class StructuredRenderer(ReportRenderer):
    """Table-style report body -- colon-separated status lines + Key/Other sections."""

    def _assemble_body(self, body, field_values, important_fields):
        # Convert markdown table to colon-separated lines with status labels
        # Route findings to Key/Other sections based on important_fields
        ...


def render_report(
    template: LoadedTemplate,
    findings: dict,
    technique: dict,
    important_fields: list[str] | None = None,
    rest_normal: bool = False,
    generate_impression: Callable[[str, str], str] | None = None,
) -> str:
    """Factory function -- dispatches to correct renderer based on template variant."""
    variant = getattr(template.schema, 'variant', 'freeform')
    renderer_map = {
        'freeform': FreeformRenderer,
        'structured': StructuredRenderer,
    }
    renderer = renderer_map[variant]()
    return renderer.render(
        template, findings, technique,
        important_fields, rest_normal, generate_impression,
    )
```

### Pattern 2: Field Value Resolution Pipeline
**What:** Sequential resolution: raw findings -> interpolation -> group collapse -> final values
**When to use:** Every render call

The resolution order matters:
1. For each field, check if findings dict has a non-None value. If yes, use it.
2. If None and `interpolate_normal` is true (or `rest_normal` override), use the field's `normal` text.
3. If None and interpolation is off, use `NOT_DOCUMENTED`.
4. After individual resolution, apply group logic: if all group members resolved to normal text and interpolation is on, replace individual normals with `joint_normal`. If partially abnormal, find matching partial or fall back to individual normals.
5. Optional fields with no findings and no interpolation: omit entirely (blank line, cleaned up later).
6. Sex-filtered fields not matching patient sex: omit entirely.

### Pattern 3: Two-Pass Measurement Substitution
**What:** First pass substitutes field/technique placeholders. Second pass substitutes `{{measurement:name}}` within the interpolated normal text.
**When to use:** Templates like US HBS where normal text contains measurement placeholders (e.g., `"measuring {{measurement:liver_span_cm}} cm"`)

```python
# Pass 1: substitute {{field_name}} and {{technique:name}}
body = substitute_fields(body, field_values)
body = substitute_technique(body, technique)

# Pass 2: substitute {{measurement:name}} in the now-interpolated text
body = substitute_measurements(body, technique)
```

Measurements come from the technique dict (or a measurements sub-dict). If a measurement placeholder has no value, it renders as `__NOT_DOCUMENTED__`.

### Pattern 4: Guidance Section Stripping
**What:** Remove everything from `## Guidance` to the next `## ` header (or end of document)
**When to use:** Every render call -- guidance is LLM-only context, never in output

```python
GUIDANCE_PATTERN = re.compile(
    r"^## Guidance\s*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
```

### Pattern 5: Section Header Conversion
**What:** Convert `## SECTION_NAME` to plain text `SECTION_NAME` (strip `## ` prefix)
**When to use:** Every render call -- output is plain text, not markdown

```python
# After all substitutions and stripping
body = re.sub(r"^## (.+)$", r"\1", body, flags=re.MULTILINE)
```

### Anti-Patterns to Avoid
- **Mutating template state:** Renderer must be stateless. Do not modify `LoadedTemplate` or `TemplateSchema` during rendering. Each `render()` call is self-contained (D-30).
- **Fabricating findings:** Never generate normal text when `interpolate_normal` is false. Use `NOT_DOCUMENTED` or the field's authored normal text only.
- **Interleaving group and non-group output:** When a group collapses to joint_normal, the individual field placeholders in the body should all be replaced -- the first member's placeholder gets the joint text, remaining members' placeholders become empty strings (cleaned up by blank line collapse).
- **Rendering measurement values in status labels:** Structured variant table shows `Normal`/`Abnormal`/`__NOT_DOCUMENTED__` -- never full normal text in the table cells.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Placeholder regex | Custom tokenizer | `PLACEHOLDER_PATTERN` from schema.py | Already tested, handles all `{{...}}` variants including typed namespaces |
| YAML parsing | Custom frontmatter parser | `python-frontmatter` + Pydantic | Already validated in Phase 1-2 |
| Field validation | Manual dict checking | Pydantic models | `FieldDefinition`, `FieldGroup`, `GroupPartial` already handle validation |
| NOT_DOCUMENTED constant | Inline string | `NOT_DOCUMENTED` from schema.py | Single source of truth, used across codebase |

**Key insight:** The schema layer already provides all the data structures and validation. The renderer's job is pure string manipulation using the validated models.

## Common Pitfalls

### Pitfall 1: Group Collapse Ordering in Body
**What goes wrong:** When a group collapses to joint_normal, you need to put the text at the right position and blank out the other members' placeholders. Getting the position wrong produces text in the wrong order or duplicated text.
**Why it happens:** Group members may not be adjacent in the template body (though they typically are in craniocaudal order).
**How to avoid:** Replace the first group member's placeholder with the joint text, replace all other member placeholders with empty string. The blank line cleanup pass handles the resulting gaps.
**Warning signs:** Joint normal text appearing in an unexpected position, or appearing multiple times.

### Pitfall 2: Rest-Normal vs Explicit Findings
**What goes wrong:** `rest_normal=True` accidentally overwriting LLM-extracted findings with normal text.
**Why it happens:** Not checking whether the finding was explicitly set (non-None string) vs unreported (None).
**How to avoid:** `rest_normal` only affects fields where `findings.get(field_name) is None`. If the LLM explicitly set a value (even an empty string), that value is preserved.
**Warning signs:** Abnormal findings being replaced by normal text when rest_normal is true.

### Pitfall 3: Measurement Placeholders in Normal Text
**What goes wrong:** After interpolating normal text that contains `{{measurement:name}}`, the measurement placeholders are not resolved because the first substitution pass already ran.
**Why it happens:** Normal text like `"measuring {{measurement:liver_span_cm}} cm"` gets inserted during field substitution, but measurement substitution needs a second pass.
**How to avoid:** Two-pass approach: field substitution first, then measurement substitution on the full body.
**Warning signs:** Output containing literal `{{measurement:...}}` strings.

### Pitfall 4: Guidance Section with Variable Length
**What goes wrong:** Guidance stripping regex doesn't match when the guidance section has unusual content or is the last section before COMMENT.
**Why it happens:** Regex anchoring issues with end-of-string vs next-header boundary.
**How to avoid:** Use `re.DOTALL` and match until next `## ` header or end of string. Test with guidance at various positions.
**Warning signs:** Guidance text appearing in rendered output.

### Pitfall 5: Optional Fields Creating Blank Lines
**What goes wrong:** When an optional field has no findings and interpolation is off, the placeholder is removed but leaves orphan blank lines that create visual gaps.
**Why it happens:** Each field placeholder is on its own line(s). Removing the content leaves empty lines.
**How to avoid:** The blank line cleanup (collapse 3+ to 2) handles most cases. But for fields that are completely omitted (optional with no data, sex-filtered out), the placeholder line itself should be removed entirely (not just blanked).
**Warning signs:** Large gaps in the output where optional/sex-filtered fields were.

### Pitfall 6: Structured Variant Body Parsing
**What goes wrong:** The structured template body contains a markdown table that must be converted to plain text colon-separated lines. Naive regex may break on edge cases.
**Why it happens:** Markdown table syntax (`| Cell | Cell |`) needs parsing to extract field name and placeholder.
**How to avoid:** The structured template has a predictable format -- parse table rows with a known regex. The table header and separator rows (`|---|---|`) are stripped. Each data row becomes `Label: Status`.
**Warning signs:** Table markup appearing in plain text output.

## Code Examples

### Field Value Resolution
```python
# Source: Derived from D-01 through D-04, schema.py constants
def _resolve_field_value(
    field: FieldDefinition,
    finding: str | None,
    interpolate: bool,
) -> str | None:
    """Resolve a single field's rendered value.

    Returns None for fields that should be omitted entirely
    (optional with no data and no interpolation, or sex-filtered out).
    """
    if finding is not None:
        # LLM provided an explicit value -- always use it
        return finding

    if interpolate:
        # Unreported + interpolation on -> use normal text
        return field.normal

    if field.optional:
        # Unreported + interpolation off + optional -> omit
        return None

    # Unreported + interpolation off + required -> NOT_DOCUMENTED
    return NOT_DOCUMENTED
```

### Group Collapse Logic
```python
# Source: Derived from D-01, D-02, D-03, schema.py FieldGroup/GroupPartial
def _resolve_group(
    group: FieldGroup,
    field_values: dict[str, str | None],
    findings: dict,
    interpolate: bool,
) -> dict[str, str | None]:
    """Apply group collapse when all/some members are normal.

    Only activates when interpolate=True. When False, individual
    field values are preserved as-is (D-03).
    """
    if not interpolate:
        return field_values

    # Determine which members are unreported (None in findings)
    unreported = [m for m in group.members if findings.get(m) is None]
    reported = [m for m in group.members if findings.get(m) is not None]

    if len(unreported) == len(group.members):
        # ALL unreported -> joint_normal on first member, blank others
        field_values[group.members[0]] = group.joint_normal
        for member in group.members[1:]:
            field_values[member] = ""
    elif unreported:
        # Partially unreported -> find matching partial
        unreported_set = set(unreported)
        partial_text = None
        for partial in group.partials:
            if set(partial.members) == unreported_set:
                partial_text = partial.text
                break
        if partial_text:
            field_values[unreported[0]] = partial_text
            for member in unreported[1:]:
                field_values[member] = ""
        # else: fall back to individual normals (already set)

    return field_values
```

### Structured Table Conversion
```python
# Source: Derived from D-10, D-13, D-25
def _convert_table_to_plain(
    table_lines: list[str],
    field_values: dict[str, str],
    findings: dict,
    interpolate: bool,
) -> list[str]:
    """Convert markdown table rows to colon-separated plain text.

    Each row becomes: `Label: Status`
    Status is: Normal, See below, or __NOT_DOCUMENTED__
    """
    result = []
    for line in table_lines:
        # Parse: | Label | {{field_name}} |
        match = re.match(r"\|\s*(.+?)\s*\|\s*\{\{(\w+)\}\}\s*\|", line)
        if not match:
            continue
        label = match.group(1)
        field_name = match.group(2)

        finding = findings.get(field_name)
        if finding is not None:
            status = "See below"
        elif interpolate:
            status = "Normal"
        else:
            status = NOT_DOCUMENTED

        result.append(f"{label}: {status}")
    return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Jinja2 for medical templates | Simple placeholder substitution | Project design decision | Avoids Jinja dependency, keeps templates readable by radiologists |
| Markdown output | Plain text output | Phase 4 decision (D-24) | Simpler for ggwave transmission and AHK frontend display |
| Interactive report building | Single-pass render + review | Project design decision | Matches audio-only transport constraint |

## Open Questions

1. **Sex filtering mechanism**
   - What we know: Sex-dependent fields have a `sex` tag ("male"/"female") per FieldDefinition. The renderer must omit fields not matching patient sex.
   - What's unclear: How does the renderer receive patient sex? Not in the `render()` signature per D-30. The CONTEXT.md says "sex filtering upstream" (per memory file).
   - Recommendation: Patient sex is likely resolved at extraction time (stage 3) -- the LLM only extracts findings for relevant fields. The renderer receives `None` for sex-filtered fields and omits them as optional/unreported. Planner should confirm this assumption or add a `patient_sex` parameter.

2. **Structured variant: Key/Other Findings section content**
   - What we know: D-12 says LLM classifies findings as key/other at extraction time. Renderer receives pre-classified text blocks.
   - What's unclear: The exact format of the pre-classified data. Is it `findings["__key_findings__"]` and `findings["__other_findings__"]` text blocks? Or per-field classification?
   - Recommendation: Since the LLM classifies at extraction, the findings dict likely contains two special keys for pre-rendered Key and Other Findings text blocks. The `important_fields` parameter provides the field-level classification list. Planner should define the interface contract.

3. **Comparison section default text**
   - What we know: D-29 says comparison defaults to "None available." when blank/absent.
   - What's unclear: The template body already has literal `None available.` under `## COMPARISON`. Does the technique dict override this, or is the body text preserved?
   - Recommendation: If `technique.get("comparison")` is provided, substitute it via `{{technique:comparison}}` placeholder. If the template body has no comparison placeholder (just literal text), the body text is preserved as-is. For templates with `{{technique:comparison}}`, absent value defaults to "None available."

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | python-backend/ (implicit, tests/ directory convention) |
| Quick run command | `python -m pytest tests/test_renderer.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TMPL-04 | interpolate_normal=false -> __NOT_DOCUMENTED__; =true -> normal text | unit | `python -m pytest tests/test_renderer.py -k "interpolat" -x` | Wave 0 |
| TMPL-04 | Group collapse with interpolate_normal | unit | `python -m pytest tests/test_renderer.py -k "group" -x` | Wave 0 |
| TMPL-05 | impression=true -> COMMENT section present; =false -> stripped | unit | `python -m pytest tests/test_renderer.py -k "impression" -x` | Wave 0 |
| TMPL-06 | important_first=true -> important fields first | unit | `python -m pytest tests/test_renderer.py -k "important" -x` | Wave 0 |
| TMPL-10 | Unreported fields show __NOT_DOCUMENTED__ | unit | `python -m pytest tests/test_renderer.py -k "not_documented" -x` | Wave 0 |
| FLDS-03 | rest_normal=True overrides interpolation for unreported only | unit | `python -m pytest tests/test_renderer.py -k "rest_normal" -x` | Wave 0 |
| -- | Structured variant table renders colon-separated lines | unit | `python -m pytest tests/test_renderer.py -k "structured" -x` | Wave 0 |
| -- | Guidance section stripped from output | unit | `python -m pytest tests/test_renderer.py -k "guidance" -x` | Wave 0 |
| -- | Blank line cleanup collapses 3+ to 2 | unit | `python -m pytest tests/test_renderer.py -k "blank_line" -x` | Wave 0 |
| -- | Post-render validation warns on remaining placeholders | unit | `python -m pytest tests/test_renderer.py -k "post_render" -x` | Wave 0 |
| -- | Integration with real CT AP template | integration | `python -m pytest tests/test_renderer_integration.py -x` | Wave 0 |
| -- | Integration with real US HBS template (measurements) | integration | `python -m pytest tests/test_renderer_integration.py -k "us_hbs" -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_renderer.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_renderer.py` -- unit tests for all renderer behaviors
- [ ] `tests/test_renderer_integration.py` -- integration tests with real templates
- [ ] `tests/fixtures/renderer/` -- minimal fixture templates for unit tests (freeform and structured variants)

## Project Constraints (from CLAUDE.md)

- Python 3.9+ with type hints on all function signatures
- Pydantic `ConfigDict(extra="forbid")` for strict validation
- Logging via module-level `logger` from `lib.config` (not `print()`)
- snake_case for functions/variables, PascalCase for classes, ALL_CAPS for constants
- The LLM must never fabricate findings -- `NOT_DOCUMENTED` for unreported fields
- All logging to file for audit trail and medico-legal traceability
- Module exports via `__init__.py` with explicit `__all__`
- Docstrings for modules, classes, and public functions
- 4-space indentation
- f-strings preferred for string formatting

## Sources

### Primary (HIGH confidence)
- `python-backend/lib/templates/schema.py` -- TemplateSchema, FieldDefinition, FieldGroup, GroupPartial, PLACEHOLDER_PATTERN, NOT_DOCUMENTED
- `python-backend/lib/templates/loader.py` -- LoadedTemplate dataclass
- `python-backend/rpt_templates/ct/ct_ap.rpt.md` -- Freeform template body format (18 fields, 2 groups)
- `python-backend/rpt_templates/ct/ct_ap_structured.rpt.md` -- Structured template body format (markdown table + Key/Other sections)
- `python-backend/rpt_templates/us/us_hbs.rpt.md` -- Measurement placeholder template
- `.planning/phases/04-report-renderer/04-CONTEXT.md` -- All 35 locked decisions
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` -- Placeholder syntax D-01-D-04, body structure D-22-D-25

### Secondary (MEDIUM confidence)
- Memory files `project_phase4_renderer_decisions.md` and `project_template_variants.md` -- design context

### Tertiary (LOW confidence)
- None -- all findings derived from codebase inspection and locked decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- all decisions locked in CONTEXT.md with 35 explicit decisions
- Pitfalls: HIGH -- derived from template body inspection and group logic analysis

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable -- no external dependency changes expected)
