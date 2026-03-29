# Phase 4: Report Renderer - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Given a loaded template and an extracted findings dict, the renderer produces a correctly formatted **plain text** report respecting interpolation flags, impression generation, field ordering, group logic, and output cleanup. This phase delivers the renderer module with base + subclass architecture (FreeformRenderer, StructuredRenderer), a factory dispatch function, and comprehensive tests. No LLM integration (impression callable is injected), no pipeline wiring (Phase 6), no composite template support (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Interpolation & Rest-Normal
- **D-01:** When `interpolate_normal=true` and ALL group members are unreported, use the group's `joint_normal` text (not individual field normals)
- **D-02:** When `interpolate_normal=true` and a group is partially abnormal, use authored partial text for the normal subset. If no matching partial exists, fall back to individual field normals
- **D-03:** When `interpolate_normal=false` (default), groups do NOT collapse — every unreported field shows `__NOT_DOCUMENTED__` individually. Groups only activate when `interpolate_normal=true`
- **D-04:** Per-request `rest_normal=True` override sets `interpolate_normal=true` for that single render call only. It ONLY affects fields where the LLM returned `None` (unreported). If the LLM explicitly set a field value, that value is preserved regardless of `rest_normal`

### Renderer Architecture
- **D-05:** Base `ReportRenderer` class with shared logic: placeholder substitution, group handling, interpolation, measurement two-pass, technique substitution, guidance stripping, blank line cleanup
- **D-06:** `FreeformRenderer` subclass: overrides body assembly — straightforward placeholder substitution in prose
- **D-07:** `StructuredRenderer` subclass: overrides body assembly — renders table with short status labels, populates Key/Other Findings sections
- **D-08:** A top-level `render_report()` factory function inspects the template's `variant` field and dispatches to the correct subclass. Caller doesn't need to know about subclasses
- **D-09:** New `variant` field added to `TemplateSchema`: `Literal['freeform', 'structured']`, default `'freeform'`. Added as part of Phase 4 plan 01 (not a separate pre-phase task). All 4 existing templates updated with explicit variant values

### Structured Variant
- **D-10:** Table cells show short status labels: `Normal` (when interpolated), `Abnormal` / `See below` (when findings exist), `__NOT_DOCUMENTED__` (when unreported and not interpolated)
- **D-11:** When `interpolate_normal=true` and a field is unreported, table cell shows `Normal`. Detailed normal text does NOT appear in Key/Other Findings
- **D-12:** LLM classifies findings as key/other at extraction time (stage 3). Renderer receives pre-classified text blocks for Key Findings and Other Findings sections
- **D-13:** Rendered in plain text as colon-separated lines: `Liver: Normal`, one field per line

### Important-First
- **D-14:** Both FreeformRenderer and StructuredRenderer support `important_first`
- **D-15:** FreeformRenderer: reorders field placeholders so important fields appear first in the prose output, remaining fields follow template order
- **D-16:** StructuredRenderer: routes important findings to Key Findings section, others to Other Findings section
- **D-17:** `important_fields: list[str]` is an optional parameter — when None or empty, template order is preserved (freeform) or all findings go to Key Findings (structured)

### Impression Generation
- **D-18:** Renderer triggers impression generation (stage 5) by calling an injected `generate_impression` callable. This is NOT a separate pipeline step — the renderer orchestrates it
- **D-19:** Callable signature: `generate_impression(findings_text: str, clinical_history: str) -> str`. Receives the rendered FINDINGS section text plus clinical history from the technique dict
- **D-20:** Callable is sync-only in Phase 4. Async can be added in Phase 6 if needed
- **D-21:** When `impression=true` but no callable is provided (e.g. unit tests), the COMMENT section is rendered with placeholder text `(impression not generated)` — no error raised
- **D-22:** When `impression=false`, the entire COMMENT section (header + content) is stripped from output
- **D-23:** Renderer logs the impression generation input/output for the medico-legal audit trail

### Output Format
- **D-24:** Output is **plain text**, not markdown. Section headers (## FINDINGS) render as UPPERCASE text on their own line (strip `## ` prefix). Markdown output format deferred to v2
- **D-25:** Structured variant table renders as colon-separated plain text lines (per D-13)
- **D-26:** Guidance section stripped: remove everything from `## Guidance` to the next H2 header (or end of body). Handles guidance of any length
- **D-27:** Blank line cleanup: after substitution, collapse runs of 3+ consecutive blank lines to 2. Preserves paragraph breaks while removing gaps from omitted optional/sex-filtered fields
- **D-28:** Post-render validation: scan for remaining `{{...}}` placeholders, log a warning for each but still return the output

### Comparison Section
- **D-29:** Comparison handled via technique dict as `{{technique:comparison}}`. Defaults to `None available.` when blank/absent in the technique dict

### Renderer API
- **D-30:** All parameters in `render()` — stateless, each call self-contained: `render(template: LoadedTemplate, findings: dict, technique: dict, important_fields: list[str] | None = None, rest_normal: bool = False, generate_impression: Callable | None = None) -> str`
- **D-31:** Accepts `LoadedTemplate` directly (the dataclass from the loader)
- **D-32:** Returns a plain string. All warnings/metadata logged via the module logger, not returned

### Testing Strategy
- **D-33:** Unit tests use inline expected strings with minimal fixture templates (controlled, predictable). Integration tests use snapshot files with real clinical templates (CT AP, US HBS)
- **D-34:** No impression callable in unit tests — set `impression=false` or pass `None`. Impression integration tested separately
- **D-35:** Both minimal fixture templates and real clinical templates used in the test suite

### Claude's Discretion
- Internal method structure within base and subclass renderers
- Exact blank line collapsing algorithm implementation
- How the factory function dispatches (dict lookup, if/elif, etc.)
- Test fixture template content and findings dict structure
- Logger message formatting for audit trail entries
- How FreeformRenderer reorders fields for important_first (string manipulation vs template re-parsing)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Artifacts (Schema & Placeholder Decisions)
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` -- Placeholder syntax D-01-D-04 (`{{field_name}}`, `{{measurement:name}}`, `{{technique:name}}`), field groups D-05-D-12, body structure D-22-D-25, validation D-26-D-28, `__NOT_DOCUMENTED__` D-29

### Phase 2 Artifacts (Registry & Loader)
- `.planning/phases/02-template-loader-registry/02-CONTEXT.md` -- LoadedTemplate dataclass D-10, registry API D-09-D-11, alias conventions D-13-D-14

### Phase 3 Artifacts (Template Content)
- `.planning/phases/03-base-template-authoring/03-CONTEXT.md` -- Clinical field inventories D-01-D-14, normal text style D-15-D-18, structured variant layout D-19-D-26, measurement placeholders D-27-D-31, optional field flag D-38

### Existing Code
- `python-backend/lib/templates/schema.py` -- TemplateSchema, FieldDefinition, FieldGroup, GroupPartial models. Variant field to be added here
- `python-backend/lib/templates/loader.py` -- LoadedTemplate dataclass (schema + body + file_path). Renderer accepts this directly
- `python-backend/lib/templates/registry.py` -- TemplateRegistry for template lookup
- `python-backend/lib/templates/exceptions.py` -- Template exception classes
- `python-backend/lib/templates/__init__.py` -- Public API exports (renderer exports to be added)

### Template Files
- `python-backend/rpt_templates/ct/ct_ap.rpt.md` -- Freeform CT AP template (18 fields, 2 groups, sex-dependent pelvis)
- `python-backend/rpt_templates/ct/ct_ap_structured.rpt.md` -- Structured CT AP template (table + Key/Other Findings sections)
- `python-backend/rpt_templates/ct/ct_thorax.rpt.md` -- Freeform CT thorax template
- `python-backend/rpt_templates/us/us_hbs.rpt.md` -- US HBS template with measurement placeholders

### Project Documentation
- `CLAUDE.md` -- Report structure (5 sections), pipeline stages, key constraints, audio channel specs
- `python-backend/CLAUDE.md` -- Backend pipeline details, safety requirements, 4-stage pipeline description

### Requirements
- `.planning/REQUIREMENTS.md` -- Phase 4 requirements: TMPL-04, TMPL-05, TMPL-06, TMPL-10, FLDS-03

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LoadedTemplate` dataclass in `loader.py` -- the renderer's primary input (schema + body + file_path)
- `TemplateSchema` with `interpolate_normal`, `impression`, `important_first` flags already defined
- `FieldDefinition` with `name`, `normal`, `sex`, `optional` fields
- `FieldGroup` with `members`, `joint_normal`, `partials` for group collapse logic
- `GroupPartial` with `members` + `text` for partial normal text lookups
- `PLACEHOLDER_PATTERN` regex for `{{...}}` matching
- `NOT_DOCUMENTED` constant for the `__NOT_DOCUMENTED__` sentinel string
- `validate_body_placeholders()` for cross-validation (used by loader, renderer can reuse for post-render checks)

### Established Patterns
- Pydantic `ConfigDict(extra="forbid")` for strict validation
- `python-frontmatter` for YAML+markdown parsing
- Modular structure under `python-backend/lib/templates/` with `__init__.py` exports
- Type hints on all function signatures
- Logging via module-level `logger` from `lib.config`
- Test fixtures in `python-backend/tests/fixtures/`

### Integration Points
- Renderer module goes in `python-backend/lib/templates/renderer.py` (new file)
- Renderer classes and factory function exported via `lib/templates/__init__.py`
- Pipeline integration (Phase 6) will call `render_report()` factory function
- `generate_impression` callable will be provided by the LLM pipeline stage in Phase 6

</code_context>

<specifics>
## Specific Ideas

- The two-pass rendering approach: first pass substitutes field and technique placeholders, second pass substitutes `{{measurement:name}}` placeholders within interpolated normal text (relevant for US HBS)
- For FreeformRenderer important_first: reorder the placeholder lines in the body so important fields' placeholders appear first in the FINDINGS section, then remaining fields in original template order
- Structured variant table in plain text: `Liver: Normal` / `Liver: See below` / `Liver: __NOT_DOCUMENTED__` -- one field per line with colon separator
- Comparison section uses `{{technique:comparison}}` with default fallback to "None available." -- handled through the technique dict mechanism, not a separate parameter
- Section header rendering: `## FINDINGS` becomes `FINDINGS` (strip `## ` prefix, keep uppercase)

</specifics>

<deferred>
## Deferred Ideas

- Configurable output format (markdown vs plain text) -- v2 feature, plain text only for now
- LLM-generated partial normal text for groups -- if authored partials prove too rigid
- Post-render LLM restructure for important_first -- if deterministic reordering produces awkward output
- Async impression callable -- add in Phase 6 if needed for non-blocking LLM calls
- Structured renderer column alignment -- colon-separated is sufficient for now, aligned columns can be added later

</deferred>

---

*Phase: 04-report-renderer*
*Context gathered: 2026-03-29*
