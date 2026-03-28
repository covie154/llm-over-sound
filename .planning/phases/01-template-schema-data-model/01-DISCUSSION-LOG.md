# Phase 1: Template Schema & Data Model - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-28
**Phase:** 01-template-schema-data-model
**Areas discussed:** Placeholder syntax, Field group design, Guidance section structure, LLM output schema, Template body structure, Validation strictness, Sample template in Phase 1

---

## Placeholder Syntax

| Option | Description | Selected |
|--------|-------------|----------|
| `{{field_name}}` | Double-brace Jinja/Mustache style. No markdown conflicts. Familiar. | ✓ |
| `{field_name}` | Single-brace Python format style. Simpler but markdown conflict risk. | |
| `__field_name__` | Dunder style. No markdown conflicts but less visually distinct. | |

**User's choice:** `{{field_name}}` — double-brace syntax
**Notes:** None

### Measurement Placeholders

| Option | Description | Selected |
|--------|-------------|----------|
| `{{_measurement_}}` with underscore prefix | Same brace syntax but _ prefix signals required measurement. | |
| `{{measurement:field_name}}` | Colon-namespaced type prefix. More explicit. | ✓ |
| Same as regular fields | No special syntax. Mark as required in YAML instead. | |

**User's choice:** `{{measurement:field_name}}` — colon-namespaced
**Notes:** None

### Technique Placeholders

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholders for variable parts | e.g. `{{technique:phase}}`, `{{technique:contrast}}`. More flexible. | ✓ |
| Static text block | Fixed boilerplate per template. Simpler but less adaptable. | |

**User's choice:** Placeholders for variable technique parts
**Notes:** None

---

## Field Group Design

### Group Representation in YAML

| Option | Description | Selected |
|--------|-------------|----------|
| Nested group object | `groups` key with named groups listing members and joint normal text. | ✓ |
| Inline group annotation | Each field has a `group` key. Flatter but scattered. | |
| Separate groups in body | Groups in markdown body. Readable but hard to validate. | |

**User's choice:** Nested group object
**Notes:** User asked for detailed explanation of how nested groups work before deciding. Provided full example with YAML structure and render-time behavior.

### Partial Group Expansion

| Option | Description | Selected |
|--------|-------------|----------|
| Individual normal text per field | Each normal member uses its own normal field. | |
| Partial joint text | Dynamically construct joint phrase for normal members. | ✓ |
| Always individual when broken | Every member renders individually. | |

**User's choice:** Partial joint text for remaining normal members
**Notes:** User specifically asked about the scenario where one group member is abnormal and others are normal (e.g. splenomegaly with normal adrenals and pancreas).

### Partial Text Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Template-authored partials | Author pre-writes partial combinations in YAML. | ✓ |
| Auto-generated from field names | Renderer constructs phrases dynamically. | |
| LLM-generated at render time | LLM composes partial normal sentence. | |

**User's choice:** Template-authored partials first, with LLM-generated as noted fallback
**Notes:** User said "Let's go with 1, but keep 3 in mind. I'd like to try how 1 sounds first and switch to 3 if it doesn't work."

### Group Size Cap

| Option | Description | Selected |
|--------|-------------|----------|
| Cap at 3-4 members | Keeps partial combinations manageable. | |
| No cap, author writes what they need | Missing partials fall back to individual normal text. | ✓ |
| You decide | Claude's discretion. | |

**User's choice:** No cap — author writes what they need
**Notes:** None

### Field Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| YAML list order is canonical | Position in list defines report order. | ✓ |
| Explicit order integer | Each field has `order: N`. | |

**User's choice:** YAML list order is canonical
**Notes:** None

### Sex-Dependent Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Both variants with sex tag | Inline in fields list with sex: male/female. | ✓ |
| Conditional block | Separate sex_dependent section. | |
| You decide | Claude's discretion. | |

**User's choice:** Both variants inline with sex tag
**Notes:** None

### Abnormal Field Text Handling

**User's question:** "For abnormal fields, the user's text may range from a complete sentence to very brief notes. How is this handled?"

**Response:** Schema stores final string per field. Sentence expansion happens in LLM extraction (Phase 3) before data enters the Pydantic model. No verbatim tracking needed in the schema.

**User's confirmation:** "No need to cover in the schema. The sentence expansion should already take place before the data gets entered into the schema."

---

## Guidance Section Structure

### Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Structured YAML with categories | Machine-parseable, Pydantic-validatable. | |
| Free-text markdown section | `## Guidance` in body. Natural for radiologists. | ✓ |
| Hybrid | Structured dimensions + free-text notes. | |

**User's choice:** Free-text markdown in the body
**Notes:** None

### Inclusion in Output

| Option | Description | Selected |
|--------|-------------|----------|
| LLM context only — stripped | Injected into LLM prompt, never in rendered report. | ✓ |
| Included as reference section | Appended to report for radiologist reference. | |
| You decide | Claude's discretion. | |

**User's choice:** LLM context only — stripped from output
**Notes:** None

### Required or Optional

| Option | Description | Selected |
|--------|-------------|----------|
| Required | Every template must have guidance. | |
| Optional | Validated if present, not required. | ✓ |

**User's choice:** Optional
**Notes:** None

---

## LLM Output Schema

### Model Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic Pydantic model per template | `create_model()` from field list. Enables structured output. | ✓ |
| Generic dict with post-hoc validation | Dict[str, str] validated after the fact. | |
| You decide | Claude's discretion. | |

**User's choice:** Dynamic Pydantic model per template
**Notes:** None

### Field Type

| Option | Description | Selected |
|--------|-------------|----------|
| `str \| None` per field | None = unreported, string = finding. | ✓ |
| Custom FindingValue type | Union type with explicit states. | |
| str with sentinel values | Magic string `__NOT_DOCUMENTED__`. | |

**User's choice:** `Optional[str]` — None for unreported
**Notes:** None

### Importance Flag

| Option | Description | Selected |
|--------|-------------|----------|
| Include in findings model | `important: bool` per field. | |
| Separate classification step | Determined at render time (Phase 4). | ✓ |
| You decide | Claude's discretion. | |

**User's choice:** Separate step at render time
**Notes:** User said: "I think we can go with a separate importance classification step, when the final report is rendered. LLM decides what to bump to the top but usually the whole group is bumped at a time."

### Technique + Findings Model

| Option | Description | Selected |
|--------|-------------|----------|
| Single model includes both | One Pydantic model, one LLM call. | ✓ |
| Separate technique model | Two models, potentially two calls. | |
| You decide | Claude's discretion. | |

**User's choice:** Single model
**Notes:** None

### Classification Model Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Both models in Phase 1 | Classification + findings models together. | ✓ |
| Only findings model | Classification deferred to Phase 2/6. | |
| You decide | Claude's discretion. | |

**User's choice:** Both models in Phase 1
**Notes:** None

---

## Template Body Structure

### Section Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown H2 headers | `## CLINICAL HISTORY`, `## FINDINGS`, etc. | ✓ |
| YAML-defined section order | Sections keyed in frontmatter. | |
| Flat body with auto headers | Renderer adds headers. | |

**User's choice:** Markdown H2 headers
**Notes:** None

### Placeholder Layout

**User's choice:** One placeholder or group per line
**Notes:** User asked for an example. Provided full CT AP template body mockup. User then asked about paragraph grouping — how `{{gallbladder_and_cbd}}` followed by `{{spleen}}`, `{{adrenals}}`, `{{pancreas}}` forms a paragraph. Also asked about single vs double newline behavior (e.g. `{{lung_bases}}\n{{bones}}`).

**Final decision:** Renderer preserves template whitespace exactly. Single newline = consecutive lines, double newline = paragraph break. Template author has full control through newline placement. Groups listed as individual field placeholders — renderer collapses them, no group markers in body.

---

## Validation Strictness

### Pydantic Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict — fail on unknown keys | `extra: 'forbid'`. Catches typos early. | ✓ |
| Warn on unknown keys | `extra: 'ignore'` with logged warnings. | |
| Lenient — ignore silently | Unknown keys silently dropped. | |

**User's choice:** Strict, with good error handling
**Notes:** User specified: "but with good error handling that lets the template author know exactly which key or value was the issue"

### Cross-Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Cross-check fields vs body | Error if mismatches between frontmatter and body placeholders. | ✓ |
| Validate frontmatter only | Body treated as opaque text. | |

**User's choice:** Cross-check fields vs body
**Notes:** None

### Pertinent Negatives

**User's question:** "How are significant negatives handled? (e.g. 'No pneumoperitoneum' for a case of bowel ischaemia). These are technically normal but are important to bring to the top."

**Response:** If the radiologist wrote it, it's an extracted finding (string value, not None). The Phase 4 importance classification bumps it if `important_first` is on. If the radiologist didn't mention it, it's `__NOT_DOCUMENTED__`.

**User's confirmation:** "In cases of non-mentioned significant negatives, mark them as __NOT_DOCUMENTED__ and output that to the report for the user to fill in manually. There is no interaction involved in the report creation for now."

---

## Sample Template in Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal test fixture | 3-4 fields, one group, one measurement, one sex-dependent field. Not clinical. | ✓ |
| Real template early | Pull CT AP into Phase 1. Blurs Phase 3 boundary. | |
| Schema only | No sample template. Issues discovered late. | |

**User's choice:** Minimal test fixture
**Notes:** None

---

## Claude's Discretion

- Internal Pydantic model class structure and naming
- How partial combination texts are stored in group YAML structure
- Error message formatting details
- Test fixture field names and content

## Deferred Ideas

- LLM-generated partial normal text for groups — fallback if authored partials don't work (try in Phase 3)
- Clinical-history-aware prompting for pertinent negatives — v2 feature
