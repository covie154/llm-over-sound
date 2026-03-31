---
phase: 5
slug: composite-templates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `python-backend/pytest.ini` |
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
| 05-01-01 | 01 | 1 | COMP-01 | unit | `python -m pytest tests/test_composer.py -k composable_from -v` | W0 | pending |
| 05-01-02 | 01 | 1 | COMP-02 | unit | `python -m pytest tests/test_composer.py -k concatenate -v` | W0 | pending |
| 05-01-03 | 01 | 1 | COMP-03 | unit | `python -m pytest tests/test_composer.py -k flags -v` | W0 | pending |
| 05-01-04 | 01 | 1 | COMP-04 | unit | `python -m pytest tests/test_composer.py -k exclude -v` | W0 | pending |
| 05-02-01 | 02 | 2 | SMPL-03 | integration | `python -m pytest tests/test_production_templates.py -k ct_tap -v` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_composer.py` — stubs for COMP-01, COMP-02, COMP-03, COMP-04
- [ ] `tests/test_production_templates.py` — stubs for SMPL-03 (CT TAP end-to-end, added to existing file)

*Existing infrastructure (pytest, conftest, fixtures) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CT TAP report reads naturally | SMPL-03 | Clinical readability is subjective | Read rendered CT TAP report, verify thorax/AP section separation and bones coverage |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
