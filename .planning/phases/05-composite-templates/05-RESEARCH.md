# Phase 5: Composite Templates - Research

**Researched:** 2026-03-31
**Domain:** Template composition system -- merging base templates into composite LoadedTemplates at load time
**Confidence:** HIGH

## Summary

Phase 5 adds a composition system that lets a composite template (like CT TAP) reference base templates via `composable_from`, merge their fields and body sections, apply boundary deduplication via `exclude_fields`, add composite-specific fields/groups, and produce a single `LoadedTemplate` indistinguishable from a base template. The renderer requires zero changes.

The existing codebase is well-structured for this extension. `TemplateSchema` needs two new optional fields (`composable_from`, `exclude_fields`). The loader needs a composition step that resolves base templates, merges fields, handles exclusions, and assembles the final body. The registry needs to handle load order (composites depend on bases) and expose composites transparently via aliases.

**Primary recommendation:** Implement composition as a separate `composer.py` module called by the loader when `composable_from is not None`. Keep it isolated from the existing loader/registry code to minimize regression risk. The CT TAP template file is the proof case.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Composite templates use a thin reference model -- frontmatter has `composable_from` list + its own flags (impression, interpolate_normal, important_first, variant). No complete fields list or body inherited from base templates
- **D-02:** `composable_from` references base templates by relative file path from `rpt_templates/` directory (e.g. `['ct/ct_thorax.rpt.md', 'ct/ct_ap.rpt.md']`)
- **D-03:** Composite defines its own `technique` section in frontmatter -- a combined study has a single technique section
- **D-04:** Guidance sections are concatenated from base templates in order. No separate composite guidance
- **D-05:** Composite can define additional `fields` of its own (e.g. `bones` for CT TAP)
- **D-06:** Composite can define additional `groups` of its own, on top of groups carried forward from base templates
- **D-07:** Composite frontmatter has an `exclude_fields` dict keyed by base template path, each value a list of field names to exclude from that base
- **D-08:** For CT TAP specifically: `bones` is excluded from BOTH CT thorax and CT AP base templates. The composite adds its own `bones` field
- **D-09:** CT thorax `limited_abdomen` is excluded (full abdomen covered by CT AP). CT AP `lung_bases` is excluded (full lungs covered by CT thorax)
- **D-10:** Groups from base templates are carried forward into the composed template
- **D-11:** If a group member is excluded via `exclude_fields`, that entire group is dropped from the composed template (group integrity)
- **D-12:** Composite can define its own additional groups in frontmatter
- **D-13:** CT TAP uses subheaded findings blocks: "Thorax:" subheading followed by thorax findings, then "Abdomen and Pelvis:" subheading followed by AP findings, then shared fields (bones)
- **D-14:** The body snippet approach means other composite templates could choose flat continuous layout
- **D-15:** CT TAP exists as freeform only in Phase 5. Structured variant deferred
- **D-16:** Composite references the default (freeform) CT AP base: `ct/ct_ap.rpt.md`
- **D-17:** Composition happens at load time, producing a single `LoadedTemplate`. No renderer changes needed
- **D-18:** Registry exposes composite templates identically to base templates. Transparent to callers
- **D-19:** Composite body snippet defines where base template body sections and extra fields are placed
- **D-20:** Findings for composite use flat dict with all field names as keys
- **D-21:** All composition fields go into existing `TemplateSchema` as optional fields
- **D-22:** Base templates leave composition fields as None (default)
- **D-23:** `composable_from` references explicit file paths -- no automatic variant matching
- **D-24:** Eager validation at load time -- errors fail at startup
- **D-25:** Field name collisions after applying `exclude_fields` are a hard error
- **D-26:** Circular composition detection at load time
- **D-27:** Missing base template raises `TemplateLoadError` with the missing path
- **D-28:** Excluding a field that doesn't exist in the base raises a validation error (typo detection)

### Claude's Discretion
- Internal implementation of the composition/merge algorithm
- How the body snippet insertion mechanism works (markers, concatenation, etc.)
- Exact `exclude_fields` YAML syntax and structure
- How group carry-forward and drop logic is implemented
- Test fixture design for composition edge cases
- Exact validation error message wording

### Deferred Ideas (OUT OF SCOPE)
- Structured CT TAP composite variant
- Nested composition (composite referencing another composite)
- Auto-variant matching
- Dynamic composition at request time
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMP-01 | Templates support a `composable_from` directive referencing base templates by relative path | Schema extension with optional `composable_from: list[str] \| None` field; loader resolves paths relative to templates_dir |
| COMP-02 | Composite templates concatenate fields and body sections from base templates in order | Composer merges field lists from bases in order, assembles body from base FINDINGS sections + composite body snippet |
| COMP-03 | Composite templates inherit flags from the composite frontmatter, not from base templates | Composite's own `impression`, `interpolate_normal`, `important_first`, `variant` are used; base flags are ignored |
| COMP-04 | Boundary fields have explicit ownership -- no duplicate fields when composing | `exclude_fields` dict removes named fields from specified bases; post-merge collision check is a hard error |
| SMPL-03 | CT TAP composite template referencing CT thorax + CT AP base templates | Author `ct/ct_tap.rpt.md` with composable_from, exclude_fields, composite bones field, subheaded body snippet |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x (installed) | Schema validation with `composable_from`, `exclude_fields` optional fields | Already used for TemplateSchema; `extra="forbid"` catches invalid keys |
| python-frontmatter | (installed) | Parse YAML frontmatter from composite template files | Already used by loader.py |
| pytest | 8.3.4 (installed) | Test composition logic, edge cases, CT TAP integration | Already used for all template tests |

No new dependencies needed. All work extends the existing stack.

## Architecture Patterns

### Recommended Module Structure
```
python-backend/lib/templates/
    schema.py          # Add composable_from, exclude_fields to TemplateSchema
    composer.py        # NEW: compose_template() -- merges base templates into LoadedTemplate
    loader.py          # Add compose hook: if composable_from, delegate to composer
    registry.py        # Load order: bases before composites (two-pass or dependency sort)
    renderer.py        # NO CHANGES
    exceptions.py      # Reuse TemplateLoadError for composition errors
```

### Pattern 1: Two-Pass Registry Loading
**What:** Registry loads all templates in two passes -- first pass loads base templates (composable_from is None), second pass loads composites (composable_from is not None) and resolves their base references.
**When to use:** Always -- composites depend on bases being loaded first.
**Example:**
```python
def _load_all(self) -> None:
    paths = discover_templates(self._templates_dir)

    # First pass: load all templates, separate bases from composites
    bases: dict[str, LoadedTemplate] = {}  # relative path -> template
    composite_paths: list[pathlib.Path] = []

    for path in paths:
        template = load_template(path)
        rel_path = str(path.relative_to(self._templates_dir))
        if template.schema.composable_from is not None:
            composite_paths.append(path)
        else:
            bases[rel_path] = template
            # register aliases...

    # Second pass: compose composites from loaded bases
    for path in composite_paths:
        raw = load_template(path)  # parse frontmatter only
        composed = compose_template(raw, bases, self._templates_dir)
        # register aliases for composed template...
```

### Pattern 2: Composer as Pure Function
**What:** `compose_template(raw_template, base_registry, templates_dir) -> LoadedTemplate` is a pure function that takes the raw parsed composite template and a dict of loaded base templates, returns a fully composed LoadedTemplate.
**When to use:** Always -- keeps composition logic testable in isolation.
**Example:**
```python
def compose_template(
    composite: LoadedTemplate,
    bases: dict[str, LoadedTemplate],
    templates_dir: pathlib.Path,
) -> LoadedTemplate:
    schema = composite.schema

    # Resolve base templates
    resolved_bases = []
    for ref_path in schema.composable_from:
        if ref_path not in bases:
            raise TemplateLoadError(composite.file_path,
                f"Base template not found: {ref_path}")
        resolved_bases.append((ref_path, bases[ref_path]))

    # Merge fields with exclusion
    merged_fields = _merge_fields(resolved_bases, schema.exclude_fields, schema.fields)

    # Merge groups (carry forward, drop if member excluded, add composite groups)
    merged_groups = _merge_groups(resolved_bases, merged_fields, schema.groups)

    # Assemble body
    merged_body = _assemble_composite_body(composite.body, resolved_bases, schema.exclude_fields)

    # Build composed schema
    composed_schema = TemplateSchema(
        study_name=schema.study_name,
        aliases=schema.aliases,
        fields=merged_fields,
        groups=merged_groups,
        technique=schema.technique,
        interpolate_normal=schema.interpolate_normal,
        impression=schema.impression,
        important_first=schema.important_first,
        variant=schema.variant,
    )

    return LoadedTemplate(schema=composed_schema, body=merged_body, file_path=composite.file_path)
```

### Pattern 3: Body Snippet with Section Markers
**What:** The composite template body contains its own FINDINGS section with subheadings and special markers (e.g. `{{base:ct/ct_thorax.rpt.md}}`) where base template FINDINGS content should be inserted. Alternatively, the composer extracts FINDINGS blocks from each base and places them under the composite's subheadings.
**When to use:** CT TAP and any composite with subheaded sections.
**Recommended approach:** The composite body snippet is authored with the final layout including subheadings. The FINDINGS section of each base template is extracted (everything between `## FINDINGS` and the next `## ` header), placeholder lines for excluded fields are removed, and the content is inserted at marked positions in the composite body. The composite's own field placeholders (e.g. `{{bones}}`) appear in the composite body directly.

**Example composite body snippet (ct_tap.rpt.md):**
```markdown
## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

### Thorax

{{lungs}}

{{pleura}}

{{airways}}

{{thyroid}}

{{mediastinum}}

{{heart_great_vessels}}

### Abdomen and Pelvis

{{liver}}

{{gallbladder}} {{cbd}}

{{spleen}}
{{adrenals}}
{{pancreas}}

{{kidneys}}


{{bowel}}
{{mesentery}}

{{lymph_nodes}}


{{bladder}}
{{uterus_ovaries}}
{{prostate}}


{{vessels}}
{{free_fluid}}
{{soft_tissues}}

### Other

{{bones}}

## Guidance

Lymph node short axis threshold: 10 mm for pathological mediastinal or hilar lymphadenopathy.

Fleischner Society guidelines for incidental pulmonary nodule management.

Normal thoracic aortic calibre: up to 4.0 cm at mid-ascending aorta.

Normal aortic calibre: infrarenal aorta up to 2.0 cm (men), 1.8 cm (women). Aneurysm threshold: 3.0 cm.

Normal CBD calibre: up to 6 mm (up to 10 mm post-cholecystectomy).

Bosniak classification for renal cysts. LI-RADS for liver lesions on contrast-enhanced CT.

## COMMENT
```

**Key insight:** The simplest implementation is to have the composite template contain its own complete body (with all placeholders from the merged field list) rather than trying to programmatically extract and stitch base template body sections. The body is authored once for the composite. The composer only needs to:
1. Merge field lists (validate placeholders in body match merged fields)
2. Concatenate guidance sections from bases
3. The rest of the body is composite-authored

This is simpler, more flexible (supports both subheaded and flat layouts per D-14), and leverages the existing `validate_body_placeholders()` function.

### Pattern 4: Schema Extension for Composition
**What:** Add optional composition fields to TemplateSchema.
**Example:**
```python
class TemplateSchema(BaseModel):
    # ... existing fields ...

    # Composition (optional -- None for base templates)
    composable_from: list[str] | None = None
    exclude_fields: dict[str, list[str]] | None = None
```

The `exclude_fields` YAML syntax:
```yaml
exclude_fields:
  ct/ct_thorax.rpt.md:
    - "bones"
    - "limited_abdomen"
  ct/ct_ap.rpt.md:
    - "bones"
    - "lung_bases"
```

### Anti-Patterns to Avoid
- **Programmatic body stitching from base templates:** Extracting FINDINGS sections from bases and stitching them together is fragile and loses layout control. Instead, the composite template should author its own body with all placeholders explicitly placed.
- **Modifying base templates at load time:** Composition should never mutate the loaded base templates. The composer reads from bases but produces a new independent LoadedTemplate.
- **Composite-specific renderer logic:** The renderer must remain unaware of composition. If the composed LoadedTemplate needs special rendering, the composition is wrong -- fix the template/composer, not the renderer.
- **Implicit field inheritance:** All fields in the composed template must be explicitly accounted for -- either from bases (minus exclusions) or from the composite's own `fields` list. No hidden defaults.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parsing | Custom YAML parser | python-frontmatter (already used) | Handles YAML/markdown split reliably |
| Schema validation | Manual dict checking | Pydantic TemplateSchema (already used) | `extra="forbid"` catches typos, validators catch invalid references |
| Body placeholder validation | Custom regex scanning | Existing `validate_body_placeholders()` | Already validates field-to-body cross-references |

## Common Pitfalls

### Pitfall 1: Load Order Dependencies
**What goes wrong:** Composite template is loaded before its base templates, causing a "base not found" error even though the base exists.
**Why it happens:** File system ordering (sorted paths) may put `ct_tap.rpt.md` before `ct_thorax.rpt.md` alphabetically.
**How to avoid:** Two-pass loading -- first pass loads all non-composite templates, second pass composes composites. The registry already loads all paths sorted; just separate them.
**Warning signs:** Intermittent load failures on different file systems.

### Pitfall 2: TemplateSchema Validation Rejects Composites
**What goes wrong:** A composite template with `composable_from` and no `fields` (or minimal fields) fails TemplateSchema validation because `fields` requires at least one entry.
**Why it happens:** The existing `validate_fields_nonempty` validator requires `fields` to be non-empty. A composite that only draws fields from bases would have an empty `fields` list in its own frontmatter.
**How to avoid:** For composites, allow `fields` to be an empty list (the merged result will have fields). Either: (a) relax the validator when `composable_from` is present, or (b) require composites to always define at least one own field (CT TAP has `bones`, so this is naturally satisfied). Option (b) is simpler and avoids validator changes. The validator runs on the raw frontmatter before composition, so option (a) requires a conditional check.
**Warning signs:** `ValueError: At least one field is required` when loading a composite template.

### Pitfall 3: Field Name Collision After Exclusion
**What goes wrong:** Two base templates both define a field with the same name (e.g. `bones`), exclusion removes it from one base but not the other, leaving a duplicate.
**Why it happens:** The implementer forgets to check for duplicates AFTER exclusion is applied.
**How to avoid:** Post-merge duplicate check is a hard error (per D-25). Check field name uniqueness across all sources (remaining base fields + composite's own fields) after applying all exclusions.
**Warning signs:** Pydantic validation error on duplicate field names in the composed schema.

### Pitfall 4: Group Integrity Violation
**What goes wrong:** A field group from a base template loses a member due to `exclude_fields`, but the group is still carried forward with the remaining members.
**Why it happens:** The group carry-forward logic doesn't check whether all members survived exclusion.
**How to avoid:** Per D-11, if any member of a base group is excluded, the entire group is dropped. Check each base group's members against the exclusion set.
**Warning signs:** Group with fewer than 2 members (fails FieldGroup validator) or group referencing non-existent fields (fails TemplateSchema cross-validation).

### Pitfall 5: Validate Body After Composition, Not Before
**What goes wrong:** `validate_body_placeholders()` runs on the raw composite frontmatter fields vs. the composite body, which fails because the body references fields from bases.
**Why it happens:** The existing loader calls `validate_body_placeholders()` immediately after parsing. For composites, the full field list is only known after composition.
**How to avoid:** Skip body validation during initial parse for composites (when `composable_from is not None`). Run validation after composition against the merged field list and assembled body.
**Warning signs:** "Field 'lungs' defined in frontmatter but has no placeholder in template body" (false positive from base-only fields).

### Pitfall 6: Existing Tests Broken by Schema Changes
**What goes wrong:** Adding `composable_from` and `exclude_fields` to TemplateSchema causes existing test fixtures to fail because `extra="forbid"` rejects unknown keys.
**Why it happens:** It won't -- the new fields are optional with defaults of `None`, so existing YAML that doesn't include them will parse fine. But if the field name is misspelled or the type is wrong, `extra="forbid"` will catch it.
**How to avoid:** Verify all existing tests pass after schema changes before proceeding with composition logic. The new fields default to `None` and are truly optional.
**Warning signs:** Existing test failures after schema.py changes.

## Code Examples

### Composite Template YAML Frontmatter (CT TAP)
```yaml
---
study_name: "CT Thorax, Abdomen and Pelvis"
aliases:
  - "ct tap"
  - "ct thorax abdomen pelvis"
  - "ct thorax abdomen and pelvis"
  - "ct chest abdomen pelvis"
technique: "CT of the chest, abdomen and pelvis was performed with intravenous contrast."
interpolate_normal: false
impression: true
important_first: false
variant: "freeform"
composable_from:
  - "ct/ct_thorax.rpt.md"
  - "ct/ct_ap.rpt.md"
exclude_fields:
  ct/ct_thorax.rpt.md:
    - "bones"
    - "limited_abdomen"
  ct/ct_ap.rpt.md:
    - "bones"
    - "lung_bases"
fields:
  - name: "bones"
    normal: "No suspicious osseous lesion. No acute fracture."
groups: []
---
```

### Field Merge Algorithm (Pseudocode)
```python
def _merge_fields(
    resolved_bases: list[tuple[str, LoadedTemplate]],
    exclude_fields: dict[str, list[str]] | None,
    composite_fields: list[FieldDefinition],
) -> list[FieldDefinition]:
    """Merge fields from base templates + composite's own fields.

    Order: base1 fields (minus exclusions) + base2 fields (minus exclusions) + composite fields.
    Post-merge: check for duplicates (hard error).
    """
    excludes = exclude_fields or {}
    merged: list[FieldDefinition] = []
    seen_names: set[str] = set()

    for ref_path, base in resolved_bases:
        excluded_for_base = set(excludes.get(ref_path, []))
        for field in base.schema.fields:
            if field.name in excluded_for_base:
                continue
            if field.name in seen_names:
                raise TemplateLoadError(...)  # Collision after exclusion
            merged.append(field)
            seen_names.add(field.name)

    # Add composite's own fields
    for field in composite_fields:
        if field.name in seen_names:
            raise TemplateLoadError(...)  # Collision with base field
        merged.append(field)
        seen_names.add(field.name)

    return merged
```

### Group Merge Algorithm (Pseudocode)
```python
def _merge_groups(
    resolved_bases: list[tuple[str, LoadedTemplate]],
    exclude_fields: dict[str, list[str]] | None,
    merged_field_names: set[str],
    composite_groups: list[FieldGroup],
) -> list[FieldGroup]:
    """Carry forward base groups (drop if any member excluded), add composite groups."""
    excludes = exclude_fields or {}
    merged_groups: list[FieldGroup] = []

    for ref_path, base in resolved_bases:
        excluded_for_base = set(excludes.get(ref_path, []))
        for group in base.schema.groups:
            # D-11: Drop entire group if any member is excluded
            if any(m in excluded_for_base for m in group.members):
                continue
            # Also verify all members are in the final merged field set
            if all(m in merged_field_names for m in group.members):
                merged_groups.append(group)

    # Add composite's own groups
    merged_groups.extend(composite_groups)

    return merged_groups
```

### Exclude Fields Validation
```python
def _validate_exclusions(
    exclude_fields: dict[str, list[str]],
    resolved_bases: dict[str, LoadedTemplate],
) -> None:
    """Validate that excluded field names actually exist in their base templates (D-28)."""
    for ref_path, excluded_names in exclude_fields.items():
        if ref_path not in resolved_bases:
            raise TemplateLoadError(...)  # Base path not in composable_from
        base_field_names = {f.name for f in resolved_bases[ref_path].schema.fields}
        for name in excluded_names:
            if name not in base_field_names:
                raise TemplateLoadError(
                    ..., f"Excluded field '{name}' does not exist in {ref_path}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic templates | Composable templates from base parts | Phase 5 (this phase) | CT TAP no longer needs to duplicate all thorax and AP fields |
| Manual field lists in combined templates | Automatic field merge with exclusion | Phase 5 | Reduces maintenance burden; base template changes propagate |

## Open Questions

1. **Composite body: authored or generated?**
   - What we know: D-19 says composite body snippet defines placement. D-14 says layout is template-controlled.
   - Recommendation: The composite template authors its own complete body with all placeholders. This is the simplest approach, gives full layout control, and leverages existing `validate_body_placeholders()`. The guidance section is the only programmatically merged part (concatenated from bases per D-04).
   - Confidence: HIGH -- this aligns with all locked decisions.

2. **Schema validator relaxation for empty fields**
   - What we know: CT TAP defines its own `bones` field, so `fields` is non-empty. But a future composite might not define any own fields.
   - Recommendation: For Phase 5, require at least one field in the composite's own `fields` list. This avoids changing the validator. Revisit if needed.
   - Confidence: MEDIUM -- works for CT TAP but may need revisiting.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | python-backend/tests/ (no pytest.ini, uses defaults) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-01 | composable_from resolves base templates | unit | `python -m pytest tests/test_composer.py::test_composable_from_resolves_bases -x` | Wave 0 |
| COMP-02 | Fields and body sections concatenate in order | unit | `python -m pytest tests/test_composer.py::test_field_merge_order -x` | Wave 0 |
| COMP-03 | Flags come from composite, not bases | unit | `python -m pytest tests/test_composer.py::test_composite_flags_override_bases -x` | Wave 0 |
| COMP-04 | No duplicate fields after exclusion | unit | `python -m pytest tests/test_composer.py::test_exclude_fields_dedup -x` | Wave 0 |
| COMP-04 | Collision after exclusion is hard error | unit | `python -m pytest tests/test_composer.py::test_collision_after_exclusion_raises -x` | Wave 0 |
| SMPL-03 | CT TAP renders complete report | integration | `python -m pytest tests/test_production_templates.py::test_ct_tap_composite -x` | Wave 0 |
| D-11 | Group dropped when member excluded | unit | `python -m pytest tests/test_composer.py::test_group_dropped_when_member_excluded -x` | Wave 0 |
| D-26 | Circular composition detected | unit | `python -m pytest tests/test_composer.py::test_circular_composition_raises -x` | Wave 0 |
| D-27 | Missing base template raises error | unit | `python -m pytest tests/test_composer.py::test_missing_base_raises -x` | Wave 0 |
| D-28 | Excluding nonexistent field raises error | unit | `python -m pytest tests/test_composer.py::test_exclude_nonexistent_field_raises -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_composer.py` -- unit tests for compose_template() and helpers
- [ ] `tests/fixtures/composite/` -- fixture directory with minimal composite template + base templates
- [ ] Update `tests/test_production_templates.py` -- CT TAP integration tests
- [ ] Update `tests/conftest.py` -- composite fixture helpers

### Pre-existing Test Failure
Note: `test_ct_ap_optional_fields` currently fails because it expects only `vessels` as optional but Phase 3 added `mesentery` and `soft_tissues` as optional. This is a stale test assertion, not a code bug. Should be fixed as part of this phase or flagged for cleanup.

## Sources

### Primary (HIGH confidence)
- `python-backend/lib/templates/schema.py` -- Current TemplateSchema, FieldDefinition, FieldGroup models
- `python-backend/lib/templates/loader.py` -- Current LoadedTemplate, load_template(), discover_templates()
- `python-backend/lib/templates/registry.py` -- Current TemplateRegistry with _load_all(), alias index
- `python-backend/lib/templates/renderer.py` -- Current renderer (confirms no changes needed)
- `python-backend/rpt_templates/ct/ct_ap.rpt.md` -- CT AP base template (18 fields, 3 groups)
- `python-backend/rpt_templates/ct/ct_thorax.rpt.md` -- CT thorax base template (8 fields, 0 groups)
- `.planning/phases/05-composite-templates/05-CONTEXT.md` -- All locked decisions D-01 through D-28

### Secondary (MEDIUM confidence)
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` -- Phase 1 decisions on placeholder syntax, field groups, body structure
- `.planning/phases/02-template-loader-registry/02-CONTEXT.md` -- Phase 2 decisions on loader/registry patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, extends existing code
- Architecture: HIGH -- composition model is well-specified by locked decisions, existing code structure supports it cleanly
- Pitfalls: HIGH -- identified from direct code inspection of validators, load order, and cross-validation logic

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable domain, no external dependencies)
