---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 07-04-PLAN.md
last_updated: "2026-06-17T04:30:00.000Z"
last_activity: 2026-06-17 -- Completed 07-04 (Python backend transport swap to minimodem ctypes binding, single-frame + CRC32)
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 17
  completed_plans: 16
  percent: 94
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-28)

**Core value:** The LLM must never fabricate findings. Every extracted finding must trace to the radiologist's draft input.
**Current focus:** Phase 07 — replace-ggwave-with-minimodem-both-sides

## Current Position

Phase: 07 (replace-ggwave-with-minimodem-both-sides) — EXECUTING
Plan: 5 of 5
Status: Executing Phase 07
Last activity: 2026-06-17 -- Completed 07-04 (Python backend transport swap to minimodem ctypes binding, single-frame + CRC32)

Progress: [█████████░] 94%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 2min | 2 tasks | 2 files |
| Phase 01 P02 | 2min | 2 tasks | 4 files |
| Phase 02 P01 | 4min | 3 tasks | 13 files |
| Phase 02 P02 | 3min | 2 tasks | 5 files |
| Phase 03 P01 | 2min | 2 tasks | 3 files |
| Phase 03 P02 | 3min | 2 tasks | 3 files |
| Phase 04 P01 | 8min | 3 tasks | 14 files |
| Phase 04 P02 | 2min | 1 tasks | 1 files |
| Phase 05 P01 | 5min | 3 tasks | 11 files |
| Phase 05 P02 | 4min | 2 tasks | 4 files |
| Phase 06 P01 | 4min | 3 tasks | 4 files |
| Phase 06 P02 | 3min | 2 tasks | 6 files |
| Phase 07 P01 | 20min | 3 tasks | 19 files |
| Phase 07 P02 | 40min | 3 tasks | 6 files |
| Phase 07 P03 | 25min | 2 tasks | 5 files |
| Phase 07 P04 | 7min | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: 6 phases derived from 28 requirements at standard granularity
- Roadmap: Renderer flags (TMPL-04/05/06/10) assigned to Phase 4 (behavior), schema definitions (TMPL-01-03/07-09) to Phase 1 (structure)
- [Phase 01]: All Pydantic models use ConfigDict(extra=forbid) for strict YAML key validation
- [Phase 01]: Test fixture uses 4 fields, 1 group, 1 measurement, 1 sex-dependent field per D-31 as reference implementation
- [Phase 02]: Backward-compat shim in template_schema.py preserves all existing import paths
- [Phase 02]: Standalone import test checks source code for audio imports rather than sys.modules
- [Phase 02]: Standalone import test checks source code for audio imports rather than sys.modules
- [Phase 03]: optional: bool = False added to FieldDefinition -- optional fields silently omitted when blank
- [Phase 03]: CT AP template established as reference pattern with 18 craniocaudal fields, sex-dependent pelvis, and clinical guidance
- [Phase 03]: US HBS measurement placeholders appear in both frontmatter normal text and body for test compatibility and render-time access
- [Phase 03]: CT AP structured variant uses markdown table for organ status with Key/Other Findings subsections
- [Phase 04]: TABLE_ROW_PATTERN anchored with ^ and re.MULTILINE to prevent cross-line captures from separator rows
- [Phase 04]: Two-pass substitution pattern: field/technique first, then measurements for normal text containing measurement placeholders
- [Phase 04]: Parametrized cross-template tests for guidance stripping and header conversion
- [Phase 05]: validate_fields_nonempty converted to model_validator for conditional empty-fields check on composites
- [Phase 05]: Body placeholder validation deferred to compose_template() for composites (Pitfall 5)
- [Phase 05]: Composed schema sets composable_from=None to indicate resolved state
- [Phase 05]: CT TAP body uses ### subheadings for anatomical section separation
- [Phase 05]: Two-pass registry loading: bases first, composites second via compose_template()
- [Phase 06]: Module-level imports for template system in pipeline.py (safe, no circular dependency)
- [Phase 06]: Sex inference from findings keys (prostate->male, uterus/ovaries->female)
- [Phase 06]: PIPELINE_MODE env var defaults to test for backward compatibility
- [Phase 06]: Golden files generated from actual pipeline output then committed as reference
- [Phase 06]: Snapshot comparison uses strip + CRLF->LF normalization for cross-platform compatibility
- [Phase 07]: RX thread uses pthreads (portable to Linux .so); one mutex guards all queue access (Pitfall 7)
- [Phase 07]: Half-duplex read-and-discard during TX via is_transmitting flag (Pitfall 3)
- [Phase 07]: -UNDEBUG forced on DLL+loopback — vendored tone generator emits the audio write inside assert(); NDEBUG stripped it so TX emitted silence (Rule 1 bug)
- [Phase 07]: CRC32 over UTF-8 bytes of ct; vectors 0xCBF43926 + 0xBF16E982 baked identically into Python+AHK tests
- [Phase 07]: AHK ChunkMessage now emits a single newline-framed frame (ci=0, cc=1) with crc=Crc32Str(ct); legacy split renamed to dormant ChunkMessageSplit; MainLoop call site unchanged
- [Phase 07]: AHK receive verifies CRC before surfacing; mismatch -> discard + full-message retransmit (ci=[0]), never displays a corrupt report (medico-legal)
- [Phase 07]: BAUD_RATE global (default 1200) in config.ahk passed to minimodem_simple_init; old protocol-id arg is now baud
- [Phase 07]: AHK CRC compared numerically ((received+0) != expected) and retx frames newline-terminated to match wrapper framing (deviations, Rules 2+3)
- [Phase 07]: Python lib/minimodem.py ctypes binding sets explicit restype/argtypes on all 12 exports; receive() uses a sized create_string_buffer (Security: signature mismatch -> memory corruption)
- [Phase 07]: backend.py transport swapped to minimodem (no ggwave/pyaudio); --baud (default 1200) replaces -p/--protocol; receive loop sleeps ~10ms between empty polls (no busy-spin); pipeline call UNCHANGED
- [Phase 07]: Binding searches BOTH libminimodem_simple.so and minimodem_simple.so (CMake PREFIX "" emits minimodem_simple.so) (Rule 1 bug)
- [Phase 07]: A7 -- removing -p/--protocol breaks any external Pi service unit invoking it; flagged in code + startup log (cannot verify from repo)

### Roadmap Evolution

- Phase 7 added: Replace ggwave with minimodem (both sides) — design spec at docs/superpowers/specs/2026-06-17-minimodem-transport-design.md

### Pending Todos

None yet.

### Blockers/Concerns

- Research flagged LLM hallucination risk (8-15% in medical contexts) -- mitigated by __NOT_DOCUMENTED__ default and constrained output
- interpolate_normal must default OFF -- "not mentioned" is not "evaluated and normal"
- Placeholder syntax decision needed early (Phase 1): {field_name} vs custom delimiter to avoid markdown conflicts

## Session Continuity

Last session: 2026-06-17T04:30:00.000Z
Stopped at: Completed 07-04-PLAN.md
Resume file: None
