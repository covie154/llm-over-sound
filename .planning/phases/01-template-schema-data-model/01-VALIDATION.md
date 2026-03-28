---
phase: 1
slug: template-schema-data-model
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x+ |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `cd python-backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd python-backend && python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd python-backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd python-backend && python -m pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | TMPL-01 | unit | `python -m pytest tests/test_template_schema.py -k "test_parse_yaml_frontmatter"` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | TMPL-02 | unit | `python -m pytest tests/test_template_schema.py -k "test_field_definitions_ordered"` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | TMPL-03 | unit | `python -m pytest tests/test_template_schema.py -k "test_field_normal_text"` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | TMPL-07 | unit | `python -m pytest tests/test_template_schema.py -k "test_field_groups"` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 1 | TMPL-08 | unit | `python -m pytest tests/test_template_schema.py -k "test_technique_section"` | ❌ W0 | ⬜ pending |
| 01-01-06 | 01 | 1 | TMPL-09 | unit | `python -m pytest tests/test_template_schema.py -k "test_guidance_section"` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | FWRK-03 | unit | `python -m pytest tests/test_template_schema.py -k "test_pydantic_validation"` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | FWRK-04 | unit | `python -m pytest tests/test_template_schema.py -k "test_findings_model"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `python-backend/tests/__init__.py` — package marker
- [ ] `python-backend/tests/conftest.py` — shared fixtures (fixture template path, sample frontmatter dicts)
- [ ] `python-backend/tests/fixtures/sample_template.md` — minimal test fixture template
- [ ] `python-backend/tests/test_template_schema.py` — test stubs for TMPL-01 through TMPL-09
- [ ] `pip install pytest python-frontmatter` — framework and dependency install

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Error messages are clear and actionable (D-27) | FWRK-03 | Subjective readability | Trigger validation errors and review message text |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
