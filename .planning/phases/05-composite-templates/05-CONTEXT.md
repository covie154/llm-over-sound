# Phase 5: Composite Templates - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

A composition system that lets composite templates reference base templates via `composable_from`, merge their fields and body sections, exclude boundary duplicates, add composite-specific fields, and produce a single `LoadedTemplate` at load time. The CT TAP composite template is the proof case. Composition is transparent to the renderer and registry callers — a composed template is indistinguishable from a base template after loading.

</domain>

<decisions>
## Implementation Decisions

### Composition Model
- **D-01:** Composite templates use a thin reference model — frontmatter has `composable_from` list + its own flags (impression, interpolate_normal, important_first, variant). No complete fields list or body inherited from base templates
- **D-02:** `composable_from` references base templates by relative file path from `rpt_templates/` directory (e.g. `['ct/ct_thorax.rpt.md', 'ct/ct_ap.rpt.md']`). Explicit, no ambiguity
- **D-03:** Composite defines its own `technique` section in frontmatter — a combined study has a single technique section (e.g. "CT of the chest, abdomen and pelvis..."), not two pasted together
- **D-04:** Guidance sections are concatenated from base templates in order. No separate composite guidance
- **D-05:** Composite can define additional `fields` of its own (e.g. `bones` for CT TAP) that don't come from any base template. These have their own normal text and field definitions
- **D-06:** Composite can define additional `groups` of its own, on top of groups carried forward from base templates

### Boundary Deduplication
- **D-07:** Composite frontmatter has an `exclude_fields` dict keyed by base template path, each value a list of field names to exclude from that base. Explicit control over what gets dropped
- **D-08:** For CT TAP specifically: `bones` is excluded from BOTH CT thorax and CT AP base templates. The composite adds its own `bones` field covering both body regions
- **D-09:** CT thorax `limited_abdomen` is excluded (full abdomen is covered by CT AP). CT AP `lung_bases` is excluded (full lungs covered by CT thorax)

### Field Groups
- **D-10:** Groups from base templates are carried forward into the composed template
- **D-11:** If a group member is excluded via `exclude_fields`, that entire group is dropped from the composed template (group integrity — partial groups are invalid)
- **D-12:** Composite can define its own additional groups in frontmatter, spanning any fields in the final composed field list

### CT TAP Template Design
- **D-13:** CT TAP uses subheaded findings blocks: "Thorax:" subheading followed by thorax findings, then "Abdomen and Pelvis:" subheading followed by AP findings, then shared fields (bones). Layout is controlled by the composite's body snippet
- **D-14:** The body snippet approach means other composite templates could choose flat continuous layout — the composition system supports both, the template decides
- **D-15:** CT TAP exists as freeform only in Phase 5. Structured variant deferred
- **D-16:** Composite references the default (freeform) CT AP base: `ct/ct_ap.rpt.md`. A future structured CT TAP would reference `ct/ct_ap_structured.rpt.md`

### Renderer Integration
- **D-17:** Composition happens at load time, producing a single `LoadedTemplate`. The renderer sees a normal template — no renderer changes needed
- **D-18:** The registry exposes composite templates identically to base templates. `Registry.get('ct tap')` returns a `LoadedTemplate` — transparent to callers
- **D-19:** The composite body snippet defines where base template body sections and extra fields are placed. The loader/composer assembles the final body from base bodies + composite snippet

### Findings Dict Shape
- **D-20:** Findings for a composite study use a flat dict with all field names as keys: `{'lungs': '...', 'liver': '...', 'bones': '...'}`. Matches the composed `LoadedTemplate` field list directly

### Schema Changes
- **D-21:** All composition fields go into the existing `TemplateSchema` as optional fields: `composable_from: list[str] | None`, `exclude_fields: dict[str, list[str]] | None`. No separate CompositeSchema model
- **D-22:** Base templates leave composition fields as None (default). The loader distinguishes composite vs base by checking `composable_from is not None`

### Variant Inheritance
- **D-23:** `composable_from` references explicit file paths — the composite author chooses which variant of each base template to reference. No automatic variant matching

### Validation Rules
- **D-24:** Eager validation at load time — when the registry loads a composite template, it immediately resolves base templates, applies exclusions, merges fields, and validates. Errors fail at startup
- **D-25:** Field name collisions after applying `exclude_fields` are a hard error. Every duplicate must be explicitly resolved via exclusion or the composite fails to load
- **D-26:** Circular composition detection at load time — track resolution chain during composition, raise error if a cycle is detected

### Error Handling
- **D-27:** Missing base template referenced in `composable_from` raises a `TemplateLoadError` with the missing path and the composite template that references it. Composite is not loaded
- **D-28:** Excluding a field name that doesn't exist in the referenced base template raises a validation error (typo detection)

### Claude's Discretion
- Internal implementation of the composition/merge algorithm
- How the body snippet insertion mechanism works (markers, concatenation, etc.)
- Exact `exclude_fields` YAML syntax and structure
- How group carry-forward and drop logic is implemented
- Test fixture design for composition edge cases
- Exact validation error message wording

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Artifacts (Schema & Placeholder Decisions)
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` -- Placeholder syntax D-01-D-04, field groups D-05-D-12, body structure D-22-D-25, validation D-26-D-28

### Phase 2 Artifacts (Registry & Loader)
- `.planning/phases/02-template-loader-registry/02-CONTEXT.md` -- LoadedTemplate dataclass, registry API, alias conventions, file extension `.rpt.md`, directory structure

### Phase 3 Artifacts (Template Content & Field Inventories)
- `.planning/phases/03-base-template-authoring/03-CONTEXT.md` -- CT AP fields D-01-D-08 (especially D-03: boundary ownership), CT thorax fields D-09-D-12, normal text style D-15-D-18, variant pattern D-19-D-26

### Phase 4 Artifacts (Renderer)
- `.planning/phases/04-report-renderer/04-CONTEXT.md` -- Renderer architecture D-05-D-08, render_report() factory D-08, stateless API D-30, LoadedTemplate as input D-31

### Existing Code
- `python-backend/lib/templates/schema.py` -- TemplateSchema (needs composable_from, exclude_fields additions), FieldDefinition, FieldGroup, GroupPartial models
- `python-backend/lib/templates/loader.py` -- LoadedTemplate dataclass, template loading logic (needs composition support)
- `python-backend/lib/templates/registry.py` -- TemplateRegistry (composition must be transparent to callers)
- `python-backend/lib/templates/renderer.py` -- ReportRenderer, FreeformRenderer, StructuredRenderer (NO changes needed)
- `python-backend/lib/templates/exceptions.py` -- TemplateLoadError and other exceptions

### Template Files (Base Templates)
- `python-backend/rpt_templates/ct/ct_ap.rpt.md` -- Freeform CT AP (18 fields, bones to be excluded in composite)
- `python-backend/rpt_templates/ct/ct_ap_structured.rpt.md` -- Structured CT AP (not referenced by CT TAP composite)
- `python-backend/rpt_templates/ct/ct_thorax.rpt.md` -- CT thorax (8 fields, bones and limited_abdomen to be excluded in composite)
- `python-backend/rpt_templates/us/us_hbs.rpt.md` -- US HBS (not involved in composition)

### Requirements
- `.planning/REQUIREMENTS.md` -- Phase 5 requirements: COMP-01, COMP-02, COMP-03, COMP-04, SMPL-03

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TemplateSchema` Pydantic model with `ConfigDict(extra="forbid")` -- new optional fields must be added before composite YAML will parse
- `LoadedTemplate` dataclass with `schema`, `body`, `file_path` -- the composition output target
- `TemplateRegistry` with `_scan_directory()` and alias-to-path index -- needs to handle composite loading in scan order
- `validate_body_placeholders()` -- can validate the final composed body against merged fields
- `TemplateLoadError` exception class -- reuse for composition errors

### Established Patterns
- YAML frontmatter parsed by `python-frontmatter`, validated by Pydantic
- `extra="forbid"` catches unknown keys -- composition fields must be in the model
- Registry scans `rpt_templates/` recursively for `*.rpt.md` files
- Loader returns `LoadedTemplate` dataclass consumed by renderer

### Integration Points
- Schema additions in `schema.py`: `composable_from`, `exclude_fields` as optional fields
- Composition logic likely in a new `composer.py` module or extension to `loader.py`
- CT TAP template file at `python-backend/rpt_templates/ct/ct_tap.rpt.md`
- Registry `_load_template()` or post-load hook resolves composites into LoadedTemplates

</code_context>

<specifics>
## Specific Ideas

- The composite body snippet uses subheadings for CT TAP: "Thorax:" followed by thorax field placeholders, "Abdomen and Pelvis:" followed by AP field placeholders, then composite's own fields (bones) at the end
- Bones field excluded from both base templates and redefined in the composite with normal text covering the full skeleton survey (ribs, thoracic spine, lumbar spine, pelvis)
- The composition system is layout-flexible: subheaded blocks for CT TAP, but another composite could use flat continuous layout -- the body snippet controls this
- Findings dict is always flat regardless of composition -- the LLM just sees one field list

</specifics>

<deferred>
## Deferred Ideas

- Structured CT TAP composite variant -- prove freeform composition first
- Nested composition (composite referencing another composite) -- not needed yet, circular detection covers the safety case
- Auto-variant matching (composite resolves to matching variant of base) -- explicit paths preferred
- Dynamic composition at request time (e.g. "CT thorax + CTPA") -- PIPE-04 in v2 requirements

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-composite-templates*
*Context gathered: 2026-03-31*
