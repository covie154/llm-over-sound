---
phase: 7
slug: replace-ggwave-with-minimodem-both-sides
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-17
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> This phase is primarily a C/audio systems port. The project has **no automated
> test harness by convention** (manual round-trip integration testing). The one
> genuinely automatable gate is the **CRC32 cross-language agreement vector**;
> everything else is loopback/round-trip validation that must be run by hand
> against audio hardware (or a virtual audio cable).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None for the C wrapper (manual loopback). Python: `python -c` assertion scripts for CRC agreement. |
| **Config file** | none — wrapper validated via a standalone `loopback` test program built by CMake |
| **Quick run command** | `python -c "import zlib; assert zlib.crc32(b'123456789')==0xCBF43926; print('CRC OK')"` |
| **Full suite command** | Build wrapper (CMake) + run `minimodem_loopback` self-test (TX→RX byte-exact in one process via file/virtual-cable backend) |
| **Estimated runtime** | CRC vector ~instant; loopback build+run ~1–2 min |

---

## Sampling Rate

- **After every task commit:** Run the CRC vector check (when CRC code touched) and `cmake --build` to keep the wrapper compiling.
- **After every plan wave:** Run the `minimodem_loopback` byte-exact self-test.
- **Before `/gsd-verify-work`:** Loopback self-test green at default baud; CRC vector green on both AHK and Python sides.
- **Max feedback latency:** ~120 seconds (build + loopback).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-W0-01 | 01 | 0 | CRC agreement | — | corrupt frame never accepted | unit | `python -c "import zlib; assert zlib.crc32(b'123456789')==0xCBF43926"` | ❌ W0 | ⬜ pending |
| 7-W0-02 | 01 | 0 | byte-exact transport | — | no silent corruption | integration | `minimodem_loopback` self-test exits 0 | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **CRC32 agreement vector** — a shared test asserting `crc32("123456789") == 0xCBF43926` AND a UTF-8 multibyte case, proven byte-identical between AHK (`ntdll!RtlComputeCrc32`) and Python (`zlib.crc32`). This gate MUST pass before any framing code is trusted (medico-legal integrity).
- [ ] **`minimodem_loopback` self-test program** — a tiny CMake target that TX-encodes a buffer and RX-decodes it in-process (file or virtual-cable backend) and asserts byte-exact equality. Built before AHK/Python integration so the FSK refactor + WinMM backend are validated in isolation.

*Per RESEARCH.md "Wave 0 gates": CRC vector + byte-exact loopback must be green before touching AHK or Python.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-machine round trip | both ends interoperate | needs two machines + USB audio cable | Run AHK frontend + Pi backend over the cable; send a draft, confirm formatted report returns intact. Calibrate volume per direction first. |
| Report-length payload + corruption | CRC + full retransmit | needs real audio path + induced noise | Send a ~500-byte report single-frame; inject corruption; confirm CRC mismatch triggers full retransmit and no partial report surfaces. |
| Baud sweep | configurable baud, both ends matched | depends on hardware passband | Change `BAUD_RATE`/`--baud` (no recompile) across 1200/4800/9600; confirm both ends must match; note where high baud fails on the interface. |
| Dependency-free DLL | zero-install portability | requires dependency walker on Windows | `ntldd -R minimodem_simple.dll` shows only system DLLs (winmm, kernel32, …). |

---

## Validation Sign-Off

- [ ] Wave 0 CRC vector + loopback self-test green before AHK/Python integration
- [ ] Sampling continuity: wrapper keeps compiling after each task
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
