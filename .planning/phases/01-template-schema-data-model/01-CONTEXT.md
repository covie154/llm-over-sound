# Phase 1: Template Schema & Data Model - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Define the YAML+markdown template format and Pydantic validation models for radiology report templates. This phase delivers the data model (Pydantic schemas for template metadata, field definitions, groups, and LLM output), the template file format specification (YAML frontmatter + markdown body), and a minimal test fixture to validate everything end-to-end. No clinical content authoring, no rendering logic, no registry/loader — those are later phases.

</domain>

<decisions>
## Implementation Decisions

### Placeholder Syntax
- **D-01:** Template placeholders use double-brace syntax: `{{field_name}}`
- **D-02:** Measurement placeholders use colon-namespaced type prefix: `{{measurement:liver_span_cm}}`
- **D-03:** Technique placeholders use colon-namespaced type prefix: `{{technique:phase}}`, `{{technique:contrast}}`
- **D-04:** All placeholder types share the `{{...}}` wrapper — type is distinguished by the colon prefix (no prefix = text field, `measurement:` = required measurement, `technique:` = technique variable)

### Field Group Design
- **D-05:** Field groups defined as a `groups` list in YAML frontmatter. Each group has `name`, `members` (list of field names), and `joint_normal` text
- **D-06:** Each field in `members` must exist in the `fields` list (Pydantic cross-validation)
- **D-07:** A field can belong to at most one group
- **D-08:** When a group partially expands (some members abnormal, some normal), the normal members use **template-authored partial combination text**. The template author pre-writes partial combinations for the subsets they expect. Missing partials fall back to individual field normal text
- **D-09:** LLM-generated partial text is a noted fallback option if authored partials prove too rigid — not implemented in v1 but kept in mind
- **D-10:** No cap on group size. Template author writes the partial combinations they need
- **D-11:** YAML list order is canonical report order — no explicit `order` integer per field
- **D-12:** Sex-dependent fields appear inline in the fields list with a `sex` tag (e.g. `{name: uterus, sex: female, normal: '...'}`). Both variants exist in the template; LLM/renderer filters by patient context at runtime

### Guidance Section
- **D-13:** Guidance section is free-text markdown in the template body (a `## Guidance` section), not structured YAML
- **D-14:** Guidance is LLM-only context — injected into LLM prompts for extraction/impression but stripped from the rendered report output
- **D-15:** Guidance section is optional — validated if present, not required

### LLM Output Schema
- **D-16:** Findings model is a dynamic Pydantic model generated per template using `create_model()`. Template field names become model fields at load time. Enables LLM structured output constraints
- **D-17:** Field type is `Optional[str]` — `None` means unreported (→ `__NOT_DOCUMENTED__` or normal text depending on `interpolate_normal`), string means extracted finding
- **D-18:** Sentence expansion from brief notes happens in LLM extraction (Phase 3) before data enters the Pydantic model. The schema stores final strings only, no verbatim tracking
- **D-19:** Importance classification (for `important_first`) is a separate LLM step at render time (Phase 4), not part of the findings model. Importance operates on field groups, not individual fields — the whole group gets bumped together
- **D-20:** Single Pydantic model per template covers both technique and anatomical findings — one extraction call
- **D-21:** Phase 1 defines both the study type classification output model (constrained to known aliases) and the findings extraction model

### Template Body Structure
- **D-22:** Markdown H2 headers for report sections: `## CLINICAL HISTORY`, `## TECHNIQUE`, `## COMPARISON`, `## FINDINGS`, `## COMMENT`
- **D-23:** One placeholder or group per line in the template body
- **D-24:** Renderer preserves template whitespace exactly — literal substitution. Single newline = consecutive lines, double newline = paragraph break. Template author controls layout entirely through newline placement
- **D-25:** Field groups are listed as individual field placeholders in the body. The renderer collapses them into joint/partial normal text when appropriate. No explicit group placeholder syntax in the body

### Validation Strictness
- **D-26:** Strict Pydantic validation: `extra: 'forbid'`. Unknown YAML keys cause a validation error at load time
- **D-27:** Error messages must be clear and actionable — pinpoint the exact key/value that failed and why
- **D-28:** Cross-validation between frontmatter fields and body placeholders: warn/error if a field has no matching placeholder in the body, or if the body references a placeholder not in the fields list

### Field Handling
- **D-29:** `__NOT_DOCUMENTED__` for everything not mentioned in the draft, no exceptions. The system never infers or prompts for pertinent negatives. Radiologist fills gaps manually after reviewing the rendered report
- **D-30:** No interaction during report creation — the system renders and returns, radiologist reviews after

### Sample Template
- **D-31:** Phase 1 includes a minimal test fixture template (not clinically accurate) with 3-4 fields, one group, one measurement placeholder, one sex-dependent field. Lives in a tests/fixtures directory. Purpose: prove Pydantic models load, validate, and cross-check correctly

### Claude's Discretion
- Internal Pydantic model class structure and naming
- How partial combination texts are stored in the group YAML (e.g. `partials` dict keyed by frozenset of normal members, or a list of `{members: [...], text: "..."}`)
- Error message formatting details
- Test fixture field names and content

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Documentation
- `CLAUDE.md` — Master project documentation including report structure, pipeline stages, key constraints, and audio channel specs
- `python-backend/CLAUDE.md` — Backend-specific documentation including pipeline stage details and safety requirements

### Existing Code
- `python-backend/lib/pipeline.py` — Existing `ReportPipeline` base class and `LLMPipeline` stub with 5-stage pipeline structure
- `python-backend/lib/__init__.py` — Public API exports for the lib package

### Research
- `.planning/research/SUMMARY.md` — Research summary with stack recommendations (python-frontmatter, Pydantic 2.10+), architecture (4 components), and critical pitfalls
- `.planning/research/ARCHITECTURE.md` — Detailed architecture research including component design
- `.planning/research/FEATURES.md` — Feature research including field groups, composability, sex-dependent fields
- `.planning/research/PITFALLS.md` — Safety pitfalls including hallucination rates, measurement mangling, interpolation dangers

### Requirements
- `.planning/REQUIREMENTS.md` — Full requirements with Phase 1 IDs: TMPL-01, TMPL-02, TMPL-03, TMPL-07, TMPL-08, TMPL-09, FWRK-03, FWRK-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReportPipeline` base class in `python-backend/lib/pipeline.py` — abstract interface that the template system will plug into
- `LLMPipeline` stub with `retrieve_template()` and `extract_findings()` methods already defined — schema models will feed into these

### Established Patterns
- Python snake_case naming, PascalCase for classes, ALL_CAPS for constants
- Modular structure under `python-backend/lib/` with `__init__.py` exports
- Type hints on function signatures
- Docstrings on modules, classes, and public functions
- `python-backend/rpt_templates/` directory exists (empty) — designated location for template files

### Integration Points
- Template Pydantic models will be imported by `LLMPipeline` in Phase 6
- The `rpt_templates/` directory is where templates live — the registry (Phase 2) scans this
- Dynamic findings model feeds into `extract_findings()` return type

</code_context>

<specifics>
## Specific Ideas

- Group partial text authoring: try pre-authored partials first; if the language feels too stilted during Phase 3 template authoring, switch to LLM-generated partials as a fallback
- The template body example discussed uses `## FINDINGS` with individual field placeholders, whitespace-controlled layout, and no explicit group markers in the body

</specifics>

<deferred>
## Deferred Ideas

- LLM-generated partial normal text for groups (D-09) — fallback if authored partials don't work well in practice
- Clinical-history-aware prompting for pertinent negatives (e.g. "query bowel ischaemia" → prompt to comment on free gas) — v2 feature, not in current scope

</deferred>

---

*Phase: 01-template-schema-data-model*
*Context gathered: 2026-03-28*
