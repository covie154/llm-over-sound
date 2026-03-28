# LLM Report Templates — Radiology Report Formatting System

## What This Is

A template-driven radiology report formatting system. Markdown templates with YAML frontmatter define the structure, fields, and normal-text defaults for each imaging study type. The LLM extracts findings from a radiologist's draft input, maps them to template fields, and renders a formatted freetext report. Templates are composable — combined studies (e.g. CT TAP) concatenate sections from constituent templates.

## Core Value

The LLM must never fabricate findings. Every extracted finding must trace to the radiologist's draft input, and fields not mentioned must be marked `__NOT_DOCUMENTED__` or filled with the template's default normal text only when explicitly permitted.

## Requirements

### Validated

- ✓ Audio transport layer (ggwave) — existing
- ✓ Message chunking and reassembly — existing
- ✓ LZNT1 compression and Base62/Base64 encoding — existing
- ✓ AHK v2 frontend GUI with draft input — existing
- ✓ Python backend with pipeline architecture (5-stage) — existing
- ✓ C++ ggwave wrapper DLL — existing

### Active

- [ ] Template schema design (YAML frontmatter + markdown body)
- [ ] Organ-level field definitions with default normal text per field
- [ ] Composable templates — combined studies concatenate sections from base templates
- [ ] Sex-dependent optional fields (prostate vs uterus/ovaries)
- [ ] Measurement placeholders marked as required fields
- [ ] Study type aliases for programmatic matching with LLM fallback
- [ ] `impression` flag per template (whether to generate COMMENT section)
- [ ] `interpolate_normal` flag per template (fill unreported fields with normal text)
- [ ] Per-report override for interpolate_normal ("rest normal")
- [ ] CT abdomen and pelvis template
- [ ] CT thorax template
- [ ] CT thorax, abdomen and pelvis (combined) template
- [ ] US HBS template

### Out of Scope

- LLM prompt engineering and API integration — separate milestone
- Frontend UI changes for template selection — separate milestone
- Automated testing harness — no test framework exists yet
- MRI templates — CT and US first, MRI later
- Sub-organ granularity — start organ-level, extend later

## Context

- This is a brownfield project with an established audio transport layer. The 5-stage LLM pipeline exists but stages 1, 3, 4, 5 are stubs (NotImplementedError).
- This milestone focuses exclusively on the template system — the `.md` files that define report structure, fields, and normal defaults. The LLM integration that consumes these templates is a separate concern.
- Templates live under `rpt_templates/` organized by modality (e.g. `rpt_templates/ct/`, `rpt_templates/us/`).
- Combined studies reference base templates by path — the system loads and concatenates sections at runtime.
- The radiologist's workflow: draft findings in point form or brief notes on AHK frontend → transmitted over ggwave → backend classifies study type, loads template, extracts findings via LLM, renders report → sends back over ggwave.
- Sex-dependent fields (pelvis) are handled as optional fields — both male and female variants exist in the template, the LLM selects based on context or explicit input.
- Measurement fields use `_` placeholders and are flagged as required — if the user doesn't provide a measurement, it should be marked `__NOT_DOCUMENTED__`.

## Constraints

- **Template format**: Markdown with YAML frontmatter — must be human-readable and editable by radiologists
- **Field granularity**: Organ-level groupings that match natural reporting patterns (e.g. "spleen, adrenals and pancreas" grouped together when all normal)
- **Composability**: Combined templates must concatenate sections, not interleave — thorax findings block followed by abdomen/pelvis findings block
- **Audio bandwidth**: Templates themselves are not transmitted over ggwave, but the rendered reports are — keep report output concise
- **No fabrication**: Fields without input findings must use `__NOT_DOCUMENTED__` or the template's stored normal text (only when interpolate_normal is enabled)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Organ-level field granularity | Matches natural reporting groupings; extensible to sub-organ later | — Pending |
| Concatenated sections for combined studies | Preserves clear anatomical separation between study regions | — Pending |
| Both sex-dependent fields as optional | LLM infers from context; avoids requiring explicit sex input | — Pending |
| Programmatic alias matching with LLM fallback | Fast exact match first, fuzzy LLM match for edge cases | — Pending |
| Default normal text stored per field | Enables interpolate_normal without LLM generating normal text | — Pending |
| Measurements as required fields | Clinical accuracy — missing measurements must be flagged, not omitted | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*
