---
phase: 4
slug: report-renderer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 |
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
| 04-01-01 | 01 | 1 | TMPL-04 | unit | `python -m pytest tests/test_renderer.py -k "interpolate_normal" -v` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | TMPL-05 | unit | `python -m pytest tests/test_renderer.py -k "impression" -v` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | TMPL-06 | unit | `python -m pytest tests/test_renderer.py -k "important_first" -v` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | TMPL-10 | unit | `python -m pytest tests/test_renderer.py -k "rest_normal" -v` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | FLDS-03 | unit | `python -m pytest tests/test_renderer.py -k "group" -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_renderer.py` — stubs for TMPL-04, TMPL-05, TMPL-06, TMPL-10, FLDS-03
- [ ] `tests/fixtures/` — minimal fixture templates for renderer unit tests

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
