# Phase 3: Base Template Authoring - Research

**Researched:** 2026-03-29
**Domain:** Radiology report template content authoring (YAML frontmatter + markdown body)
**Confidence:** HIGH

## Summary

Phase 3 is a content authoring phase, not a code development phase. The primary deliverable is three clinically accurate radiology report templates (CT AP, CT thorax, US HBS) plus one variant (CT AP structured) written as `.rpt.md` files conforming to the existing Pydantic schema and loader infrastructure built in Phases 1 and 2.

The existing schema (`TemplateSchema`, `FieldDefinition`, `FieldGroup`) and loader/registry code are complete and tested. Templates must pass `TemplateSchema` validation (strict `extra="forbid"`) and `validate_body_placeholders()` cross-validation at load time. The existing stub templates in `tests/fixtures/registry_fixtures/` are minimal placeholders that will be superseded by real production templates.

**Primary recommendation:** Author templates directly as `.rpt.md` files in `python-backend/rpt_templates/ct/` and `python-backend/rpt_templates/us/`, validate each with the existing loader, and add integration tests that load the real templates through the registry. A pre-phase schema update must add `optional: bool = False` to `FieldDefinition` before authoring begins (D-38).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Fine-grained organ fields, each organ gets its own field for maximum LLM extraction precision
- **D-02:** CT AP field list (craniocaudal order): liver, gallbladder, cbd, spleen, adrenals, pancreas, kidneys, bowel, mesentery, lymph_nodes, bladder, uterus_ovaries (sex:female), prostate (sex:male), vessels (optional), lung_bases, free_fluid, bones, soft_tissues
- **D-03:** CT AP owns lung bases -- no overlap with CT thorax. CT thorax owns limited abdomen
- **D-04:** Sex-dependent pelvis: `uterus_ovaries` (sex:female) as single combined field, `prostate` (sex:male)
- **D-05:** `vessels` field is optional -- omitted from rendered output when no finding. Dedicated to abdominal aorta, IVC, portal vein
- **D-06:** Dedicated `lymph_nodes` field for retroperitoneal, mesenteric, inguinal node survey
- **D-07:** `bowel` and `mesentery` are separate fields (not combined)
- **D-08:** New `optional: true` flag on FieldDefinition -- optional fields are silently omitted from rendered output when blank; required fields show `__NOT_DOCUMENTED__`
- **D-09:** CT thorax fields (in order): lungs, pleura, airways (optional), thyroid (optional), mediastinum, heart_great_vessels, limited_abdomen, bones
- **D-10:** Single `pleura` field (not split by laterality) -- LLM extracts lateralized findings as free text
- **D-11:** `mediastinum` covers lymph nodes, thymus, etc. `heart_great_vessels` covers cardiac and vascular structures
- **D-12:** `bones` is required; soft_tissues dropped entirely for CT thorax
- **D-13:** US HBS fields: liver, gallbladder_cbd, spleen, pancreas, others (optional)
- **D-14:** `others` is an optional catch-all field that can be blank -- for incidental findings outside the four core organs
- **D-15:** Template normal text uses standard reporting prose (full sentences)
- **D-16:** Normal text is organ-focused only -- no extended pertinent negatives beyond the organ itself
- **D-17:** Group joint normal text uses concise combined statements
- **D-18:** Author key partial combination text now -- write the most common 2-member partials for groups with 3+ members
- **D-19:** Freeform variant = continuous prose paragraphs (default variant)
- **D-20:** Structured variant = tabular organ list with Normal/See below/__NOT_DOCUMENTED__ status, then Key Findings + Other Findings prose sections
- **D-21:** CT AP gets both variants. CT thorax and US HBS get freeform only in Phase 3
- **D-22:** Default variant owns short alias (e.g. "ct ap"). Structured uses suffix ("ct ap structured")
- **D-23:** Frontmatter can differ between variants -- fields, groups, and flags are independent per variant file
- **D-24:** Structured variant has full sections: CLINICAL HISTORY / TECHNIQUE / COMPARISON / organ list + Key Findings + Other Findings / COMMENT
- **D-25:** LLM classifies findings as "key" vs "other" at extraction time (Phase 4 concern, template body anticipates it)
- **D-26:** Structured variant is purely a body layout difference -- no new schema concepts
- **D-27:** Enforced measurements in US HBS only: `liver_span_cm`, `cbd_diameter_mm`, `spleen_length_cm`. CT templates have no enforced measurements in Phase 3
- **D-28:** Uses `{{measurement:name}}` placeholder syntax (per Phase 1 D-02)
- **D-29:** Measurement placeholders embedded within the field's normal text prose
- **D-30:** Missing measurements render as `__NOT_DOCUMENTED__`
- **D-31:** Only include measurements in normal text when the template enforces a measurement for that field
- **D-32:** Default variant has no suffix: `ct_ap.rpt.md`. Variant has suffix: `ct_ap_structured.rpt.md`
- **D-33:** Single-variant templates use plain name: `ct_thorax.rpt.md`, `us_hbs.rpt.md`
- **D-34:** Templates in modality subdirectories: `rpt_templates/ct/`, `rpt_templates/us/`
- **D-35:** Guidance includes normal dimension thresholds and classification system references
- **D-36:** Same guidance content for both structured and freeform variants
- **D-37:** Minimal but real guidance in Phase 3: 2-3 key thresholds and 1-2 classification references per template
- **D-38:** Add `optional: bool = False` to FieldDefinition before Phase 3 template authoring begins (pre-phase quick task)

### Claude's Discretion
- Exact wording of normal text for each organ (clinical accuracy within the standard reporting style)
- Which specific partial combinations to author for each group
- Specific classification systems and thresholds to include in guidance sections
- Internal YAML structure details (group member ordering, partial text formatting)

### Deferred Ideas (OUT OF SCOPE)
- Comprehensive guidance content (full dimension tables, all classification systems)
- MRI templates
- Sub-organ field granularity (liver segments, vertebral levels)
- Additional CT AP variants beyond structured
- GB wall thickness measurement for US HBS
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SMPL-01 | CT abdomen and pelvis template with full organ-level fields, normal defaults, sex-dependent pelvis fields, and guidance section | D-02 defines exact field list, D-04 defines sex fields, D-35-37 define guidance scope. Schema validated by existing FieldDefinition + FieldGroup models |
| SMPL-02 | CT thorax template with lungs, pleura, mediastinum/hila, heart/pericardium, limited abdomen, and bones fields | D-09 defines exact field list with optional markers. Schema validates all fields |
| SMPL-04 | US HBS template with liver, gallbladder/CBD, spleen, and pancreas fields including measurement placeholders | D-13 defines fields, D-27 defines required measurements, D-28-29 define placeholder syntax in prose |
| FLDS-01 | Templates support sex-dependent optional fields -- both male and female variants exist in template, LLM selects based on context | CT AP template includes uterus_ovaries (sex:female) and prostate (sex:male) per D-04. FieldDefinition already supports `sex` field |
| FLDS-02 | Measurement fields use `_` placeholders and are marked as required -- missing measurements output `__NOT_DOCUMENTED__` | US HBS uses `{{measurement:name}}` syntax per D-28. Measurement placeholders in body are validated by existing cross-validation |
</phase_requirements>

## Standard Stack

No new libraries are needed for this phase. All infrastructure exists from Phases 1 and 2.

### Core (Existing, Not New)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| python-frontmatter | (installed) | Parse YAML frontmatter from .rpt.md files | Existing from Phase 1 |
| pydantic | (installed) | Validate template schema at load time | Existing from Phase 1 |
| pytest | 8.3.4 | Test framework | Existing |

### Tools Used During Authoring
| Tool | Purpose |
|------|---------|
| `TemplateRegistry` | Load and validate templates end-to-end |
| `load_template()` | Parse single template file |
| `validate_body_placeholders()` | Cross-validate frontmatter fields vs body tokens |

## Architecture Patterns

### Template File Structure (Established)
```
python-backend/
  rpt_templates/
    ct/
      ct_ap.rpt.md              # CT AP freeform (default)
      ct_ap_structured.rpt.md   # CT AP structured variant
      ct_thorax.rpt.md          # CT thorax freeform
    us/
      us_hbs.rpt.md             # US HBS freeform
```

### YAML Frontmatter Pattern (from sample_template.md)
```yaml
---
study_name: "CT Abdomen and Pelvis"
aliases:
  - "ct ap"
  - "ct abdomen"
  - "ct abdomen pelvis"
  - "ct abdomen and pelvis"
technique: "CT of the abdomen and pelvis was performed with intravenous contrast in the portal venous phase."
interpolate_normal: false
impression: true
important_first: false
fields:
  - name: "liver"
    normal: "The liver is normal in size and attenuation. No focal lesion."
  - name: "uterus_ovaries"
    sex: "female"
    normal: "The uterus and ovaries are normal."
  - name: "prostate"
    sex: "male"
    normal: "The prostate is normal in size."
  - name: "vessels"
    optional: true                # NEW: requires D-38 schema update
    normal: "The abdominal aorta and IVC are normal in calibre."
groups:
  - name: "spleen_adrenals_pancreas"
    members:
      - "spleen"
      - "adrenals"
      - "pancreas"
    joint_normal: "The spleen, adrenal glands and pancreas are unremarkable."
    partials:
      - members: ["spleen", "adrenals"]
        text: "The spleen and adrenal glands are unremarkable."
      - members: ["spleen", "pancreas"]
        text: "The spleen and pancreas are unremarkable."
      - members: ["adrenals", "pancreas"]
        text: "The adrenal glands and pancreas are unremarkable."
---
```

### Body Template Pattern (Freeform)
```markdown
## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

{{liver}}

{{gallbladder}}

{{cbd}}

{{spleen}}

...field placeholders in craniocaudal order...

{{uterus_ovaries}}

{{prostate}}

## Guidance

...LLM-only reference content...

## COMMENT
```

### Body Template Pattern (Structured -- CT AP only)
```markdown
## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

| Organ | Status |
|-------|--------|
| Liver | {{liver}} |
| Gallbladder | {{gallbladder}} |
...all fields...

### Key Findings

(LLM populates with clinically important findings)

### Other Findings

(LLM populates with incidental/minor findings)

## COMMENT
```

### Anti-Patterns to Avoid
- **Fabricated normal text:** Normal text must reflect actual radiology reporting conventions. Do not invent clinical language -- use standard phrases radiologists use daily
- **Extended pertinent negatives in normal text:** D-16 prohibits cross-organ pertinent negatives (e.g. liver normal text must NOT mention "no biliary dilatation" -- that belongs in the gallbladder/CBD field)
- **Measurement placeholders in CT templates:** D-27 explicitly limits enforced measurements to US HBS only in Phase 3. CT templates use qualitative assessments ("normal in size")
- **Overlapping fields between templates:** D-03 defines clear boundaries. CT AP owns lung bases, CT thorax owns limited abdomen. No duplication

## Pre-Phase Blocker: Schema Update (D-38)

**CRITICAL:** The `optional` field does NOT exist on `FieldDefinition` yet. D-38 states this must be added before Phase 3 template authoring begins. Without it, templates using `optional: true` (vessels in CT AP, airways/thyroid in CT thorax, others in US HBS) will fail schema validation with `extra="forbid"`.

**Required change:**
```python
class FieldDefinition(BaseModel):
    name: str
    normal: str
    sex: Optional[str] = None
    optional: bool = False        # NEW -- D-38
```

This is defined as a pre-phase `/gsd:quick` task, not part of Phase 3 plans. The planner must either:
1. Verify it was completed before Phase 3 starts, OR
2. Include it as Wave 0 / first task in the plan

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template validation | Custom YAML parsing | Existing `load_template()` + `TemplateSchema` | Pydantic validation catches all structural issues |
| Body placeholder checking | Manual regex matching | Existing `validate_body_placeholders()` | Already handles field vs typed placeholder separation |
| Registry integration testing | Ad-hoc loading | `TemplateRegistry(dir)` constructor | Validates all templates, checks alias collisions |

## Common Pitfalls

### Pitfall 1: Extra YAML Keys Rejected by Strict Validation
**What goes wrong:** Adding any key not in the Pydantic model (typo, experimental field) causes `ValidationError` with `extra="forbid"`.
**Why it happens:** Template authors try adding custom metadata.
**How to avoid:** Only use keys defined in `TemplateSchema`: `study_name`, `aliases`, `fields`, `groups`, `technique`, `interpolate_normal`, `impression`, `important_first`. After D-38, `FieldDefinition` also accepts `optional`.
**Warning signs:** `Extra inputs are not permitted` in validation error.

### Pitfall 2: Field Name Not Referenced in Body
**What goes wrong:** `validate_body_placeholders()` raises a fatal error if a field defined in frontmatter has no `{{field_name}}` placeholder in the body.
**Why it happens:** Forgetting to add a placeholder for every field, or misspelling the placeholder name.
**How to avoid:** Every field in the `fields` list MUST have exactly one `{{field_name}}` token in the body. Verify by running loader after authoring each template.
**Warning signs:** "Field 'X' defined in frontmatter but has no placeholder in template body"

### Pitfall 3: Group Members Not in Fields List
**What goes wrong:** Pydantic cross-validation fails if a group member references a field name not in the `fields` list.
**Why it happens:** Typo in group member name, or adding a group before defining all its member fields.
**How to avoid:** Define all fields first, then create groups referencing those exact field names.
**Warning signs:** "Group 'X' references field 'Y' which is not in the fields list"

### Pitfall 4: Alias Collision Between Variants
**What goes wrong:** `TemplateRegistry` startup fails if two templates share an alias.
**Why it happens:** CT AP freeform and structured variant both claiming "ct ap".
**How to avoid:** Per D-22, default variant owns short alias ("ct ap"), structured variant uses suffix ("ct ap structured"). No overlap.
**Warning signs:** "Alias 'ct ap' conflicts with [other file path]"

### Pitfall 5: Registry Fixture Alias Collision with Production Templates
**What goes wrong:** If tests load both `tests/fixtures/registry_fixtures/` AND `rpt_templates/`, aliases like "ct ap" will collide.
**Why it happens:** Test fixtures from Phase 2 use the same aliases as production templates.
**How to avoid:** Tests should either (a) load only the fixture directory, or (b) update fixture aliases to be clearly distinct (e.g. "test ct ap"). Production template tests should use the production directory only.
**Warning signs:** Registry startup failure in tests after adding production templates.

### Pitfall 6: Measurement Placeholder Syntax Mismatch
**What goes wrong:** Using `{{liver_span_cm}}` instead of `{{measurement:liver_span_cm}}` makes it look like a regular field placeholder, triggering "placeholder has no matching field" error.
**Why it happens:** Forgetting the `measurement:` type prefix.
**How to avoid:** All measurement placeholders MUST use `{{measurement:name}}` syntax. The `measurement:` prefix tells the validator it is a typed placeholder (separate namespace from fields).

### Pitfall 7: Optional Field Without Schema Support
**What goes wrong:** Adding `optional: true` to a field definition before D-38 schema update causes `extra="forbid"` rejection.
**Why it happens:** Phase 3 templates require `optional` but the schema change is a separate pre-phase task.
**How to avoid:** Complete D-38 schema update first. Verify with a quick test that `FieldDefinition(name="test", normal="test", optional=True)` validates.

## Code Examples

### Loading and Validating a Template
```python
# Source: existing loader.py
from lib.templates.loader import load_template
import pathlib

template = load_template(pathlib.Path("rpt_templates/ct/ct_ap.rpt.md"))
print(template.schema.study_name)  # "CT Abdomen and Pelvis"
print(len(template.schema.fields))  # 18 (including sex-dependent variants)
```

### Registry Integration Test Pattern
```python
# Source: existing test_registry.py pattern
from lib.templates.registry import TemplateRegistry

registry = TemplateRegistry("rpt_templates")
template = registry.get_template("ct ap")
assert template.schema.study_name == "CT Abdomen and Pelvis"

# Structured variant has different alias
structured = registry.get_template("ct ap structured")
assert structured.schema.study_name == "CT Abdomen and Pelvis (Structured)"
```

### Sex-Dependent Field in YAML
```yaml
# Source: Phase 1 D-12, existing sample_template.md
fields:
  - name: "uterus_ovaries"
    sex: "female"
    normal: "The uterus and ovaries are normal in size and morphology."
  - name: "prostate"
    sex: "male"
    normal: "The prostate is normal in size."
```

### Measurement Placeholder in Normal Text (US HBS)
```yaml
# Source: Phase 3 D-28, D-29
fields:
  - name: "liver"
    normal: "The liver is normal in echotexture, measuring {{measurement:liver_span_cm}} cm in craniocaudal span."
```

### Group with Partials
```yaml
# Source: Phase 1 D-08, Phase 3 D-17/D-18
groups:
  - name: "spleen_adrenals_pancreas"
    members:
      - "spleen"
      - "adrenals"
      - "pancreas"
    joint_normal: "The spleen, adrenal glands and pancreas are unremarkable."
    partials:
      - members: ["spleen", "adrenals"]
        text: "The spleen and adrenal glands are unremarkable."
      - members: ["spleen", "pancreas"]
        text: "The spleen and pancreas are unremarkable."
      - members: ["adrenals", "pancreas"]
        text: "The adrenal glands and pancreas are unremarkable."
```

## CT AP Field Inventory (D-02, Research for Normal Text)

The following fields are defined by D-02 in craniocaudal order. Normal text recommendations based on standard radiology reporting conventions (Claude's discretion per CONTEXT.md):

| Field Name | Normal Text (Standard Prose) | Sex | Optional | Groups |
|------------|------------------------------|-----|----------|--------|
| liver | "The liver is normal in size and attenuation. No focal lesion." | - | no | - |
| gallbladder | "The gallbladder is normal. No gallstones." | - | no | - |
| cbd | "The common bile duct is normal in calibre." | - | no | gallbladder_cbd group |
| spleen | "The spleen is normal in size." | - | no | spleen_adrenals_pancreas group |
| adrenals | "The adrenal glands are normal." | - | no | spleen_adrenals_pancreas group |
| pancreas | "The pancreas is normal in morphology and enhancement." | - | no | spleen_adrenals_pancreas group |
| kidneys | "The kidneys are normal in size and enhancement. No hydronephrosis or renal calculus." | - | no | - |
| bowel | "The visualised bowel is unremarkable. No dilatation or wall thickening." | - | no | - |
| mesentery | "The mesentery is clear." | - | no | - |
| lymph_nodes | "No pathologically enlarged lymph nodes." | - | no | - |
| bladder | "The urinary bladder is normal." | - | no | - |
| uterus_ovaries | "The uterus and ovaries are normal in size and morphology." | female | no | - |
| prostate | "The prostate is normal in size." | male | no | - |
| vessels | "The abdominal aorta is normal in calibre. The IVC and portal vein are patent." | - | yes | - |
| lung_bases | "The visualised lung bases are clear." | - | no | - |
| free_fluid | "No free fluid." | - | no | - |
| bones | "No suspicious osseous lesion." | - | no | - |
| soft_tissues | "The abdominal wall and soft tissues are unremarkable." | - | no | - |

**Groups for CT AP:**
1. `gallbladder_cbd`: gallbladder + cbd -- "The gallbladder and common bile duct are normal. No gallstones."
2. `spleen_adrenals_pancreas`: spleen + adrenals + pancreas -- "The spleen, adrenal glands and pancreas are unremarkable."

**Possible additional groups:** `bowel_mesentery` (bowel + mesentery) could be grouped but D-07 separates them explicitly. Whether to group them is Claude's discretion for field grouping strategy, but they remain separate fields regardless.

## CT Thorax Field Inventory (D-09)

| Field Name | Normal Text | Sex | Optional |
|------------|-------------|-----|----------|
| lungs | "The lungs are clear. No consolidation, mass or nodule." | - | no |
| pleura | "No pleural effusion or pneumothorax." | - | no |
| airways | "The trachea and main bronchi are patent." | - | yes |
| thyroid | "The thyroid gland is unremarkable." | - | yes |
| mediastinum | "No pathological mediastinal or hilar lymphadenopathy." | - | no |
| heart_great_vessels | "The heart is normal in size. No pericardial effusion. The thoracic aorta is normal in calibre." | - | no |
| limited_abdomen | "The visualised upper abdomen is unremarkable." | - | no |
| bones | "No suspicious osseous lesion." | - | no |

**Groups for CT thorax:** Less natural grouping opportunity here. `lungs` and `pleura` could be grouped but their normal text is quite different in character. Recommend no groups for CT thorax in Phase 3.

## US HBS Field Inventory (D-13)

| Field Name | Normal Text | Sex | Optional |
|------------|-------------|-----|----------|
| liver | "The liver is normal in echotexture, measuring {{measurement:liver_span_cm}} cm in craniocaudal span. No focal lesion." | - | no |
| gallbladder_cbd | "The gallbladder is normal with no gallstones or wall thickening. The common bile duct measures {{measurement:cbd_diameter_mm}} mm, within normal limits." | - | no |
| spleen | "The spleen is normal in echotexture, measuring {{measurement:spleen_length_cm}} cm." | - | no |
| pancreas | "The pancreas is normal in echotexture where visualised." | - | no |
| others | "" | - | yes |

**Note:** `others` has empty normal text since it is a catch-all for incidental findings. When blank and optional, it is silently omitted.

**Groups for US HBS:** No natural groups -- only 4 core fields, each with distinct anatomy and measurement requirements.

## Guidance Section Content (D-35-37)

### CT AP Guidance (Minimal -- 2-3 thresholds, 1-2 classifications)
- Normal aortic calibre: infrarenal aorta up to 2.0 cm (men), 1.8 cm (women). Aneurysm threshold: 3.0 cm
- Normal CBD calibre: up to 6 mm (up to 10 mm post-cholecystectomy)
- Bosniak classification for renal cysts (reference LI-RADS for liver lesions if contrast CT)

### CT Thorax Guidance
- Lymph node short axis threshold: 10 mm for mediastinal/hilar lymphadenopathy
- Fleischner Society guidelines for incidental pulmonary nodule management (reference only -- mention the guideline, not full tables)
- Normal thoracic aortic calibre: up to 4.0 cm at mid-ascending aorta

### US HBS Guidance
- Normal liver span: up to 15.5 cm (craniocaudal)
- Normal CBD calibre: up to 6 mm (up to 10 mm post-cholecystectomy)
- Normal spleen length: up to 12 cm

## Structured Variant Body Layout (D-20, D-24)

The structured variant for CT AP uses a different body structure but the same fields in frontmatter. The body replaces continuous prose with:

1. Standard headers: CLINICAL HISTORY, TECHNIQUE, COMPARISON
2. An organ status list (one line per field with the field placeholder)
3. A "Key Findings" section (populated by LLM with clinically significant findings)
4. An "Other Findings" section (populated by LLM with incidental findings)
5. COMMENT section

The field placeholders work identically -- the renderer substitutes the same way. The difference is purely layout. Per D-26, no new schema concepts are needed.

The structured variant sets `important_first: true` to signal the renderer that findings should be triaged into key vs other categories.

## Existing Stub Templates vs Production Templates

The `tests/fixtures/registry_fixtures/` directory contains stub templates with minimal fields used for Phase 2 registry testing. These stubs have overlapping aliases with production templates (e.g. "ct ap", "ct thorax", "us hbs").

**Impact:** Production templates in `rpt_templates/` and test fixtures in `tests/fixtures/registry_fixtures/` are loaded by DIFFERENT registry instances (different directories), so no alias collision occurs. Tests using the fixture directory continue to work. New tests targeting production templates should create a separate registry instance pointing to `rpt_templates/`.

**Recommendation:** Keep existing fixture stubs for Phase 2 regression tests. Add new production template validation tests using the production directory.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | python-backend/ (implicit) |
| Quick run command | `cd python-backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd python-backend && python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SMPL-01 | CT AP template loads, validates, has 18 fields in order, sex-dependent pelvis, guidance section | integration | `python -m pytest tests/test_production_templates.py::test_ct_ap_loads -x` | No -- Wave 0 |
| SMPL-02 | CT thorax template loads, validates, has correct fields (lungs, pleura, mediastinum, etc.) | integration | `python -m pytest tests/test_production_templates.py::test_ct_thorax_loads -x` | No -- Wave 0 |
| SMPL-04 | US HBS template loads, validates, has measurement placeholders | integration | `python -m pytest tests/test_production_templates.py::test_us_hbs_loads -x` | No -- Wave 0 |
| FLDS-01 | CT AP has uterus_ovaries (sex:female) and prostate (sex:male) fields | unit | `python -m pytest tests/test_production_templates.py::test_ct_ap_sex_fields -x` | No -- Wave 0 |
| FLDS-02 | US HBS body contains measurement:liver_span_cm, measurement:cbd_diameter_mm, measurement:spleen_length_cm | unit | `python -m pytest tests/test_production_templates.py::test_us_hbs_measurements -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd python-backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd python-backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `python-backend/tests/test_production_templates.py` -- covers SMPL-01, SMPL-02, SMPL-04, FLDS-01, FLDS-02
- [ ] Schema update: `optional: bool = False` on FieldDefinition (D-38 pre-phase task)
- [ ] Existing registry fixture stubs verified not to conflict with production tests

## Open Questions

1. **Registry fixture stub update**
   - What we know: Existing stubs in `tests/fixtures/registry_fixtures/` have the same study names and aliases as the production templates being authored
   - What's unclear: Whether any existing tests rely on the specific field count or content of those stubs
   - Recommendation: Leave stubs untouched; new tests use production directory. If a stub's alias changes, update the registry test assertions accordingly

2. **Structured variant alias set**
   - What we know: D-22 says structured uses suffix alias ("ct ap structured")
   - What's unclear: Whether the structured variant should also have "ct abdomen pelvis structured", "ct abdomen structured" etc.
   - Recommendation: Include the most common suffix variants (match base aliases with " structured" appended)

3. **Group strategy for fields with overlapping concerns**
   - What we know: gallbladder and CBD are separate fields (D-02) but closely related anatomically
   - What's unclear: Whether grouping them makes radiological sense when one is normal and the other abnormal
   - Recommendation: Group gallbladder+CBD since they are routinely reported together. If gallbladder is abnormal, the CBD finding (e.g. "dilated CBD") would likely also be reported explicitly

## Sources

### Primary (HIGH confidence)
- `python-backend/lib/templates/schema.py` -- current FieldDefinition, FieldGroup, TemplateSchema models
- `python-backend/lib/templates/loader.py` -- load_template(), validate_body_placeholders()
- `python-backend/lib/templates/registry.py` -- TemplateRegistry class
- `python-backend/tests/fixtures/sample_template.md` -- reference template format
- `python-backend/tests/fixtures/registry_fixtures/` -- existing stub templates
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` -- Phase 1 schema decisions
- `.planning/phases/02-template-loader-registry/02-CONTEXT.md` -- Phase 2 registry decisions
- `.planning/phases/03-base-template-authoring/03-CONTEXT.md` -- Phase 3 locked decisions

### Secondary (MEDIUM confidence)
- Normal text wording for radiology fields -- based on standard reporting conventions widely used in clinical practice. Exact phrasing is Claude's discretion per CONTEXT.md

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all infrastructure exists
- Architecture: HIGH -- template format, file structure, and validation all established in Phases 1-2
- Clinical content: MEDIUM -- normal text uses standard radiology reporting conventions but exact wording is discretionary
- Pitfalls: HIGH -- derived from reading actual validation code and understanding strict mode behavior

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable -- template format is locked)
