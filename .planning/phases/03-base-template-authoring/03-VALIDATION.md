---
phase: 3
slug: base-template-authoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `python-backend/pytest.ini` or `python-backend/pyproject.toml` |
| **Quick run command** | `cd python-backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd python-backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd python-backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd python-backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SMPL-01 | integration | `python -m pytest tests/test_templates.py -k "ct_ap"` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | SMPL-02 | integration | `python -m pytest tests/test_templates.py -k "ct_thorax"` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | SMPL-04 | integration | `python -m pytest tests/test_templates.py -k "us_hbs"` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | FLDS-01 | integration | `python -m pytest tests/test_templates.py -k "fields"` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | FLDS-02 | integration | `python -m pytest tests/test_templates.py -k "measurement"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_template_validation.py` — template load-and-validate tests for all 4 template files
- [ ] `tests/conftest.py` — shared fixtures for template paths and registry instances

*Existing infrastructure (schema, loader, registry) covers framework needs. Wave 0 adds template-specific test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Clinical accuracy of normal text | SMPL-01 | Requires radiologist domain review | Read each field's normal text and verify clinical correctness |
| Craniocaudal field ordering | FLDS-01 | Ordering correctness is domain knowledge | Verify field list order matches anatomical superior-to-inferior |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
