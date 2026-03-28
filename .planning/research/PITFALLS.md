# Domain Pitfalls

**Domain:** LLM-powered radiology report template system
**Researched:** 2026-03-28

## Critical Pitfalls

Mistakes that cause clinical harm, medico-legal liability, or system rewrites.

### Pitfall 1: LLM Hallucination of Findings (Fabrication)

**What goes wrong:** The LLM invents findings not present in the radiologist's draft input. Literature reports hallucination rates of 8-15% across current LLM systems in medical contexts. Even a single fabricated finding can alter clinical management.

**Why it happens:** LLMs have strong priors about what "normal" reports contain. When a field exists in the template but the draft is silent on it, the model fills in plausible-sounding normal text rather than marking it unknown. Especially dangerous for negatives -- stating something is absent when it was never evaluated.

**Prevention:**
- Extraction prompt must explicitly instruct: "Only extract findings explicitly stated in the input. If a field is not mentioned, output `__NOT_DOCUMENTED__`."
- Use constrained JSON output keyed to template fields.
- Post-extraction validation: for each extracted finding, verify it can be traced to the original draft.
- Never allow `interpolate_normal` to be the default. Explicit opt-in only.
- Log every input-output pair for audit trail.

**Detection:**
- Extracted JSON contains field values where the draft has no corresponding mention.
- Output contains hedging language for fields not in the draft.

**Which phase should address it:** Phase 1 (template schema) must define `__NOT_DOCUMENTED__` as mandatory default. Phase 2 (LLM prompts) must enforce the constraint.

---

### Pitfall 2: interpolate_normal Filling Clinically Dangerous Defaults

**What goes wrong:** When enabled, unreported fields get "normal" text. If the radiologist did not evaluate the organ (scan limited, organ excluded from field of view), the report states normalcy for an unevaluated organ.

**Why it happens:** "Not mentioned" and "evaluated and normal" are clinically distinct states the system cannot distinguish without explicit radiologist intent.

**Prevention:**
- `interpolate_normal` must default to `false` at both template and per-report levels.
- When enabled, consider a disclosure: "Unreported fields populated with normal defaults per radiologist instruction."
- Some fields can safely default to normal (e.g., "No free fluid") while others should never auto-fill (organ-specific assessments in limited studies).
- Frontend should present `__NOT_DOCUMENTED__` fields prominently for radiologist review.

**Which phase should address it:** Phase 1 (template schema) must implement safe defaults.

---

### Pitfall 3: Measurement Mangling and Unit Confusion

**What goes wrong:** LLM mishandles measurements: transposing dimensions, dropping dimensions, confusing units (mm vs cm), or fabricating measurements. LLMs achieve only ~96% accuracy on measurement extraction -- 4% error rate is clinically unacceptable without safeguards.

**Prevention:**
- Treat measurements as opaque tokens -- extract literal string verbatim.
- Measurement fields use `_` placeholders marked `required: true`. No draft measurement = `__NOT_DOCUMENTED__`, never fabricated.
- Regex-based post-extraction validation: extracted measurements must match a pattern found in original draft.
- Store as strings, not numbers, to prevent floating-point issues.

**Which phase should address it:** Phase 1 (field schema with required flag). Phase 2 (extraction prompts with preservation instructions).

---

### Pitfall 4: Loss of Clinical Language and Intent

**What goes wrong:** LLM paraphrases the radiologist's language. "Suspicious for malignancy" becomes "concerning for neoplasm". These change the clinical certainty level communicated to the referring physician.

**Prevention:**
- Extraction prompt: "Preserve the radiologist's exact language. Do not rephrase."
- Use deterministic string interpolation for rendering wherever possible.
- Impression generation (Stage 5) is the only stage where LLM composition of new text is acceptable.

**Which phase should address it:** Phase 1 (mark which fields require verbatim preservation). Phase 2 (prompts enforce verbatim extraction).

---

## Moderate Pitfalls

### Pitfall 5: Composability Boundary Duplication

**What goes wrong:** Combined templates (CT TAP) produce duplicate fields at anatomical boundaries. Diaphragm, lung bases, and adrenals may appear in both thorax and abdomen templates.

**Prevention:**
- Define explicit field ownership rules per boundary region.
- Combined templates are first-class entities that reference base templates with clear boundary ownership.
- Field registry detects duplicate field names at load time.

**Which phase should address it:** Phase 1 (template schema design). Composability model must handle boundaries before combined templates are built.

---

### Pitfall 6: Sex-Dependent Field Misclassification

**What goes wrong:** LLM guesses wrong patient sex. With `interpolate_normal` on, could state "the prostate is normal" for a female patient.

**Prevention:**
- If no sex-indicating context and template has sex-dependent fields, request clarification rather than guessing.
- Sex-dependent fields clearly marked in schema.
- Consider requiring explicit sex input for pelvis-containing studies.

**Which phase should address it:** Phase 1 (template schema with sex field support and fallback mechanism).

---

### Pitfall 7: Study Type Misclassification Cascade

**What goes wrong:** Stage 1 selects wrong template. All subsequent stages operate on wrong field set, producing structurally valid but clinically nonsensical report.

**Prevention:**
- Comprehensive alias index covering common abbreviations.
- Below-threshold confidence triggers clarification request.
- Include classified study type in report header for radiologist to spot misclassification.
- Allow frontend to optionally pre-select study type.

**Which phase should address it:** Phase 1 (alias index design). Phase 2 (classification with confidence thresholds).

---

### Pitfall 8: Template Rigidity vs Clinical Reality

**What goes wrong:** Templates enforce fixed organ-by-organ structure, but pathology spans multiple organs. "Rim-enhancing collection extending from appendix into right paracolic gutter" spans bowel and peritoneum.

**Prevention:**
- Allow cross-references between fields.
- Include a "general/other findings" catch-all field.
- Extraction prompt: place multi-organ findings in most clinically relevant field.

**Which phase should address it:** Phase 1 (template design with catch-all field).

---

### Pitfall 9: YAML Frontmatter Parsing Fragility

**What goes wrong:** YAML is sensitive to whitespace and special characters. Radiology terminology includes colons (e.g., "CT: abdomen"), quotes, and special characters that break parsing.

**Prevention:**
- Strict YAML schema validator at template load time. Fail loudly.
- Default text values must always be quoted strings.
- Provide template validation tool for template authors.

**Which phase should address it:** Phase 1. Schema parser must be robust from day one.

---

## Minor Pitfalls

### Pitfall 10: Report Length Exceeding Audio Bandwidth

**Prevention:** Templates should aim for concise output. Normal defaults should be brief. Estimate compressed report sizes during template design.

### Pitfall 11: Impression Generation Contradicting Findings

**Prevention:** Pass fully rendered findings (not just draft) to impression stage. Implement consistency check: abnormal findings must appear in impression.

### Pitfall 12: Template Version Drift

**Prevention:** Rebuild template index at startup. Version templates in frontmatter. Validate unique aliases at startup.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Template schema design | YAML parsing fragility | Strict quoting rules, validation at load time |
| Template schema design | Composability boundary duplication | Explicit field ownership rules |
| Template schema design | Sex-dependent fields without fallback | Clarification request mechanism |
| Template schema design | Measurement fields without required flag | All measurement placeholders `required: true` |
| Template schema design | `interpolate_normal` defaulting to true | Must default to false |
| LLM extraction prompts | Hallucinated findings | Constrained output, verbatim instructions, validation |
| LLM extraction prompts | Paraphrased clinical language | Explicit verbatim preservation |
| LLM extraction prompts | Study type misclassification | Confidence threshold with clarification fallback |
| LLM extraction prompts | Measurement mangling | Opaque token extraction, regex validation |
| Report rendering | Impression contradicting findings | Pass full findings to impression stage |
| Combined templates | Duplicate anatomy | Field registry with collision detection |

## Sources

- [Structured Reporting in Radiological Settings: Pitfalls and Perspectives (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9409900/)
- [Pearls and Pitfalls for LLMs 2.0 (Radiology/RSNA)](https://pubs.rsna.org/doi/10.1148/radiol.242512)
- [Best Practices for Safe Use of LLMs in Radiology (Radiology/RSNA)](https://pubs.rsna.org/doi/10.1148/radiol.241516)
- [How We Do It: Creating Consistent Structure in Abdominal Radiology Report Templates (AJR)](https://ajronline.org/doi/10.2214/AJR.18.20368)
- [ESR Paper on Structured Reporting in Radiology -- Update 2023 (Springer)](https://link.springer.com/article/10.1186/s13244-023-01560-0)
- [RSNA RadReport Reporting Templates](https://www.rsna.org/practice-tools/data-tools-and-standards/radreport-reporting-templates)
