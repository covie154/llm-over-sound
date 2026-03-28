# Phase 1: Template Schema & Data Model - Research

**Researched:** 2026-03-28
**Domain:** Pydantic data modeling, YAML frontmatter parsing, radiology template schema design
**Confidence:** HIGH

## Summary

Phase 1 defines the Pydantic validation models and YAML+markdown template file format for radiology report templates. The core deliverables are: (1) a Pydantic model hierarchy for template metadata (study name, aliases, ordered fields with normal text, field groups with joint normal text, technique section, guidance section), (2) a dynamic Pydantic model factory for LLM findings output constrained to a template's field list, (3) a study type classification output model, and (4) a minimal test fixture template proving end-to-end validation.

The stack is deliberately minimal: `python-frontmatter` 1.1.0 for YAML+markdown parsing and `pydantic` 2.11.7 for schema validation. Both are verified available. Pydantic's `create_model()` API has been tested and confirmed working for dynamic model generation with `Optional[str]` fields defaulting to `None`. Cross-validation via `model_validator(mode='after')` is confirmed working for group-member-in-fields checks.

**Primary recommendation:** Build a layered Pydantic model hierarchy (FieldDefinition -> FieldGroup -> TemplateSchema) with strict validation (`extra='forbid'`), use `create_model()` for dynamic findings models, and place all models in a single `python-backend/lib/template_schema.py` module.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Template placeholders use double-brace syntax: `{{field_name}}`
- D-02: Measurement placeholders use colon-namespaced type prefix: `{{measurement:liver_span_cm}}`
- D-03: Technique placeholders use colon-namespaced type prefix: `{{technique:phase}}`, `{{technique:contrast}}`
- D-04: All placeholder types share the `{{...}}` wrapper -- type is distinguished by the colon prefix (no prefix = text field, `measurement:` = required measurement, `technique:` = technique variable)
- D-05: Field groups defined as a `groups` list in YAML frontmatter. Each group has `name`, `members` (list of field names), and `joint_normal` text
- D-06: Each field in `members` must exist in the `fields` list (Pydantic cross-validation)
- D-07: A field can belong to at most one group
- D-08: Partial combination text via template-authored partials, missing partials fall back to individual field normal text
- D-10: No cap on group size
- D-11: YAML list order is canonical report order -- no explicit `order` integer per field
- D-12: Sex-dependent fields with `sex` tag inline in fields list (e.g. `{name: uterus, sex: female, normal: '...'}`)
- D-13: Guidance section is free-text markdown in the template body (`## Guidance` section), not structured YAML
- D-14: Guidance is LLM-only context -- stripped from rendered report output
- D-15: Guidance section is optional
- D-16: Findings model is a dynamic Pydantic model generated per template using `create_model()`
- D-17: Field type is `Optional[str]` -- `None` means unreported
- D-18: Schema stores final strings only, no verbatim tracking
- D-20: Single Pydantic model per template covers both technique and anatomical findings
- D-21: Phase 1 defines both the study type classification output model and the findings extraction model
- D-22: Markdown H2 headers for report sections: `## CLINICAL HISTORY`, `## TECHNIQUE`, `## COMPARISON`, `## FINDINGS`, `## COMMENT`
- D-23: One placeholder or group per line in the template body
- D-24: Renderer preserves template whitespace exactly
- D-25: Field groups listed as individual field placeholders in body, renderer collapses them
- D-26: Strict Pydantic validation: `extra: 'forbid'`
- D-27: Error messages must be clear and actionable
- D-28: Cross-validation between frontmatter fields and body placeholders (warn/error)
- D-29: `__NOT_DOCUMENTED__` for everything not mentioned in draft
- D-31: Minimal test fixture template in tests/fixtures directory

### Claude's Discretion
- Internal Pydantic model class structure and naming
- How partial combination texts are stored in the group YAML (e.g. `partials` dict keyed by frozenset of normal members, or a list of `{members: [...], text: "..."}`)
- Error message formatting details
- Test fixture field names and content

### Deferred Ideas (OUT OF SCOPE)
- LLM-generated partial normal text for groups (D-09)
- Clinical-history-aware prompting for pertinent negatives
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TMPL-01 | Template files use YAML frontmatter + markdown body format, parseable by python-frontmatter | python-frontmatter 1.1.0 API: `frontmatter.load()` / `frontmatter.loads()` returns Post object with `.metadata` dict and `.content` string |
| TMPL-02 | Each template defines organ-level fields with ordered field list preserving craniocaudal or logical reporting order | Pydantic `list[FieldDefinition]` preserves insertion order; YAML list order is canonical per D-11 |
| TMPL-03 | Each field stores a default normal text string | `FieldDefinition.normal: str` field in Pydantic model |
| TMPL-07 | Templates support field groups with joint normal text | `FieldGroup` model with `name`, `members`, `joint_normal`, `partials`; cross-validated against fields list via `model_validator` |
| TMPL-08 | Templates include a technique section with boilerplate text and optional placeholders | `technique` field in frontmatter schema with `text: str` and optional placeholder extraction from body `## TECHNIQUE` section |
| TMPL-09 | Templates include a guidance section with clinical reference information | Free-text `## Guidance` section in markdown body per D-13; parsed and stored but optional per D-15 |
| FWRK-03 | Pydantic models define the template metadata schema and validate frontmatter at load time | `TemplateSchema` model with `extra='forbid'`, `model_validator` for cross-validation |
| FWRK-04 | Pydantic models define the LLM findings output schema for constrained structured output | `create_findings_model()` factory function using `pydantic.create_model()` with `Optional[str]` fields |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.11.7 | Schema validation, dynamic model creation, LLM structured output | Already installed; v2 `create_model()` and `model_validator` verified working on this machine |
| python-frontmatter | 1.1.0 | Parse YAML frontmatter + markdown body from template files | De facto standard for frontmatter parsing; only dependency is PyYAML (already installed) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.3.4 | Unit testing for schema validation | Already installed; needed for Wave 0 test infrastructure |
| pyyaml | 6.0.2 | YAML parsing (transitive dep of python-frontmatter) | Already installed; no action needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-frontmatter | Manual YAML splitting with `yaml.safe_load()` | python-frontmatter handles edge cases (multiple `---` delimiters, empty frontmatter); not worth hand-rolling |
| Pydantic `create_model()` | TypedDict or dataclass | Loses validation, JSON schema generation, and LLM structured output compatibility |

**Installation:**
```bash
python -m pip install python-frontmatter
```

**Version verification:** Pydantic 2.11.7 confirmed installed via `python -m pip show pydantic`. python-frontmatter 1.1.0 confirmed available via dry-run install.

## Architecture Patterns

### Recommended Project Structure
```
python-backend/
  lib/
    template_schema.py    # All Pydantic models (FieldDefinition, FieldGroup, TemplateSchema, etc.)
    template_parser.py    # Parse frontmatter+body, extract sections, create validated schema (Phase 2 prep)
    pipeline.py           # Existing -- LLMPipeline stubs
  rpt_templates/          # Existing empty dir -- template files go here
  tests/
    __init__.py
    conftest.py           # Shared fixtures, template loading helpers
    fixtures/
      sample_template.md  # Minimal test fixture (D-31)
    test_template_schema.py  # Schema validation tests
```

### Pattern 1: Layered Pydantic Model Hierarchy
**What:** Build models bottom-up: FieldDefinition -> FieldGroup -> TemplateSchema. Each layer validates its own concerns, TemplateSchema adds cross-model validation.
**When to use:** Always -- this is the core deliverable.
**Example:**
```python
# Source: Verified against Pydantic 2.11.7 on this machine
from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional

class FieldDefinition(BaseModel):
    """A single template field (organ-level finding)."""
    model_config = ConfigDict(extra='forbid')

    name: str
    normal: str
    sex: Optional[str] = None  # 'male', 'female', or None for universal

class GroupPartial(BaseModel):
    """A pre-authored partial normal text for a subset of group members."""
    model_config = ConfigDict(extra='forbid')

    members: list[str]  # subset of group members that are normal
    text: str           # combined normal text for this subset

class FieldGroup(BaseModel):
    """A group of fields with joint normal text."""
    model_config = ConfigDict(extra='forbid')

    name: str
    members: list[str]
    joint_normal: str
    partials: list[GroupPartial] = []

class TemplateSchema(BaseModel):
    """Complete template metadata from YAML frontmatter."""
    model_config = ConfigDict(extra='forbid')

    study_name: str
    aliases: list[str]
    fields: list[FieldDefinition]
    groups: list[FieldGroup] = []
    technique: str  # boilerplate technique text
    # Flags for later phases (defined in schema now, used in Phase 4)
    interpolate_normal: bool = False
    impression: bool = True
    important_first: bool = False

    @model_validator(mode='after')
    def validate_groups(self):
        field_names = {f.name for f in self.fields}
        seen_in_groups = set()
        for group in self.groups:
            for member in group.members:
                if member not in field_names:
                    raise ValueError(
                        f"Group '{group.name}' references field '{member}' "
                        f"which is not in the fields list. "
                        f"Available fields: {sorted(field_names)}"
                    )
                if member in seen_in_groups:
                    raise ValueError(
                        f"Field '{member}' appears in multiple groups. "
                        f"Each field can belong to at most one group (D-07)."
                    )
                seen_in_groups.add(member)
        return self
```

### Pattern 2: Dynamic Findings Model Factory
**What:** A function that takes a TemplateSchema and returns a Pydantic model class with one `Optional[str]` field per template field. Enables LLM structured output constraints.
**When to use:** Every time a template is loaded and findings extraction is needed.
**Example:**
```python
# Source: Verified against Pydantic 2.11.7 create_model() on this machine
from pydantic import create_model
from typing import Optional

def create_findings_model(schema: TemplateSchema) -> type[BaseModel]:
    """Generate a dynamic Pydantic model from a template's field list.

    Each template field becomes an Optional[str] field defaulting to None.
    None means unreported (-> __NOT_DOCUMENTED__ or normal text depending on config).
    Technique fields from the template body are also included.
    """
    field_definitions = {}
    for field_def in schema.fields:
        # Use field name as model field name
        field_definitions[field_def.name] = (Optional[str], None)

    # Add technique placeholders if any
    # (technique placeholders extracted from body in parsing step)

    model = create_model(
        f"{schema.study_name.replace(' ', '')}Findings",
        **field_definitions,
    )
    return model
```

### Pattern 3: Study Type Classification Model
**What:** A static Pydantic model constraining LLM study type output to known aliases.
**When to use:** Pipeline stage 1 -- the LLM must pick from a closed set.
**Example:**
```python
from pydantic import BaseModel
from enum import Enum

def create_study_type_enum(all_aliases: list[str]) -> type[Enum]:
    """Create an Enum of all known study type aliases for LLM output constraint."""
    return Enum('StudyType', {alias: alias for alias in all_aliases})

class StudyTypeClassification(BaseModel):
    """LLM output model for stage 1: study type classification."""
    study_type: str  # constrained to known aliases at runtime via enum or Literal
    confidence: float  # 0.0-1.0, for future threshold-based clarification requests
```

### Anti-Patterns to Avoid
- **Nested Pydantic models in frontmatter YAML:** Do not require the YAML author to write Pydantic-aware structures. The YAML is simple dicts/lists; Pydantic validates after parsing.
- **Storing template body in the Pydantic model:** The body is markdown text, not structured data. Store it separately as a plain string. The schema validates frontmatter only.
- **Using `model_config = ConfigDict(extra='allow')` on template schema:** Per D-26, use `extra='forbid'` to catch typos and invalid keys in template YAML.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parsing | Custom `---` delimiter splitting | `python-frontmatter` | Handles edge cases (empty frontmatter, multiple delimiters, encoding) |
| Schema validation | Manual dict key checking | Pydantic `BaseModel` with `extra='forbid'` | Type coercion, error messages, JSON schema generation for free |
| Dynamic model creation | Runtime class construction with `type()` | `pydantic.create_model()` | Proper validation, JSON schema, serialization all handled |
| Cross-field validation | Post-parse manual checks | `@model_validator(mode='after')` | Integrates with Pydantic error reporting, runs automatically |

**Key insight:** Pydantic 2.x handles all validation complexity including cross-field checks, dynamic model creation, and actionable error messages. The only custom logic needed is the specific validation rules (group members in fields, single-group membership, placeholder-field cross-checks).

## Common Pitfalls

### Pitfall 1: YAML String Quoting
**What goes wrong:** YAML values like `normal: The liver is normal in size and echogenicity.` can break if they contain colons, special characters, or start with certain characters.
**Why it happens:** YAML interprets unquoted values contextually. A colon followed by space (`: `) starts a mapping. Values starting with `*`, `&`, `!`, `%`, `@` have special meaning.
**How to avoid:** Document that all `normal` text values in template YAML should be quoted strings (single or double quotes). Add a note in the test fixture and template authoring guidance.
**Warning signs:** Pydantic validation errors on fields that look correct in the YAML file.

### Pitfall 2: Field Name Collisions with Python Reserved Words
**What goes wrong:** Template field names like `class` or `return` cannot be Python identifiers, which breaks `create_model()`.
**Why it happens:** `create_model()` uses field names as keyword arguments.
**How to avoid:** Validate field names against Python reserved words in the schema validator. Use a regex pattern: `^[a-z][a-z0-9_]*$` for field names (lowercase snake_case, must start with letter).
**Warning signs:** `SyntaxError` or `TypeError` when calling `create_model()`.

### Pitfall 3: Group Partial Combinatorial Explosion
**What goes wrong:** A group with N members has 2^N possible partial combinations. Template authors might try to enumerate all of them.
**Why it happens:** Misunderstanding the design. Partials are optional and only needed for common subsets.
**How to avoid:** Document clearly: partials are optional. Missing partials fall back to individual field normal text (D-08). Authors only write the combinations they actually need.
**Warning signs:** Groups with more than 3-4 partial entries -- probably over-engineering.

### Pitfall 4: Technique Section Confusion
**What goes wrong:** Technique section has two aspects: boilerplate text in frontmatter AND placeholders in the body. Mixing them up leads to incomplete models.
**Why it happens:** D-03 defines technique placeholders `{{technique:phase}}` in the body, but the technique also needs static boilerplate text.
**How to avoid:** Store technique boilerplate in frontmatter, technique placeholders are extracted from the body's `## TECHNIQUE` section during parsing. The dynamic findings model includes technique placeholder fields alongside anatomical fields (D-20).
**Warning signs:** Technique text missing from rendered output, or technique placeholders not being filled.

### Pitfall 5: Body-Frontmatter Placeholder Mismatch
**What goes wrong:** A field defined in frontmatter has no matching `{{field_name}}` in the body, or vice versa. The report renders incorrectly.
**Why it happens:** Template editing -- adding/removing fields from one place but forgetting the other.
**How to avoid:** Cross-validation (D-28) implemented as a `model_validator` or a separate validation function that takes both the schema and parsed body. Emit warnings or errors listing mismatches.
**Warning signs:** `__NOT_DOCUMENTED__` appearing in unexpected places, or placeholder tokens appearing literally in rendered output.

## Code Examples

### Loading and Validating a Template File
```python
# Source: python-frontmatter docs + Pydantic 2.11.7 verified API
import frontmatter

def load_template(filepath: str) -> tuple[TemplateSchema, str]:
    """Load a template file, validate frontmatter, return schema and body.

    Args:
        filepath: Path to the markdown template file.

    Returns:
        Tuple of (validated TemplateSchema, markdown body string).

    Raises:
        pydantic.ValidationError: If frontmatter fails validation.
    """
    post = frontmatter.load(filepath)
    schema = TemplateSchema(**post.metadata)  # Validates and raises on error
    body = post.content
    return schema, body
```

### Sample Template YAML Frontmatter
```yaml
---
study_name: "CT Abdomen Pelvis"
aliases:
  - "ct abdomen pelvis"
  - "ct ap"
  - "ct abdomen and pelvis"
technique: "CT of the abdomen and pelvis was performed with intravenous contrast."
interpolate_normal: false
impression: true
important_first: false
fields:
  - name: "liver"
    normal: "The liver is normal in size and attenuation. No focal lesion."
  - name: "gallbladder_biliary"
    normal: "The gallbladder is unremarkable. No biliary dilatation."
  - name: "spleen"
    normal: "The spleen is normal in size."
  - name: "adrenals"
    normal: "The adrenal glands are unremarkable."
  - name: "pancreas"
    normal: "The pancreas is normal in morphology and enhancement."
  - name: "uterus"
    sex: "female"
    normal: "The uterus is normal in size and morphology."
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

### Dynamic Findings Model Usage
```python
# After loading template and creating findings model:
FindingsModel = create_findings_model(schema)

# LLM output can be validated:
findings = FindingsModel(
    liver="Hepatomegaly. The liver measures 18cm in craniocaudal dimension.",
    gallbladder_biliary=None,  # Not mentioned -> __NOT_DOCUMENTED__
    spleen=None,
    adrenals=None,
    pancreas=None,
)

# JSON schema for LLM structured output constraint:
json_schema = FindingsModel.model_json_schema()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `validator` | Pydantic v2 `field_validator` / `model_validator` | Pydantic 2.0 (2023) | Different decorator syntax, `mode='before'`/`'after'` parameter |
| Pydantic v1 `Config` inner class | Pydantic v2 `model_config = ConfigDict(...)` | Pydantic 2.0 (2023) | Class-level attribute instead of inner class |
| `Optional[X]` requires `from typing import Optional` | `X | None` syntax (Python 3.10+) | Python 3.10 (2021) | Cleaner syntax, but `Optional[str]` still works and is more explicit for `create_model()` |

**Deprecated/outdated:**
- Pydantic v1 `@validator` decorator: replaced by `@field_validator` in v2
- Pydantic v1 `schema()` method: replaced by `model_json_schema()` in v2
- `python-frontmatter` < 1.0: current 1.1.0 is stable and maintained

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | none -- see Wave 0 |
| Quick run command | `python -m pytest python-backend/tests/ -x -q` |
| Full suite command | `python -m pytest python-backend/tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TMPL-01 | YAML frontmatter + markdown body parsed by python-frontmatter | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_load_template_file -x` | No -- Wave 0 |
| TMPL-02 | Ordered field list with organ-level fields | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_field_order_preserved -x` | No -- Wave 0 |
| TMPL-03 | Each field stores default normal text | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_field_normal_text -x` | No -- Wave 0 |
| TMPL-07 | Field groups with joint normal text validate correctly | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_field_groups -x` | No -- Wave 0 |
| TMPL-08 | Technique section with boilerplate and placeholders | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_technique_section -x` | No -- Wave 0 |
| TMPL-09 | Guidance section parsed from body | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_guidance_section -x` | No -- Wave 0 |
| FWRK-03 | Pydantic models validate frontmatter at load time | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_strict_validation -x` | No -- Wave 0 |
| FWRK-04 | Dynamic findings model created from template fields | unit | `python -m pytest python-backend/tests/test_template_schema.py::test_findings_model -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest python-backend/tests/ -x -q`
- **Per wave merge:** `python -m pytest python-backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `python-backend/tests/__init__.py` -- package init
- [ ] `python-backend/tests/conftest.py` -- shared fixtures (template loading helpers, fixture paths)
- [ ] `python-backend/tests/fixtures/sample_template.md` -- minimal test fixture (D-31)
- [ ] `python-backend/tests/test_template_schema.py` -- all schema validation tests
- [ ] Framework install: `python -m pip install python-frontmatter` -- python-frontmatter not yet installed

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All code | Yes | 3.13.5 | -- |
| pydantic | Schema validation | Yes | 2.11.7 | -- |
| python-frontmatter | YAML+markdown parsing | No (not installed) | 1.1.0 (available) | Install via pip |
| pytest | Testing | Yes | 8.3.4 | -- |
| PyYAML | Transitive dep of frontmatter | Yes | 6.0.2 | -- |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- `python-frontmatter` 1.1.0: Not installed but available. Install with `python -m pip install python-frontmatter`

## Open Questions

1. **Partial storage format for groups**
   - What we know: D-08 requires template-authored partial combination texts. Partials need to map a subset of normal members to combined text.
   - What's unclear: Best YAML representation -- a list of `{members: [...], text: "..."}` objects (recommended) vs a dict keyed by sorted comma-separated member names.
   - Recommendation: Use list of objects (as shown in code examples). More readable in YAML, easier to validate in Pydantic, and order-independent matching can happen in code.

2. **Technique placeholder extraction scope**
   - What we know: D-20 says single Pydantic model covers both technique and anatomical findings. D-03 defines `{{technique:phase}}` syntax.
   - What's unclear: Whether technique placeholders should be extracted from the body during schema creation (Phase 1) or during template parsing (Phase 2).
   - Recommendation: Phase 1 defines the schema structure. Actual body parsing and placeholder extraction is Phase 2 work. The findings model factory should accept an optional list of technique field names.

3. **Body cross-validation timing**
   - What we know: D-28 requires cross-validation between frontmatter fields and body placeholders.
   - What's unclear: Whether this belongs in the TemplateSchema model validator (requires body access) or as a separate validation function.
   - Recommendation: Separate validation function that takes (schema, body) -- keeps the Pydantic model focused on frontmatter validation. The function can be called during template loading in Phase 2.

## Project Constraints (from CLAUDE.md)

- Python naming: snake_case functions/variables, PascalCase classes, ALL_CAPS constants
- Type hints on function signatures
- Docstrings on modules, classes, and public functions
- Modules live under `python-backend/lib/` with exports in `__init__.py`
- Template files live in `python-backend/rpt_templates/`
- The LLM must never fabricate findings -- `__NOT_DOCUMENTED__` is the mandatory sentinel
- `interpolate_normal` defaults to `false`
- All extraction logged for medico-legal audit trail
- AHK v2 syntax only (not relevant to Phase 1 but noted)

## Sources

### Primary (HIGH confidence)
- Pydantic 2.11.7 -- `create_model()`, `model_validator`, `ConfigDict(extra='forbid')` all verified by running on this machine
- python-frontmatter 1.1.0 -- [PyPI](https://pypi.org/project/python-frontmatter/), [GitHub](https://github.com/eyeseast/python-frontmatter), [Docs](https://python-frontmatter.readthedocs.io/)
- Existing codebase: `python-backend/lib/pipeline.py`, `python-backend/lib/__init__.py`

### Secondary (MEDIUM confidence)
- Prior project research: `.planning/research/SUMMARY.md`, `.planning/research/ARCHITECTURE.md`

### Tertiary (LOW confidence)
- None -- all critical claims verified against installed packages

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- both packages verified installed/available on this machine with correct versions
- Architecture: HIGH -- Pydantic model patterns verified by running code; model hierarchy follows standard Pydantic v2 practices
- Pitfalls: HIGH -- YAML quoting, field name collisions, and cross-validation issues are well-documented Pydantic/YAML concerns

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable domain, no fast-moving dependencies)
