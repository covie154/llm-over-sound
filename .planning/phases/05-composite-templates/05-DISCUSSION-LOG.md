# Phase 5: Composite Templates - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 05-composite-templates
**Areas discussed:** Composition model, Boundary deduplication, CT TAP template design, Renderer integration, Schema changes, Variant inheritance, Findings dict shape, Validation rules, Error handling

---

## Composition Model

### Q1: Should a composite template have its own body, or be purely assembled from base template bodies?

| Option | Description | Selected |
|--------|-------------|----------|
| Thin reference | Composite frontmatter has composable_from list + its own flags. No fields or body of its own -- assembled from bases at load time. Keeps templates DRY. | ✓ |
| Hybrid with own body | Composite has composable_from AND its own body that references base sections via include markers. | |
| Full override | Composite has its own complete fields and body, composable_from as optional hint. | |

**User's choice:** Thin reference
**Notes:** None

### Q2: How should composable_from reference base templates?

| Option | Description | Selected |
|--------|-------------|----------|
| Relative file paths | Relative to rpt_templates/ directory. Explicit, no ambiguity. | ✓ |
| Study aliases | Resolved through registry alias index. Readable but creates dependency. | |
| Template names | Uses study_name field. Readable but fragile. | |

**User's choice:** Relative file paths
**Notes:** None

### Q3: Should a composite template define its own technique section, or merge base techniques?

| Option | Description | Selected |
|--------|-------------|----------|
| Own technique | Composite writes its own technique text. Combined study has single technique section. | ✓ |
| Merge base techniques | Concatenate technique sections with separator. | |

**User's choice:** Own technique
**Notes:** None

### Q4: Should a composite template define its own guidance section?

| Option | Description | Selected |
|--------|-------------|----------|
| Concatenate base guidance | Append guidance from each base in order. Organ-specific info still relevant. | ✓ |
| Own guidance section | Composite writes its own combined guidance. | |

**User's choice:** Concatenate base guidance
**Notes:** None

---

## Boundary Deduplication

### Q5: How should duplicate fields be handled when composing?

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude list in composite | Composite has exclude_fields list per base template. Explicit control. | ✓ |
| Last-wins dedup | Last base template's version wins. Simple but implicit. | |
| Rename with prefix | Duplicate fields get prefixed (e.g. thorax_bones). | |

**User's choice:** Exclude list in composite
**Notes:** None

### Q6: For CT TAP, which template should own boundary/shared fields?

| Option | Description | Selected |
|--------|-------------|----------|
| AP owns bones | CT AP keeps bones. Exclude from thorax. | |
| Thorax owns bones | CT thorax keeps bones. Exclude from AP. | |
| Keep both | Don't deduplicate -- different normal text per region. | |
| Drop from both, add to composite | Exclude bones from both bases. Composite adds its own bones field. | ✓ |

**User's choice:** Other -- Drop bones from each template, add "bones" specifically into the CT TAP template separately, because it covers both body regions
**Notes:** This led to the decision that composites can define their own additional fields (D-05)

### Q7: Composite needs its own fields. Should it also have a body snippet for placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Extra fields + insertion point | Composite defines fields and a body snippet for placement control. | ✓ |
| Extra fields, auto-appended | Fields always appended at end. Simpler but less control. | |

**User's choice:** Extra fields + insertion point
**Notes:** None

---

## CT TAP Template Design

### Q8: How should CT TAP findings section be organized?

| Option | Description | Selected |
|--------|-------------|----------|
| Subheaded blocks | "Thorax:" subheading, then thorax findings, then "Abdomen and Pelvis:" subheading, then AP findings. | ✓ |
| Flat continuous | All findings in one block, no subheadings. | |

**User's choice:** Subheaded blocks, but noted this is a template-level decision. Others might prefer flat. Make it flexible.
**Notes:** This confirmed that the body snippet approach supports both layouts (D-14)

### Q9: Should CT TAP exist as freeform only, or also get a structured variant?

| Option | Description | Selected |
|--------|-------------|----------|
| Freeform only | One CT TAP composite. Prove composition first. | ✓ |
| Both variants | CT TAP freeform + structured. Doubles work. | |

**User's choice:** Freeform only
**Notes:** None

---

## Renderer Integration

### Q10: Should composition happen at load time or render time?

| Option | Description | Selected |
|--------|-------------|----------|
| Load time | Produces single LoadedTemplate. Renderer sees normal template. | ✓ |
| Render time | Renderer receives CompositeTemplate and merges internally. | |

**User's choice:** Load time
**Notes:** None

### Q11: Should registry expose composite templates the same way as base templates?

| Option | Description | Selected |
|--------|-------------|----------|
| Same API, transparent | Registry.get('ct tap') returns LoadedTemplate like any other. | ✓ |
| Separate API | Registry.get_composite() as distinct method. | |

**User's choice:** Same API, transparent
**Notes:** None

### Q12: How should groups be handled across composed templates?

| Option | Description | Selected |
|--------|-------------|----------|
| Carry forward from bases | Groups preserved. Excluded members drop the group. | ✓ |
| Composite defines own groups | Composite can define new groups spanning base fields. | |

**User's choice:** Carry forward from bases, BUT composite can also define additional groups on top
**Notes:** Led to D-12 -- composite groups additive to base groups

---

## Schema Changes

### Q13: Single TemplateSchema or separate CompositeSchema?

| Option | Description | Selected |
|--------|-------------|----------|
| Single TemplateSchema | Add optional composition fields. One model, one loader path. | ✓ |
| Separate CompositeSchema | Inheriting model. Cleaner separation but two models. | |

**User's choice:** Single TemplateSchema
**Notes:** None

---

## Variant Inheritance

### Q14: Which CT AP base should the CT TAP composite reference?

| Option | Description | Selected |
|--------|-------------|----------|
| Reference default (freeform) | Explicit path to ct_ap.rpt.md. Future structured TAP references structured base. | ✓ |
| Resolve variant at load time | Automatic variant matching. More magic. | |

**User's choice:** Reference the default (freeform) base
**Notes:** None

---

## Findings Dict Shape

### Q15: What shape is the findings dict for composite studies?

| Option | Description | Selected |
|--------|-------------|----------|
| Flat dict | All field names as keys. Matches composed LoadedTemplate. | ✓ |
| Nested by region | Dict keyed by region, each containing field dicts. | |

**User's choice:** Flat dict
**Notes:** None

---

## Validation Rules

### Q16: Eager or lazy validation for composite templates?

| Option | Description | Selected |
|--------|-------------|----------|
| Eager at load time | Resolve, merge, validate at startup. Fail fast. | ✓ |
| Lazy at first render | Compose on first access. Faster startup. | |

**User's choice:** Eager at load time
**Notes:** None

### Q17: Field name collisions -- error or warning?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard error | Composite fails to load. Forces explicit resolution. | ✓ |
| Warning, last wins | Log warning, proceed with last base's version. | |

**User's choice:** Hard error
**Notes:** None

---

## Error Handling

### Q18: How to handle missing base template in composable_from?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail with clear error | TemplateLoadError with missing path and referencing composite. | ✓ |
| Skip and warn | Log warning, skip composite, load others normally. | |

**User's choice:** Fail with clear error
**Notes:** None

### Q19: Should the system detect circular composition?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, detect at load time | Track resolution chain, raise error on cycle. | ✓ |
| No, out of scope | Unlikely enough to skip. | |

**User's choice:** Yes, detect at load time
**Notes:** None

---

## Claude's Discretion

- Internal implementation of composition/merge algorithm
- Body snippet insertion mechanism
- Exact YAML syntax for exclude_fields
- Group carry-forward and drop logic implementation
- Test fixture design
- Validation error message wording

## Deferred Ideas

- Structured CT TAP variant -- prove freeform composition first
- Nested composition (composite references composite) -- not needed yet
- Auto-variant matching -- explicit paths preferred
- Dynamic composition at request time (PIPE-04 in v2)
