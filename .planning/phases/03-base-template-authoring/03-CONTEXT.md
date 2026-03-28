# Phase 3: Base Template Authoring - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Write three clinically accurate base templates (CT AP, CT thorax, US HBS) with real organ-level fields, normal defaults, sex-dependent pelvis fields, and measurement placeholders. Author both a freeform and structured variant for CT AP to prove the variant pattern. All templates must load and validate against the existing Pydantic schema. A pre-phase schema update adds the `optional` flag to FieldDefinition before template authoring begins.

</domain>

<decisions>
## Implementation Decisions

### Clinical Field Inventory — CT AP
- **D-01:** Fine-grained organ fields, each organ gets its own field for maximum LLM extraction precision
- **D-02:** CT AP field list (craniocaudal order): liver, gallbladder, cbd, spleen, adrenals, pancreas, kidneys, bowel, mesentery, lymph_nodes, bladder, uterus_ovaries (sex:female), prostate (sex:male), vessels (optional), lung_bases, free_fluid, bones, soft_tissues
- **D-03:** CT AP owns lung bases — no overlap with CT thorax. CT thorax owns limited abdomen
- **D-04:** Sex-dependent pelvis: `uterus_ovaries` (sex:female) as single combined field, `prostate` (sex:male)
- **D-05:** `vessels` field is optional — omitted from rendered output when no finding. Dedicated to abdominal aorta, IVC, portal vein
- **D-06:** Dedicated `lymph_nodes` field for retroperitoneal, mesenteric, inguinal node survey
- **D-07:** `bowel` and `mesentery` are separate fields (not combined)
- **D-08:** New `optional: true` flag on FieldDefinition — optional fields are silently omitted from rendered output when blank; required fields show `__NOT_DOCUMENTED__`

### Clinical Field Inventory — CT Thorax
- **D-09:** CT thorax fields (in order): lungs, pleura, airways (optional), thyroid (optional), mediastinum, heart_great_vessels, limited_abdomen, bones
- **D-10:** Single `pleura` field (not split by laterality) — LLM extracts lateralized findings as free text
- **D-11:** `mediastinum` covers lymph nodes, thymus, etc. `heart_great_vessels` covers cardiac and vascular structures
- **D-12:** `bones` is required; soft_tissues dropped entirely for CT thorax

### Clinical Field Inventory — US HBS
- **D-13:** US HBS fields: liver, gallbladder_cbd, spleen, pancreas, others (optional)
- **D-14:** `others` is an optional catch-all field that can be blank — for incidental findings outside the four core organs

### Normal Text Authoring Style
- **D-15:** Template normal text uses standard reporting prose (full sentences). LLM extraction from brief notes uses terse clinical output. Full sentences from radiologist's draft are preserved as-is
- **D-16:** Normal text is organ-focused only — no extended pertinent negatives beyond the organ itself (e.g. liver normal text does NOT include biliary dilatation comments)
- **D-17:** Group joint normal text uses concise combined statements: "The spleen, adrenal glands and pancreas are unremarkable."
- **D-18:** Author key partial combination text now — write the most common 2-member partials for groups with 3+ members

### Structured vs Freeform Variants
- **D-19:** Freeform variant = continuous prose paragraphs, organ-by-organ flowing text (like existing fixture template). This is the default variant
- **D-20:** Structured variant = tabular organ list with "Normal" / "See below" / "__NOT_DOCUMENTED__" status per field, then **Key Findings** prose section (important findings), then **Other Findings** prose section (incidentals)
- **D-21:** CT AP gets both variants to prove the pattern. CT thorax and US HBS get freeform only in Phase 3
- **D-22:** Default variant (freeform) owns the short alias (e.g. "ct ap"). Structured variant uses suffix alias ("ct ap structured")
- **D-23:** Frontmatter can differ between variants — fields, groups, and flags are independent per variant file
- **D-24:** Structured variant has full sections: CLINICAL HISTORY / TECHNIQUE / COMPARISON / organ list + Key Findings + Other Findings / COMMENT
- **D-25:** LLM classifies findings as "key" vs "other" at extraction time — needs a field in the findings output model (renderer Phase 4 concern, but template body structure anticipates it)
- **D-26:** The structured variant is purely a body layout difference — no new schema concepts needed for variants

### Measurement Placeholders
- **D-27:** Enforced measurements in US HBS only: `liver_span_cm`, `cbd_diameter_mm`, `spleen_length_cm`. CT templates have no enforced measurements in Phase 3
- **D-28:** Uses `{{measurement:name}}` placeholder syntax (per Phase 1 D-02)
- **D-29:** Measurement placeholders embedded within the field's normal text prose (not on separate lines)
- **D-30:** Missing measurements render as `__NOT_DOCUMENTED__` (consistent with other unreported fields)
- **D-31:** Only include measurements in normal text when the template enforces a measurement for that field. Otherwise qualitative only ("normal in size")

### Template File Naming
- **D-32:** Default variant has no suffix: `ct_ap.rpt.md`. Variant has suffix: `ct_ap_structured.rpt.md`
- **D-33:** Single-variant templates use plain name: `ct_thorax.rpt.md`, `us_hbs.rpt.md`
- **D-34:** Templates in modality subdirectories: `rpt_templates/ct/`, `rpt_templates/us/` (per Phase 2 D-15)

### Guidance Section Content
- **D-35:** Guidance includes normal dimension thresholds and classification system references — LLM-only context
- **D-36:** Same guidance content for both structured and freeform variants of the same study type
- **D-37:** Minimal but real guidance in Phase 3: 2-3 key thresholds and 1-2 classification references per template. Enough to prove the pattern

### Schema Changes (Pre-Phase)
- **D-38:** Add `optional: bool = False` to FieldDefinition before Phase 3 template authoring begins. This is a pre-phase /gsd:quick task, not part of Phase 3 plans

### Claude's Discretion
- Exact wording of normal text for each organ (clinical accuracy within the standard reporting style)
- Which specific partial combinations to author for each group
- Specific classification systems and thresholds to include in guidance sections
- Internal YAML structure details (group member ordering, partial text formatting)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Artifacts (Schema Decisions)
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` — Placeholder syntax (D-01–D-04), field groups (D-05–D-12), sex-dependent fields (D-12), body structure (D-22–D-25), validation strictness (D-26–D-28)

### Phase 2 Artifacts (Registry Decisions)
- `.planning/phases/02-template-loader-registry/02-CONTEXT.md` — File extension `.rpt.md` (D-16), directory structure `rpt_templates/ct/` (D-15), alias conventions (D-13–D-14), registry API (D-09–D-11)

### Existing Code
- `python-backend/lib/templates/schema.py` — TemplateSchema, FieldDefinition, FieldGroup Pydantic models (must be compatible with new templates)
- `python-backend/lib/templates/registry.py` — TemplateRegistry class that will load these templates
- `python-backend/lib/templates/loader.py` — Template loader that parses .rpt.md files
- `python-backend/tests/fixtures/sample_template.md` — Reference fixture template showing YAML frontmatter + body structure

### Project Documentation
- `CLAUDE.md` — Report structure (5 sections), pipeline stages, key constraints
- `python-backend/CLAUDE.md` — Backend pipeline details, safety requirements

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 3 requirements: SMPL-01, SMPL-02, SMPL-04, FLDS-01, FLDS-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FieldDefinition` Pydantic model with `name`, `normal`, `sex` fields — templates must validate against this
- `FieldGroup` model with `name`, `members`, `joint_normal`, `partials` — groups must reference valid field names
- `TemplateSchema` model with strict validation (`extra="forbid"`) — YAML frontmatter must match exactly
- `validate_body_placeholders()` — cross-validates frontmatter fields against body `{{placeholder}}` tokens
- Test fixture `sample_template.md` — shows working YAML+body format with technique, measurement, sex-dependent field, group, and guidance section

### Established Patterns
- YAML list order is canonical report order (Phase 1 D-11)
- `{{field_name}}` for text, `{{measurement:name}}` for measurements, `{{technique:name}}` for technique variables
- H2 headers for report sections: `## CLINICAL HISTORY`, `## TECHNIQUE`, `## FINDINGS`, `## COMMENT`
- One placeholder per line in template body
- `partials: []` for empty partials (existing convention in fixtures)

### Integration Points
- Templates go in `python-backend/rpt_templates/ct/` and `python-backend/rpt_templates/us/`
- `TemplateRegistry` scans `rpt_templates/` recursively for `*.rpt.md` files
- Registry test fixtures in `python-backend/tests/fixtures/registry_fixtures/` already have stub templates that will be superseded by real ones

</code_context>

<specifics>
## Specific Ideas

- The structured variant body layout: organ list at top (Liver: Normal / See below / __NOT_DOCUMENTED__), then Key Findings prose block, then Other Findings prose block. This directly maps to the important_first concept from TMPL-06
- US HBS "others" field is a catch-all for anything outside the four core organs — e.g. "Incidental right renal cyst" goes here
- Measurement placeholders woven into normal text: "The liver is normal in echotexture, measuring {{measurement:liver_span_cm}} cm in craniocaudal span."

</specifics>

<deferred>
## Deferred Ideas

- Comprehensive guidance content (full dimension tables, all classification systems) — refine after Phase 3 proves the pattern
- MRI templates — CT and US first per Out of Scope
- Sub-organ field granularity (liver segments, vertebral levels) — v2 per ADVT-01
- Additional CT AP variants beyond structured (e.g. by-system ordering) — after variant pattern is proven
- GB wall thickness measurement — considered for US HBS but deferred; can be added later

</deferred>

---

*Phase: 03-base-template-authoring*
*Context gathered: 2026-03-29*
