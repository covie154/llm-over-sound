# Phase 3: Base Template Authoring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 03-base-template-authoring
**Areas discussed:** Clinical field inventory, Normal text authoring style, Structured vs freeform variants, Measurement placeholders, Schema changes needed, Template file naming, Guidance section content

---

## Clinical Field Inventory

### CT AP field organization

| Option | Description | Selected |
|--------|-------------|----------|
| Fine-grained organ fields | Each organ gets its own field | ✓ |
| Grouped natural clusters | Group commonly-normal organs into clusters | |
| Hybrid approach | Fine-grained in frontmatter, groups collapse at render time | |

**User's choice:** Fine-grained organ fields
**Notes:** Maximum LLM extraction precision

### Boundary organs

| Option | Description | Selected |
|--------|-------------|----------|
| CT AP owns lung bases, CT thorax owns limited abdomen | No overlap, composite concatenates | ✓ |
| Boundary fields excluded from both | Only in composite | |
| Both include boundary fields | Deduplication at composition time | |

**User's choice:** CT AP owns lung bases, CT thorax owns limited abdomen

### Pelvis sex-dependent fields

| Option | Description | Selected |
|--------|-------------|----------|
| Separate male and female fields | uterus, ovaries, prostate as 3 fields | |
| Grouped by sex | female_pelvis group + male_pelvis field | |
| Single pelvis field with sex variants | One field, two normal text variants | |

**User's choice:** Custom — two fields: uterus_ovaries (sex:female) as single combined field, prostate (sex:male)
**Notes:** User combined uterus and ovaries into one female field rather than splitting into three separate fields

### Mediastinum granularity (CT thorax)

| Option | Description | Selected |
|--------|-------------|----------|
| Mediastinum and hila as one field | Single combined field | |
| Split mediastinum and hila | Two separate fields | |
| Fine-grained mediastinal structures | Separate fields for nodes, vessels, thymus, hila | |

**User's choice:** Custom — mediastinum (lymph nodes, thymus etc) and heart_great_vessels (cardiac/vascular)
**Notes:** User wanted a different split than offered: mediastinum/hila together, but heart/great vessels separate

### CT thorax full field list

**User's choice:** Provided directly:
1. Lungs
2. Pleura
3. Airways (optional)
4. Thyroid (optional)
5. Mediastinum
6. Heart/great vessels
7. Limited Abdomen
8. Bones

### US HBS fields

| Option | Description | Selected |
|--------|-------------|----------|
| Just the four core fields | Liver, gallbladder_cbd, spleen, pancreas | |
| Add kidneys as optional | Core four + kidneys | |
| Core four plus free fluid | Core four + free_fluid | |

**User's choice:** Custom — four core fields plus an "others" optional catch-all field
**Notes:** "Others" field can be blank, serves as catch-all for incidental findings

### Bowel and mesentery

| Option | Description | Selected |
|--------|-------------|----------|
| Single field: bowel_mesentery | Combined | |
| Separate: bowel + mesentery | Split for extraction precision | ✓ |

**User's choice:** Separate fields

### Lymph node field

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated lymph_nodes field | Single field for node survey | ✓ |
| Regional coverage only | No standalone field | |

**User's choice:** Dedicated lymph_nodes field

### Vessels field

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated vessels field | For aorta, IVC, portal vein | ✓ |
| No dedicated field | Vessel findings in organ fields | |
| You decide | Claude picks | |

**User's choice:** Dedicated vessels field, but optional — may not appear if no finding
**Notes:** This drove the decision for the new `optional` flag

### Optional field behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Omit silently | Remove from output when blank | |
| __NOT_DOCUMENTED__ like all others | Consistent sentinel | |
| New field flag: optional | optional: true omits, required shows __NOT_DOCUMENTED__ | ✓ |

**User's choice:** New optional flag on FieldDefinition

### CT thorax bones/soft tissues

| Option | Description | Selected |
|--------|-------------|----------|
| Single bones_soft_tissues | Combined field | |
| Split: bones + soft_tissues | Separate fields | |
| Just bones, soft tissues optional | Bones required, soft tissues optional | ✓ |

**User's choice:** Just bones — soft tissues dropped entirely for CT thorax

### Pleura laterality

| Option | Description | Selected |
|--------|-------------|----------|
| Single pleura field | One field, laterality in free text | ✓ |
| Split: right_pleura + left_pleura | Separate fields | |

**User's choice:** Single pleura field

---

## Normal Text Authoring Style

### Prose style

| Option | Description | Selected |
|--------|-------------|----------|
| Terse clinical | Minimal statements | |
| Standard reporting | Full sentences | ✓ |
| Descriptive with pertinent negatives | Thorough with related negatives | |

**User's choice:** Standard reporting for prefilled template normal text. Terse clinical for LLM-fleshed-out text from brief notes. Full sentences preserved as-is.

### Measurements in normals

| Option | Description | Selected |
|--------|-------------|----------|
| Qualitative only in normals | "Normal in size" | |
| Include typical normal values | Embed measurement placeholders in normal text | |
| You decide per organ | Claude picks by clinical convention | |

**User's choice:** Include measurement placeholder in normal text only when the template enforces a measurement for that field. Otherwise qualitative only.

### Pertinent negatives scope

| Option | Description | Selected |
|--------|-------------|----------|
| Organ-focused only | Normal text covers the organ itself only | ✓ |
| Include related pertinent negatives | Extended negatives for related structures | |
| Template author decides per field | No rigid rule | |

**User's choice:** Organ-focused only

### Group joint normal style

| Option | Description | Selected |
|--------|-------------|----------|
| Concise combined statement | Single sentence for the group | ✓ |
| Individual organ sentences joined | Each organ stated separately as one block | |
| You decide per group | Claude picks per group | |

**User's choice:** Concise combined statement

### Partial combinations

| Option | Description | Selected |
|--------|-------------|----------|
| Author key partials now | Write most common 2-member partials | ✓ |
| Defer partials to renderer | Only joint_normal, fall back to individual | |
| Empty partials, extend later | partials: [] now, populate if needed | |

**User's choice:** Author key partials now

---

## Structured vs Freeform Variants

### Variant definitions

| Option | Description | Selected |
|--------|-------------|----------|
| Structured = full sections, Freeform = minimal | Full vs bare minimum sections | |
| Structured = organ-grouped, Freeform = narrative | Organized by organ vs continuous prose | |
| Let me describe it | Custom description | ✓ |

**User's choice:** Custom description provided:
- Freeform: Continuous prose like existing fixture
- Structured: Tabular organ list (organ: Normal/See below), then Key Findings prose block, then Other Findings prose block

### Which study type gets both variants

| Option | Description | Selected |
|--------|-------------|----------|
| CT AP | Most complex, proves pattern | ✓ |
| CT thorax | Simpler, less authoring work | |
| All three | 6 templates total | |

**User's choice:** CT AP

### Organ list status values (structured)

| Option | Description | Selected |
|--------|-------------|----------|
| Normal / See below only | Binary | |
| Normal / See below / __NOT_DOCUMENTED__ | Three states | ✓ |
| You decide | Claude picks | |

**User's choice:** Three states — preserves no-fabrication rule

### Key/Other Findings classification

| Option | Description | Selected |
|--------|-------------|----------|
| LLM classifies at extraction time | LLM decides key vs other | ✓ |
| Template body drives via important_first | Existing flag, no extra LLM work | |
| Radiologist tags in draft | Explicit marking by user | |

**User's choice:** LLM classifies at extraction time

### Alias naming convention

| Option | Description | Selected |
|--------|-------------|----------|
| Default = freeform, structured suffix | "ct ap" → freeform, "ct ap structured" → structured | ✓ |
| Default = structured, freeform suffix | "ct ap" → structured | |
| Both require explicit suffix | No default | |

**User's choice:** Default = freeform, structured suffix

### Shared frontmatter

| Option | Description | Selected |
|--------|-------------|----------|
| Same frontmatter, different body | Identical fields/groups/flags | |
| Frontmatter can differ too | Fully independent variants | ✓ |
| Mostly shared, flags can differ | Fields same, flags can differ | |

**User's choice:** Frontmatter can differ — each variant is fully independent

### Technique/Comparison in structured variant

| Option | Description | Selected |
|--------|-------------|----------|
| Full sections before organ list | HISTORY / TECHNIQUE / COMPARISON / findings / COMMENT | ✓ |
| Minimal: just FINDINGS and COMMENT | Organ list is the entire body | |
| You decide | Claude structures based on convention | |

**User's choice:** Full sections before organ list

---

## Measurement Placeholders

### Enforced measurements

**User's choice:** US HBS only for Phase 3. CT templates have no enforced measurements.

### Specific US HBS measurements

| Option | Description | Selected |
|--------|-------------|----------|
| Liver span (cm) | Craniocaudal liver span | ✓ |
| CBD diameter (mm) | Common bile duct caliber | ✓ |
| Gallbladder wall thickness (mm) | GB wall for cholecystitis | |
| Spleen length (cm) | Spleen craniocaudal length | ✓ |

**User's choice:** Liver span, CBD diameter, spleen length. GB wall thickness deferred.

### Underscore notation

| Option | Description | Selected |
|--------|-------------|----------|
| Inline with units: '_ cm' | Readable underscore | |
| Named placeholder: {{measurement:name}} | Consistent with Phase 1 syntax | ✓ |
| Both: named that renders as '_ cm' | Best of both worlds | |

**User's choice:** Named placeholder syntax

### Missing measurement rendering

| Option | Description | Selected |
|--------|-------------|----------|
| __NOT_DOCUMENTED__ | Same sentinel as other fields | ✓ |
| Underscore: '_ cm' | Quick visual cue | |
| You decide | Claude picks | |

**User's choice:** __NOT_DOCUMENTED__ — consistent behavior

### Measurement position in body

| Option | Description | Selected |
|--------|-------------|----------|
| Embedded in normal text | Part of the field's prose | ✓ |
| Separate line after field | Visually distinct from field | |
| You decide per measurement | Claude picks per case | |

**User's choice:** Embedded in normal text

---

## Schema Changes Needed

### Schema change timing

| Option | Description | Selected |
|--------|-------------|----------|
| Part of Phase 3 | Schema and templates evolve together | |
| Pre-phase schema update | Quick change before Phase 3 | ✓ |
| Phase 3 plan 1 = schema, plan 2 = templates | Explicit two-plan split | |

**User's choice:** Pre-phase /gsd:quick task for `optional` flag

### Structured variant schema impact

| Option | Description | Selected |
|--------|-------------|----------|
| Pure body difference | No schema changes needed | ✓ |
| New variant_type field | Add to TemplateSchema | |
| New body section markers | Schema validates Key/Other Findings headers | |

**User's choice:** Pure body difference — no new schema concepts

---

## Template File Naming

### Variant file naming

| Option | Description | Selected |
|--------|-------------|----------|
| Default has no suffix | ct_ap.rpt.md + ct_ap_structured.rpt.md | ✓ |
| Both have explicit suffixes | ct_ap_freeform.rpt.md + ct_ap_structured.rpt.md | |
| Subdirectories per variant | rpt_templates/ct/freeform/ + structured/ | |

**User's choice:** Default has no suffix, variant has suffix

### Single-variant naming

| Option | Description | Selected |
|--------|-------------|----------|
| Plain name | ct_thorax.rpt.md | ✓ |
| Explicit freeform suffix always | ct_thorax_freeform.rpt.md | |
| Match CT AP default | Follow whatever convention CT AP uses | |

**User's choice:** Plain name — clean and simple

---

## Guidance Section Content

### Content types

| Option | Description | Selected |
|--------|-------------|----------|
| Normal dimension thresholds | Key measurements and normal ranges | ✓ |
| Classification systems | Bosniak, Fleischner, etc. | ✓ |
| Reporting pitfalls | Completeness reminders | |
| Clinical decision thresholds | Objective criteria for findings | |

**User's choice:** Normal dimension thresholds + classification systems

### Variant guidance consistency

| Option | Description | Selected |
|--------|-------------|----------|
| Same guidance for both | Clinical reference doesn't depend on layout | ✓ |
| Can differ | Each variant independent | |
| You decide | Claude picks | |

**User's choice:** Same guidance for both variants

### Guidance depth

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal but real | 2-3 thresholds + 1-2 classifications per template | ✓ |
| Comprehensive clinical reference | Full dimension tables, all classifications | |
| Placeholder guidance, flesh out later | Skeleton with TODOs | |

**User's choice:** Minimal but real

---

## Claude's Discretion

- Exact wording of normal text for each organ
- Which specific partial combinations to author for each group
- Specific classification systems and thresholds to include in guidance
- Internal YAML structure details

## Deferred Ideas

- Comprehensive guidance content — refine after Phase 3
- MRI templates — CT and US first
- Sub-organ field granularity — v2
- Additional CT AP variants beyond structured
- GB wall thickness measurement for US HBS
