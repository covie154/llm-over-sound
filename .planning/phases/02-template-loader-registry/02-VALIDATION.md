---
phase: 2
slug: template-loader-registry
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 |
| **Config file** | `python-backend/tests/` |
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
| TBD | TBD | TBD | MTCH-01 | unit | `python -m pytest tests/test_registry.py -k alias_index` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MTCH-02 | unit | `python -m pytest tests/test_registry.py -k scan_recursive` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MTCH-03 | unit | `python -m pytest tests/test_registry.py -k lookup_fallback` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | FWRK-01 | integration | `python -m pytest tests/test_registry.py -k standalone_import` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_registry.py` — stubs for MTCH-01, MTCH-02, MTCH-03, FWRK-01
- [ ] `tests/fixtures/` — fixture templates for registry testing (minimal structural templates)

*Existing test infrastructure (pytest, conftest) covers framework needs.*

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
