# Requirements: LLM Report Templates

**Defined:** 2026-03-28
**Core Value:** The LLM must never fabricate findings. Every extracted finding must trace to the radiologist's draft input.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Template Schema

- [x] **TMPL-01**: Template files use YAML frontmatter + markdown body format, parseable by python-frontmatter
- [x] **TMPL-02**: Each template defines organ-level fields with ordered field list preserving craniocaudal or logical reporting order
- [x] **TMPL-03**: Each field stores a default normal text string (pertinent negatives authored by a radiologist)
- [ ] **TMPL-04**: Each template has an `interpolate_normal` flag (default: false) controlling whether unreported fields get normal text or `__NOT_DOCUMENTED__`
- [ ] **TMPL-05**: Each template has an `impression` flag (default: true) controlling whether a COMMENT/impression section is generated
- [ ] **TMPL-06**: Each template has an `important_first` flag (default: false) -- when true, findings deemed clinically important (based on clinical history, LLM decides) are moved to the top of the findings section, with remaining findings following template order
- [x] **TMPL-07**: Templates support field groups with joint normal text (e.g. "The spleen, adrenal glands and pancreas are unremarkable" when all members normal, expanding to individual fields when any member is abnormal)
- [x] **TMPL-08**: Templates include a technique section with boilerplate text and optional placeholders for contrast type/phase
- [x] **TMPL-09**: Templates include a guidance section with clinical reference information (normal/abnormal dimensions, interpretation guidance, clinical decision thresholds)
- [ ] **TMPL-10**: Unreported fields not interpolated as normal must output the literal string `__NOT_DOCUMENTED__`

### Study Matching

- [x] **MTCH-01**: Each template defines a list of study type aliases in YAML frontmatter for programmatic matching
- [ ] **MTCH-02**: A template registry builds an alias-to-filepath index at startup by scanning `rpt_templates/` recursively
- [ ] **MTCH-03**: Study type lookup uses exact alias match first, with LLM fallback for fuzzy/unmatched input

### Field Handling

- [ ] **FLDS-01**: Templates support sex-dependent optional fields -- both male and female variants exist in the template, LLM selects based on context
- [ ] **FLDS-02**: Measurement fields use `_` placeholders and are marked as required -- missing measurements output `__NOT_DOCUMENTED__`
- [ ] **FLDS-03**: Per-request "rest normal" override -- when radiologist says "rest normal" or equivalent phrase, `interpolate_normal` is set to true for that request only

### Composability

- [ ] **COMP-01**: Templates support a `composable_from` directive referencing base templates by relative path
- [ ] **COMP-02**: Composite templates concatenate fields and body sections from base templates in order (e.g. thorax findings block, then abdomen/pelvis findings block)
- [ ] **COMP-03**: Composite templates inherit flags (impression, interpolate_normal, important_first) from the composite template frontmatter, not from base templates
- [ ] **COMP-04**: Boundary fields have explicit ownership -- no duplicate fields when composing (e.g. "imaged lung bases" belongs to abdomen/pelvis template only)

### Sample Templates

- [ ] **SMPL-01**: CT abdomen and pelvis template with full organ-level fields, normal defaults, sex-dependent pelvis fields, and guidance section
- [ ] **SMPL-02**: CT thorax template with lungs, pleura, mediastinum/hila, heart/pericardium, limited abdomen, and bones fields
- [ ] **SMPL-03**: CT thorax, abdomen and pelvis composite template referencing CT thorax + CT abdomen/pelvis base templates
- [ ] **SMPL-04**: US HBS template with liver, gallbladder/CBD, spleen, and pancreas fields including measurement placeholders

### Framework Integration

- [x] **FWRK-01**: The template system (loader, registry, renderer) is callable as a standalone Python module for testing and research independent of the ggwave backend
- [ ] **FWRK-02**: The template system integrates with the existing 5-stage backend pipeline -- called after the backend receives a ggwave message
- [x] **FWRK-03**: Pydantic models define the template metadata schema and validate frontmatter at load time
- [x] **FWRK-04**: Pydantic models define the LLM findings output schema for constrained structured output

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Templates

- **ADVT-01**: Sub-organ field granularity (e.g. individual liver segments, vertebral levels)
- **ADVT-02**: MRI template set (brain, spine, MSK, abdomen)
- **ADVT-03**: X-ray template set (chest, abdominal, MSK)
- **ADVT-04**: BI-RADS/PI-RADS/LI-RADS scoring system templates

### Pipeline Enhancement

- **PIPE-01**: Clarification requests when study type classification confidence is below threshold
- **PIPE-02**: Post-extraction validation -- regex-based check that extracted measurements appear in original draft
- **PIPE-03**: Impression consistency check -- verify abnormal findings appear in generated impression
- **PIPE-04**: User-merged study support (e.g. "CT thorax+CTPA" parsed and composed at request time)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| DICOM SR output | Output goes over ggwave as plain text; no PACS integration |
| MRRT/HTML5 template format | Overly complex; RSNA has paused development; YAML+markdown is simpler |
| RadLex/SNOMED ontology enforcement | Adds complexity without benefit in single-user system |
| Multi-language support | Single radiologist, English-only |
| Interactive template editor | Templates are markdown files edited in a text editor |
| Drop-down/pick-list UI | Audio-only transport; no interactive form support |
| AI-generated normal text | Fabrication risk; normal text is radiologist-authored in template |
| Comparison with prior studies | No access to prior report data in architecture |
| Frontend UI changes | Separate milestone |
| LLM prompt engineering | Template system defines the schema; prompts are a separate concern |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TMPL-01 | Phase 1 | Complete |
| TMPL-02 | Phase 1 | Complete |
| TMPL-03 | Phase 1 | Complete |
| TMPL-04 | Phase 4 | Pending |
| TMPL-05 | Phase 4 | Pending |
| TMPL-06 | Phase 4 | Pending |
| TMPL-07 | Phase 1 | Complete |
| TMPL-08 | Phase 1 | Complete |
| TMPL-09 | Phase 1 | Complete |
| TMPL-10 | Phase 4 | Pending |
| MTCH-01 | Phase 2 | Complete |
| MTCH-02 | Phase 2 | Pending |
| MTCH-03 | Phase 2 | Pending |
| FLDS-01 | Phase 3 | Pending |
| FLDS-02 | Phase 3 | Pending |
| FLDS-03 | Phase 4 | Pending |
| COMP-01 | Phase 5 | Pending |
| COMP-02 | Phase 5 | Pending |
| COMP-03 | Phase 5 | Pending |
| COMP-04 | Phase 5 | Pending |
| SMPL-01 | Phase 3 | Pending |
| SMPL-02 | Phase 3 | Pending |
| SMPL-03 | Phase 5 | Pending |
| SMPL-04 | Phase 3 | Pending |
| FWRK-01 | Phase 2 | Complete |
| FWRK-02 | Phase 6 | Pending |
| FWRK-03 | Phase 1 | Complete |
| FWRK-04 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28 after roadmap creation*
