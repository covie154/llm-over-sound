# Research Summary

**Project:** LLM Report Templates -- Radiology Report Formatting System
**Synthesized:** 2026-03-28

## Key Findings

### Stack
- **2 new dependencies**: `python-frontmatter` (1.1.0) for YAML+markdown parsing, `Pydantic` (2.10+) for schema validation and LLM structured output integration
- No template engine needed -- `str.replace()` is sufficient for placeholder substitution
- No markdown library needed -- output is plain text over ggwave
- Deliberately minimal for Raspberry Pi deployment

### Features (Table Stakes)
- Organ-level field definitions with default normal text per field
- `interpolate_normal` flag (default OFF) with per-request "rest normal" override
- `__NOT_DOCUMENTED__` sentinel for unreported fields (clinically non-negotiable)
- Study type aliases for programmatic matching with LLM fallback
- Measurement placeholders marked as required fields
- Sex-dependent optional fields (both variants in template, LLM selects)
- Composable templates for combined studies (concatenated sections)

### Architecture
- Four components: TemplateRegistry (alias index), TemplateResolver (parse+compose), ParsedTemplate (frozen dataclass), ReportRenderer (deterministic assembly)
- Composite templates reference base templates by path; fields and body concatenated in order
- Single-level composition only (no nesting)
- Build order: data model → loader → registry → renderer → compositor → pipeline integration

### Critical Pitfalls
1. **LLM hallucination** (8-15% rates in medical contexts) -- mitigate with constrained output, `__NOT_DOCUMENTED__` default, post-extraction validation
2. **interpolate_normal danger** -- "not mentioned" ≠ "evaluated and normal"; must default OFF
3. **Measurement mangling** (~4% LLM error rate) -- treat as opaque tokens, regex validation
4. **Clinical language paraphrasing** -- verbatim extraction instructions, deterministic rendering
5. **Composability boundary duplication** -- explicit field ownership rules for overlapping anatomy
6. **Sex-dependent field misclassification** -- never default pelvic organ normal text (post-surgical risk)

## Recommendations for Roadmap

### Phase Structure (suggested)
1. **Template schema + data model** -- Pydantic models, field definitions, YAML frontmatter format
2. **Template loader + registry** -- Parse templates, build alias index, validate at load time
3. **Base template authoring** -- CT AP, CT thorax, US HBS with real clinical content
4. **Report renderer** -- Deterministic placeholder replacement, interpolate_normal logic, grouped fields, sex filtering
5. **Composite templates** -- CT TAP composition from base templates
6. **Pipeline integration** -- Wire template system into existing 5-stage backend pipeline

### Non-Negotiable Safety Requirements
- `interpolate_normal` defaults to `false` everywhere
- `__NOT_DOCUMENTED__` is the mandatory sentinel for unreported fields
- Measurements are opaque tokens, never fabricated
- Clinical language preserved verbatim in extraction
- All extraction logged for medico-legal audit trail
- YAML frontmatter values must be quoted strings (parsing fragility)

### Design Decisions to Make Early
- Placeholder syntax: `{field_name}` vs custom delimiter (avoid markdown conflicts)
- Boundary field ownership rules for combined studies
- Whether sex input should be required or LLM-inferred for pelvis studies
- Template validation CLI for template authors

## Sources (Key)
- [Herts et al., AJR 2019](https://ajronline.org/doi/10.2214/AJR.18.20368) -- gold standard for template field groupings
- [RSNA RadReport](https://www.rsna.org/practice-tools/data-tools-and-standards/radreport-reporting-templates) -- template standards
- [RSNA Best Practices for LLMs in Radiology](https://pubs.rsna.org/doi/10.1148/radiol.241516) -- safety guidelines
- [python-frontmatter](https://pypi.org/project/python-frontmatter/) -- YAML+markdown parser
- [Pydantic v2](https://docs.pydantic.dev/latest/) -- data validation
