# Roadmap: LLM Report Templates

## Overview

This milestone delivers the template system that powers radiology report formatting. Starting from the data model and schema definition, we build up through parsing, real clinical content authoring, deterministic rendering, template composition for combined studies, and finally wire everything into the existing backend pipeline. Each phase produces a verifiable capability -- a template that parses, a registry that resolves, reports that render correctly.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Template Schema & Data Model** - Define YAML+markdown template format and Pydantic validation models
- [x] **Phase 2: Template Loader & Registry** - Parse templates from disk, build alias index, expose as standalone module (completed 2026-03-28)
- [ ] **Phase 3: Base Template Authoring** - Write CT AP, CT thorax, and US HBS templates with real clinical content
- [ ] **Phase 4: Report Renderer** - Deterministic report assembly honoring interpolation, impression, and ordering flags
- [ ] **Phase 5: Composite Templates** - Composition system for combined studies and CT TAP template
- [ ] **Phase 6: Pipeline Integration** - Wire template system into the existing 5-stage backend pipeline

## Phase Details

### Phase 1: Template Schema & Data Model
**Goal**: A Pydantic-validated schema defines what a valid template looks like, and a sample template can be loaded and validated without errors
**Depends on**: Nothing (first phase)
**Requirements**: TMPL-01, TMPL-02, TMPL-03, TMPL-07, TMPL-08, TMPL-09, FWRK-03, FWRK-04
**Success Criteria** (what must be TRUE):
  1. A YAML+markdown template file can be parsed by python-frontmatter and its frontmatter validated by the Pydantic model without errors
  2. The Pydantic model enforces required fields: study name, aliases list, ordered field definitions with normal text, technique section, and guidance section
  3. Field groups with joint normal text are representable in the schema and validate correctly
  4. A Pydantic model exists for LLM findings output with field-name-keyed structured output that validates against a template's field list
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Pydantic models for template schema, findings output, and study type classification
- [x] 01-02-PLAN.md — Test infrastructure, fixture template, and comprehensive validation tests

### Phase 2: Template Loader & Registry
**Goal**: Templates on disk are discovered, parsed, indexed by alias, and resolvable by study type name -- usable as a standalone Python module
**Depends on**: Phase 1
**Requirements**: MTCH-01, MTCH-02, MTCH-03, FWRK-01
**Success Criteria** (what must be TRUE):
  1. The template registry scans rpt_templates/ recursively at startup and builds a complete alias-to-filepath index
  2. Exact alias match returns the correct template; unmatched input falls through to an LLM fallback path (stub acceptable, but interface defined)
  3. The template system is importable and callable as a standalone Python module without requiring the ggwave backend
**Discussion Notes** (for /gsd:discuss-phase):
  - The alias index must support multiple templates for the same body region with different format variants (e.g. "ct ap structured" vs "ct ap freeform"). Same fields, different body layouts. Variant selection happens entirely through alias matching — no GUI toggle, text input only.
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Module reorganization, loader, exceptions, and test fixtures
- [x] 02-02-PLAN.md — TemplateRegistry class with alias index and comprehensive tests

### Phase 3: Base Template Authoring
**Goal**: Three clinically accurate base templates exist with real organ-level fields, normal defaults, sex-dependent pelvis fields, and measurement placeholders
**Depends on**: Phase 1, Phase 2
**Requirements**: SMPL-01, SMPL-02, SMPL-04, FLDS-01, FLDS-02
**Success Criteria** (what must be TRUE):
  1. CT abdomen/pelvis template loads and validates, contains organ-level fields in craniocaudal order, sex-dependent pelvis fields (male and female variants), and a guidance section
  2. CT thorax template loads and validates, contains lungs, pleura, mediastinum/hila, heart/pericardium, limited abdomen, and bones fields
  3. US HBS template loads and validates, contains liver, gallbladder/CBD, spleen, and pancreas fields with measurement placeholders marked as required
  4. All templates have radiologist-authored default normal text for every field and measurement placeholders use underscore notation
**Discussion Notes** (for /gsd:discuss-phase):
  - Author template variants with different body layouts (structured vs freeform) for the same study type. Different section headers (HISTORY/TECHNIQUE/REPORT/COMMENT vs just FINDINGS/IMPRESSION), different boilerplate structure. The body IS the per-radiologist boilerplate — no separate config layer.
  - Consider authoring both a structured and freeform variant for at least one study type (e.g. CT AP) to prove the variant pattern works end-to-end.
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Report Renderer
**Goal**: Given a template and extracted findings, the renderer produces a correctly formatted report respecting all template flags and field handling rules
**Depends on**: Phase 1, Phase 3
**Requirements**: TMPL-04, TMPL-05, TMPL-06, TMPL-10, FLDS-03
**Success Criteria** (what must be TRUE):
  1. When interpolate_normal is false, unreported fields output the literal string `__NOT_DOCUMENTED__`; when true, unreported fields are filled with the template's stored normal text
  2. When the impression flag is true, a COMMENT/impression section is included in output; when false, it is omitted
  3. When important_first is true, findings flagged as clinically important are rendered before other findings; when false, template order is preserved
  4. A per-request "rest normal" phrase overrides interpolate_normal to true for that single request only
  5. Field groups render joint normal text when all members are unreported (and interpolate_normal is on), but expand to individual fields when any member has findings
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Composite Templates
**Goal**: Combined study templates compose from base templates, and the CT TAP template correctly concatenates thorax and abdomen/pelvis sections
**Depends on**: Phase 3, Phase 4
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, SMPL-03
**Success Criteria** (what must be TRUE):
  1. A composite template referencing base templates via composable_from loads and resolves all referenced base templates
  2. The composed template concatenates fields and body sections in order (thorax block then abdomen/pelvis block) without duplicate fields at boundaries
  3. Composite template flags (impression, interpolate_normal, important_first) come from the composite frontmatter, not from base templates
  4. The CT TAP composite template renders a complete report using the renderer from Phase 4
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Pipeline Integration
**Goal**: The template system is wired into the existing 5-stage backend pipeline so that ggwave messages trigger template-based report formatting end-to-end
**Depends on**: Phase 2, Phase 4, Phase 5
**Requirements**: FWRK-02
**Success Criteria** (what must be TRUE):
  1. A message received by the backend triggers study type classification, template lookup via the registry, and report rendering via the renderer
  2. The template system functions correctly when called from the pipeline (not just standalone) with no import or path resolution errors
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Template Schema & Data Model | 0/2 | Not started | - |
| 2. Template Loader & Registry | 2/2 | Complete   | 2026-03-28 |
| 3. Base Template Authoring | 0/1 | Not started | - |
| 4. Report Renderer | 0/2 | Not started | - |
| 5. Composite Templates | 0/1 | Not started | - |
| 6. Pipeline Integration | 0/1 | Not started | - |
