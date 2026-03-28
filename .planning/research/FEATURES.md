# Feature Landscape

**Domain:** Radiology report template system (LLM-powered, audio-channel transport)
**Researched:** 2026-03-28

## Table Stakes

Features users expect. Missing = product feels incomplete or clinically unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Organ-level field definitions | Every structured reporting system groups findings by organ/system. RSNA RadReport, rScriptor, and AJR Herts et al. all use organ-based sections. | Low | Standard groupings: liver, gallbladder/bile ducts, pancreas, spleen, adrenals, kidneys/ureters, bladder, bowel, mesentery/peritoneum, abdominal wall, vasculature, bones, lung bases. |
| Default normal text per field | AJR "review of systems" approach stores pertinent-negative text per organ field. Single most impactful efficiency feature -- radiologists report only abnormals. rScriptor's entire business model is built on this. | Low | Store as string value in YAML frontmatter per field. Keep clinically precise -- "normal in size and attenuation" not just "normal". |
| `interpolate_normal` flag | Controls whether unreported fields get default normal text or `__NOT_DOCUMENTED__`. Must be configurable per-template and overridable per-request. | Low | Template-level default in frontmatter, per-request override. Default OFF (safe). |
| `__NOT_DOCUMENTED__` sentinel | Fields not mentioned and not interpolated must be explicitly marked. Safety floor -- prevents silent omission of unexamined organs. Clinically non-negotiable. | Low | Literal string replacement. Frontend should visually highlight for radiologist review. |
| Study type aliases for matching | Templates must be findable by multiple names. "CT abdomen pelvis" = "CT AP" = "CTAP". RSNA RadReport uses keyword/tag matching. | Low | List of strings in YAML frontmatter. Programmatic exact match first, LLM fallback for fuzzy cases. |
| Measurement placeholders | Radiology reports contain quantitative measurements. Must be explicit placeholders flagged as required. Missing measurement = `__NOT_DOCUMENTED__`, never silently omitted. | Medium | Use `_` notation in template body. Parser identifies and flags as `required: true, type: measurement`. |
| Impression/conclusion generation | Stage 5 of pipeline. Every report ends with an impression. LLM generates concise summary answering clinical question. | Medium | Template frontmatter `impression: true/false` flag. Most templates `true`. |
| Sex-dependent optional fields | Pelvis templates must handle both male (prostate, seminal vesicles) and female (uterus, ovaries, adnexa) anatomy. AJR explicitly avoids defaulting pelvic organ fields due to post-surgical patients (hysterectomy, prostatectomy). | Medium | Both male and female field blocks marked `sex: M` or `sex: F`. LLM infers from context. Never default pelvic organ normal text. |
| YAML frontmatter + markdown body | Human-readable, version-controllable, editable by radiologists who are not programmers. MRRT used HTML5, which is hostile to hand-editing. | Low | `---` delimited YAML header. Markdown body is template skeleton with placeholders. |
| Five-section report structure | Clinical history, technique, comparison, findings, impression. Universal radiology report structure. | Low | Technique and comparison may be draft-passthrough. Findings is template-driven. Impression is LLM-generated. |
| Audit logging of extraction | Stage 3 must log every input-output pair. Medico-legal requirement. | Low | Log to `backend_log.txt`. Include draft text, extracted JSON, template used, timestamp. |

## Differentiators

Features that set this system apart. Not universally expected, but provide significant value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Composable templates for combined studies | CT TAP composed from CT thorax + CT abdomen-pelvis. Reduces maintenance, ensures consistency. | Medium | YAML `compose_from: [ct/thorax.md, ct/abdomen_pelvis.md]`. Runtime concatenation of fields and body sections. |
| Per-request "rest normal" override | Radiologist says "rest normal", overrides `interpolate_normal: false` for single request. Saves dictation time. | Low | Detect "rest normal" phrase in draft. Set runtime `interpolate_normal = true` for this request only. |
| Grouped organ fields with joint normal text | Some organs reported together when all normal: "The liver, spleen, and pancreas are unremarkable." Expand to individual fields when any abnormal. | Medium | YAML group structure. Renderer checks if all members normal; if so, uses group text. |
| Pertinent negative vocabulary per field | Each field has clinically specific negatives beyond generic "normal". E.g., gallbladder: "No gallstones. No wall thickening or pericholecystic fluid." | Low | Stored per field as `normal_text` string. Authored by radiologist, not auto-generated. |
| Technique section auto-population | Boilerplate technique descriptions per study type. Reduces dictation burden on most repetitive section. | Low | `technique` field in YAML frontmatter with optional contrast placeholders. |
| Field ordering preservation | Template body defines deterministic field order matching radiologist's expected reading order (craniocaudal for CT). | Low | Ordered list in YAML. Parser maintains insertion order. |
| Clarification requests for ambiguous input | System returns structured clarification request rather than guessing when confidence is low. | Medium | Response with clarification status code. Requires audio round-trip, so use sparingly. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Drop-down/pick-list UI in template | Audio-only transport. Interactive multi-select impossible over ggwave. | Free-text draft input extracted by LLM into structured fields. |
| MRRT/HTML5 template format | Overly complex. No PACS integration needed. RSNA has effectively paused MRRT development. | YAML frontmatter + markdown. Simpler, human-editable. |
| DICOM SR output | Output goes over ggwave as plain text. DICOM SR adds massive complexity for zero benefit. | Plain text report. DICOM SR is a separate export concern if ever needed. |
| RadLex/SNOMED ontology enforcement | Adds complexity without benefit in single-user, non-integrated system. | Preserve radiologist's clinical language verbatim. |
| AI-generated normal text | Fabrication risk. LLM deciding "the liver is normal" without radiologist saying so is a false statement. | Store normal text in template as authored by radiologist. |
| Sub-organ granularity (initial release) | Dramatically increases template complexity. | Organ-level for v1. Sub-organ detail goes in free text of organ field. |
| Comparison with prior studies | Requires access to prior report data not available in our architecture. | Radiologist includes comparison info in draft. Template has passthrough comparison section. |
| Multi-language support | Single radiologist system. | English-only templates. |
| BI-RADS/PI-RADS/LI-RADS scoring | Complex decision trees. Out of scope for general template system. | Implement as specialized templates later if needed. |

## Feature Dependencies

```
Study type aliases --> Template retrieval (Stage 2)
    |
    v
Organ-level field definitions --> Findings extraction (Stage 3)
    |
    v
Default normal text + interpolate_normal flag --> Report rendering (Stage 4)
    |                                               |
    v                                               v
Sex-dependent fields (pelvis only)           Grouped organ normal text
    |                                               |
    v                                               v
Measurement placeholders --------+--------> Final rendered findings
                                 |
                                 v
                          Impression generation (Stage 5)

Composability (compose_from) --> Template loading (affects Stage 2)
"Rest normal" detection --> Overrides interpolate_normal at runtime (Stage 3)
Clarification requests --> Requires frontend support for round-trip Q&A
```

## MVP Recommendation

**Phase 1 -- Core template schema and basic rendering:**
1. YAML frontmatter + markdown body format
2. Organ-level field definitions with ordered field list
3. Study type aliases for matching
4. `__NOT_DOCUMENTED__` sentinel
5. Default normal text per field
6. `interpolate_normal` flag (template-level)

**Phase 2 -- Advanced field handling:**
1. Sex-dependent optional fields
2. Measurement placeholders as required fields
3. Grouped organ fields with joint normal text
4. Per-request "rest normal" override

**Phase 3 -- Composability and combined studies:**
1. `compose_from` directive for combined templates
2. Section ordering enforcement (craniocaudal)

**Phase 4 -- Pipeline integration (separate milestone):**
1. Impression generation (Stage 5)
2. Clarification requests for ambiguous input
3. Audit logging integration

## Sources

- [RSNA RadReport Template Library](https://www.rsna.org/practice-tools/data-tools-and-standards/radreport-reporting-templates)
- [Herts et al., AJR 2019 -- "How We Do It: Creating Consistent Structure and Content in Abdominal Radiology Report Templates"](https://ajronline.org/doi/10.2214/AJR.18.20368)
- [ESR Paper on Structured Reporting 2023 Update](https://link.springer.com/article/10.1186/s13244-023-01560-0)
- [RSNA RadElement Common Data Elements](https://www.rsna.org/practice-tools/data-tools-and-standards/radelement-common-data-elements)
- [rScriptor / Scriptor Software](https://scriptorsoftware.com/)
- [Enhancing LLMs for Impression Generation via Multi-Agent System (RadCouncil)](https://arxiv.org/html/2412.06828v1)
- [RSNA Best Practices for Safe Use of LLMs in Radiology](https://pubs.rsna.org/doi/10.1148/radiol.241516)
