# Architecture

**Domain:** Composable radiology report template system
**Researched:** 2026-03-28

## Component Overview

### Four-Component Architecture

**1. TemplateRegistry** (startup index)
- Scans `rpt_templates/` directory recursively at startup
- Parses YAML frontmatter from each `.md` file
- Builds alias-to-filepath index for fast study type lookup
- Validates no duplicate aliases across templates
- Detects `composable_from` references and validates they resolve

**2. TemplateResolver** (parse + compose)
- Given a study type string, resolves to a `ParsedTemplate`
- For base templates: parses frontmatter + body, returns `ParsedTemplate`
- For composite templates: loads referenced base templates, concatenates fields and body sections
- Uses `python-frontmatter` for parsing
- Validates against Pydantic schema on load

**3. ParsedTemplate** (frozen dataclass)
- Immutable data structure representing a fully resolved template
- Contains: metadata (study name, aliases, flags), ordered field list, body template string
- For composite templates: fields and body are already merged
- Used by both extraction (Stage 3) and rendering (Stage 4)

**4. ReportRenderer** (deterministic assembly)
- Takes `ParsedTemplate` + extracted findings dict + runtime flags
- Applies `interpolate_normal` logic (per-template default, per-request override)
- Filters sex-dependent fields based on context
- Handles grouped organ fields (joint normal text when all members normal)
- Replaces placeholders in body template with findings text
- Pure string manipulation, no LLM involvement

## Data Flow

### Startup (one-time)
```
rpt_templates/**/*.md
    |
    v
TemplateRegistry.build_index()
    |
    v
alias_index: dict[str, Path]  # "CT AP" -> rpt_templates/ct/ct_abdomen_pelvis.md
```

### Per-Request (5-stage pipeline)
```
Draft input + study type
    |
    v
Stage 1: Study classification (LLM) --> study_type string
    |
    v
Stage 2: TemplateRegistry.lookup(study_type) --> file path
         TemplateResolver.load(path) --> ParsedTemplate
    |
    v
Stage 3: Findings extraction (LLM)
         Input: draft text + ParsedTemplate.fields (as JSON schema)
         Output: dict[field_name, str]  # extracted text or "__NOT_DOCUMENTED__"
    |
    v
Stage 4: ReportRenderer.render(ParsedTemplate, findings, runtime_flags)
         Output: formatted report string
    |
    v
Stage 5: Impression generation (LLM)
         Input: rendered findings section
         Output: impression/conclusion text
    |
    v
Final report = technique + comparison + findings + impression
```

## Data Model

### Template File Format
```yaml
---
study_name: "CT Abdomen and Pelvis"
aliases: ["CT AP", "CTAP", "CT abd pelvis", "CT abdomen pelvis"]
modality: "CT"
body_region: "abdomen_pelvis"
impression: true
interpolate_normal: false
fields:
  - name: liver
    label: "Liver"
    default_normal: "No suspicious hepatic lesion is noted."
    type: text
  - name: gallbladder_biliary
    label: "Gallbladder and Biliary Tree"
    default_normal: "The gallbladder is unremarkable. The biliary tree is not dilated."
    type: text
  - name: cbd_measurement
    label: "CBD Measurement"
    type: measurement
    required: true
  - name: prostate
    label: "Prostate"
    default_normal: "The prostate is unremarkable."
    type: text
    sex: M
  - name: uterus_ovaries
    label: "Uterus and Ovaries"
    default_normal: "The uterus and ovaries are unremarkable."
    type: text
    sex: F
groups:
  - name: solid_organs
    fields: [spleen, adrenals, pancreas]
    normal_text: "The spleen, adrenal glands and pancreas are unremarkable."
---
{findings_body}
```

### Python Data Model (Pydantic)
```python
class FieldDefinition(BaseModel):
    name: str
    label: str
    default_normal: str | None = None
    type: Literal["text", "measurement"] = "text"
    required: bool = False
    sex: Literal["M", "F"] | None = None

class FieldGroup(BaseModel):
    name: str
    fields: list[str]  # field names
    normal_text: str

class TemplateMetadata(BaseModel):
    study_name: str
    aliases: list[str]
    modality: str
    body_region: str
    impression: bool = True
    interpolate_normal: bool = False
    fields: list[FieldDefinition]
    groups: list[FieldGroup] = []
    composable_from: list[str] | None = None

class ParsedTemplate:
    metadata: TemplateMetadata
    body: str  # markdown template body with placeholders
```

### Three Value States per Field
1. **Reported**: Radiologist provided a finding → use extracted text verbatim
2. **Normal default**: Field unreported + `interpolate_normal=true` → use stored `default_normal`
3. **Not documented**: Field unreported + `interpolate_normal=false` → `__NOT_DOCUMENTED__`

## Composite Template Design

### Reference-Based Concatenation
Combined templates reference base templates by relative path:
```yaml
---
study_name: "CT Thorax, Abdomen and Pelvis"
aliases: ["CT TAP", "CT chest abdomen pelvis"]
composable_from:
  - "ct/ct_thorax.md"
  - "ct/ct_abdomen_pelvis.md"
impression: true
interpolate_normal: false
---
```

### Resolution Rules
1. Combined template has **no body** and **no fields** of its own
2. Fields concatenated in order: thorax fields first, then abdomen/pelvis fields
3. Body sections concatenated with separator between regions
4. Flags (impression, interpolate_normal) come from the combined template, not base templates
5. **Single-level depth only** -- no nested composition (CT TAP references base templates, not other combined templates)

### Boundary Field Ownership
When templates overlap at anatomical boundaries:
- "Imaged lung bases" belongs to the **abdomen/pelvis** template (not thorax)
- "Upper abdomen" belongs to the **abdomen/pelvis** template (not thorax)
- Each base template documents which boundary fields it owns
- Combined template inherits all fields; no deduplication needed if ownership is clear

## Key Patterns

### Lazy Composite Resolution
Don't resolve composite templates at startup. Build the alias index, but resolve `composable_from` references only when the template is actually requested. This keeps startup fast and avoids circular reference issues.

### Section Extraction for Composition
Template bodies use section markers (`## Thorax`, `## Abdomen and Pelvis`) that the compositor uses to extract and concatenate sections from base templates.

### Deterministic Rendering with Fallback Chain
For each field in the template:
1. If field has an extracted finding → use it
2. If field is in a group where all members are normal → use group normal text (skip individual)
3. If field has no finding + interpolate_normal=true → use field's default_normal
4. If field has no finding + interpolate_normal=false → `__NOT_DOCUMENTED__`

## Anti-Patterns to Avoid

1. **Templates as code**: Templates should contain no logic. All conditional behavior lives in the Python renderer.
2. **Deep inheritance**: No template should extend another template that extends another. Single-level composition only.
3. **LLM-generated normals**: The LLM should never write normal findings. Normal text comes from the template, authored by a radiologist.
4. **Mutable template state**: ParsedTemplate must be immutable. Use deepcopy when composing to avoid mutation of cached base templates.

## Suggested Build Order

```
1. Data model (Pydantic models for fields, groups, metadata)
   ↓
2. Template loader (python-frontmatter parsing + Pydantic validation)
   ↓
3. Template registry (alias index, startup scan)
   ↓
4. Base template rendering (placeholder replacement, interpolate_normal)
   ↓
5. Template compositor (composable_from resolution, field/body concatenation)
   ↓
6. Pipeline integration (wire into existing 5-stage pipeline)
```

Each step is independently testable. Steps 1-4 work without composition support. Step 5 adds composition. Step 6 wires everything into the existing backend.

## Directory Structure

```
rpt_templates/
  ct/
    ct_abdomen_pelvis.md
    ct_thorax.md
    ct_thorax_abdomen_pelvis.md  # composite
  us/
    us_hbs.md
  mri/
    (future)

python-backend/
  lib/
    templates/
      __init__.py
      models.py          # Pydantic data models
      loader.py           # frontmatter parsing
      registry.py         # alias index
      compositor.py       # composite template resolution
      renderer.py         # report rendering
```

## Sources

- [Herts et al., AJR 2019](https://ajronline.org/doi/10.2214/AJR.18.20368)
- [RSNA RadReport](https://www.rsna.org/practice-tools/data-tools-and-standards/radreport-reporting-templates)
- [python-frontmatter docs](https://python-frontmatter.readthedocs.io/en/latest/)
- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
