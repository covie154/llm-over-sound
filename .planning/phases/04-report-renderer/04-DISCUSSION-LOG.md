# Phase 4: Report Renderer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 04-report-renderer
**Areas discussed:** Interpolation & rest-normal, Structured variant rendering, Impression generation, Output cleanup, Renderer API surface, Testing strategy, Schema changes needed, Plain text output

---

## Interpolation & rest-normal

### Group behavior when interpolate_normal is ON

| Option | Description | Selected |
|--------|-------------|----------|
| Joint normal text | Use group's joint_normal -- more concise and natural | ✓ |
| Individual field normals | Always expand to per-field normal text | |
| Template author controls | Per-group flag to decide | |

**User's choice:** Joint normal text
**Notes:** Falls back to individual normals only if joint_normal is missing.

### Rest-normal scope

| Option | Description | Selected |
|--------|-------------|----------|
| Unreported only | Fills fields where LLM returned None | ✓ |
| All empty fields | Fills any field showing __NOT_DOCUMENTED__ | |

**User's choice:** Unreported only
**Notes:** LLM's deliberate choices are preserved.

### Partial group handling

| Option | Description | Selected |
|--------|-------------|----------|
| Authored partials | Look up matching partial, fall back to individual normals | ✓ |
| Always individual normals | Skip partial lookups entirely | |
| LLM-generated partial | LLM generates combined sentence at render time | |

**User's choice:** Authored partials

### Groups when interpolate_normal is OFF

| Option | Description | Selected |
|--------|-------------|----------|
| __NOT_DOCUMENTED__ per field | Each unreported field shows individually | ✓ |
| Joint __NOT_DOCUMENTED__ | Single line per group | |
| Groups always collapse | joint_normal even when interpolation off | |

**User's choice:** __NOT_DOCUMENTED__ per field

---

## Structured variant rendering

### Renderer architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Same substitution | Just placeholder substitution on body text | |
| Structured-aware mode | Special logic for table format | |
| Separate renderer class | FreeformRenderer and StructuredRenderer subclasses | ✓ |

**User's choice:** Separate renderer classes

### Key vs Other findings classification

| Option | Description | Selected |
|--------|-------------|----------|
| LLM at extraction | LLM classifies during stage 3 | ✓ |
| Renderer splits by important_fields | Renderer sorts findings | |
| Template author pre-defines | Static per-field classification | |

**User's choice:** LLM at extraction

### Class design

| Option | Description | Selected |
|--------|-------------|----------|
| Base + subclasses | Shared base with variant-specific overrides | ✓ |
| Totally independent classes | Standalone with own logic | |
| Strategy pattern | Single class with swappable strategies | |

**User's choice:** Base + subclasses

### Dispatch mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| New frontmatter field | variant: freeform/structured in schema | ✓ |
| Infer from important_first | Couples two independent concepts | |
| Infer from body content | Detect table syntax -- fragile | |

**User's choice:** New frontmatter field

### Table cell content

| Option | Description | Selected |
|--------|-------------|----------|
| Short status labels | Normal / Abnormal / See below / __NOT_DOCUMENTED__ | ✓ |
| Full finding text in cell | Entire finding in table cell | |
| Truncated preview + detail | First ~50 chars + full text in sections | |

**User's choice:** Short status labels

### Table cell when interpolate_normal ON

| Option | Description | Selected |
|--------|-------------|----------|
| Show 'Normal' | Table cell reflects interpolated normal status | ✓ |
| Show the normal text | Actual normal text in cell | |
| __NOT_DOCUMENTED__ always | Ignore interpolation status | |

**User's choice:** Show 'Normal'

### important_first scope

| Option | Description | Selected |
|--------|-------------|----------|
| Both support it | Freeform reorders, Structured routes to Key/Other | ✓ |
| Structured only | Freeform ignores the flag | |
| Freeform reorders + adds header | Creates structured-like layout in prose | |

**User's choice:** Both support it

---

## Impression generation

### Renderer's role

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-generated string | Renderer receives impression as string | |
| Renderer triggers stage 5 | Renderer calls impression callable | ✓ |
| Impression as separate output | Pipeline appends after rendering | |

**User's choice:** Renderer triggers stage 5

### LLM access pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Callable injection | Accept generate_impression callable | ✓ |
| Direct LLM import | Renderer imports LLM client | |
| Two-phase render | Intermediate result with placeholder | |

**User's choice:** Callable injection

### Impression context

| Option | Description | Selected |
|--------|-------------|----------|
| Rendered findings + clinical history | Both for clinically relevant impression | ✓ |
| Rendered findings only | Just findings text | |
| Raw findings dict + template | Structured data input | |

**User's choice:** Rendered findings + clinical history

### Audit logging

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, renderer logs it | Renderer logs input/output for audit trail | ✓ |
| Caller's responsibility | Callable owner logs | |
| Both log | Belt and suspenders | |

**User's choice:** Renderer logs it

### No callable provided

| Option | Description | Selected |
|--------|-------------|----------|
| Raise error | Fail-fast when impression=true but no callable | |
| Leave COMMENT empty | Placeholder text '(impression not generated)' | ✓ |
| Skip COMMENT section | Treat as impression=false | |

**User's choice:** Leave COMMENT empty

### Async support

| Option | Description | Selected |
|--------|-------------|----------|
| Sync only | Phase 4 sync, async in Phase 6 if needed | ✓ |
| Async from the start | Future-proof but complex | |
| Support both | Maximum flexibility | |

**User's choice:** Sync only

---

## Output cleanup

### Blank line handling

| Option | Description | Selected |
|--------|-------------|----------|
| Collapse blank lines | 3+ consecutive blanks -> 2 | ✓ |
| Strip placeholder lines | Remove entire line for omitted fields | |
| Leave as-is | Preserve template whitespace exactly | |

**User's choice:** Collapse blank lines

### Guidance stripping

| Option | Description | Selected |
|--------|-------------|----------|
| Remove from H2 to next H2 | Strip ## Guidance to next section | ✓ |
| Remove from H2 to end | Guidance must be last before COMMENT | |
| Template flag | Named sections to strip | |

**User's choice:** Remove from H2 to next H2

### Markdown in output

**User's choice:** Plain text output only. Markdown output format KIV for v2.

### Comparison section

**User's choice:** Handled via technique dict as `{{technique:comparison}}`, defaults to "None available." when blank.

### Post-render validation

| Option | Description | Selected |
|--------|-------------|----------|
| Warn on unsubstituted | Log warning for remaining placeholders | ✓ |
| Error on unsubstituted | Raise error on remaining placeholders | |
| No validation | Trust findings dict matches template | |

**User's choice:** Warn on unsubstituted

### Return type

**User's choice:** Plain string. All warnings/metadata logged, not returned.

---

## Renderer API surface

### Parameter design

| Option | Description | Selected |
|--------|-------------|----------|
| All in render() | Stateless, each call self-contained | ✓ |
| Template at construction | Bound to one template | |
| Full construction | Dependencies at construction, per-request at render | |

**User's choice:** All in render()

### Template argument

| Option | Description | Selected |
|--------|-------------|----------|
| LoadedTemplate | Accept dataclass directly | ✓ |
| Schema + body separately | Separate arguments | |
| Template path | Load internally | |

**User's choice:** LoadedTemplate

### Factory dispatch

| Option | Description | Selected |
|--------|-------------|----------|
| Factory function | Top-level render_report() dispatches by variant | ✓ |
| Caller decides | Pipeline picks renderer class | |
| Registry returns renderer | Registry pairs template with renderer | |

**User's choice:** Factory function

---

## Testing strategy

### Expected output definition

| Option | Description | Selected |
|--------|-------------|----------|
| Inline expected strings | Per-test assertions | |
| Snapshot files | .txt files in fixtures | |
| Both | Inline for unit, snapshots for integration | ✓ |

**User's choice:** Both

### Impression in tests

| Option | Description | Selected |
|--------|-------------|----------|
| Lambda/mock | Fixed string return | |
| No impression in unit tests | Set impression=false or pass None | ✓ |
| Fixture impressions | Pattern-based mapping | |

**User's choice:** No impression in unit tests

### Template fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Both fixtures and real | Minimal fixtures for unit, real templates for integration | ✓ |
| Fixtures only | Controlled but no real template proof | |
| Real templates only | Realistic but fragile | |

**User's choice:** Both

---

## Schema changes needed

### Variant field values

| Option | Description | Selected |
|--------|-------------|----------|
| freeform / structured, default freeform | Two values, backward compatible | ✓ |
| Open string | No enum constraint | |
| Enum with validation | Literal type, strict | |

**User's choice:** freeform | structured, default freeform

### Timing

| Option | Description | Selected |
|--------|-------------|----------|
| Part of Phase 4 plan 01 | Schema change alongside base renderer | ✓ |
| Pre-phase quick task | Before Phase 4 planning | |
| Defer until needed | Infer variant from content | |

**User's choice:** Part of Phase 4 plan 01

### Template backfill

| Option | Description | Selected |
|--------|-------------|----------|
| Update all templates | Explicit variant field in all 4 templates | ✓ |
| Rely on default | Only update structured template | |
| Only update structured | Semi-explicit | |

**User's choice:** Update all templates

---

## Plain text output format

### Section headers

| Option | Description | Selected |
|--------|-------------|----------|
| UPPERCASE on own line | Strip ## prefix, keep text | ✓ |
| Header with underline | Dashes below header | |
| Header with blank lines | Whitespace only | |

**User's choice:** UPPERCASE on own line

### Table rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Aligned columns | Padded plain text columns | |
| Colon-separated | Field: Status per line | ✓ |
| Keep pipe table | Preserve markdown table syntax | |

**User's choice:** Colon-separated

---

## Claude's Discretion

- Internal method structure within base and subclass renderers
- Blank line collapsing algorithm implementation
- Factory dispatch mechanism (dict lookup, if/elif)
- Test fixture template content and findings dict structure
- Logger message formatting for audit trail
- FreeformRenderer important_first reordering approach

## Deferred Ideas

- Configurable output format (markdown vs plain text) -- v2
- LLM-generated partial normal text for groups
- Post-render LLM restructure for important_first
- Async impression callable -- Phase 6
- Structured renderer column alignment
