# Phase 6: Pipeline Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 06-pipeline-integration
**Areas discussed:** Stage wiring scope, Registry lifecycle, Error propagation, Pipeline activation, Testing strategy, Sex filtering, Pipeline contract, Demo script

---

## Stage Wiring Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Stages 2+4 only | Wire template lookup and rendering. Stages 1, 3, 5 stay as NotImplementedError | |
| Stages 2+4 with passthrough stubs | Wire 2+4, replace NotImplementedError in 1/3/5 with passthrough logic | |
| All 5 stages with mock LLM | Wire everything including mock LLM | |

**User's choice:** Stages 2+4 only (Recommended)

### Testability

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — passthrough mode | Pipeline accepts pre-classified input and pre-extracted findings | |
| No — LLM required | Stages 1, 3, 5 raise NotImplementedError until LLM milestone | |
| Yes — injectable callables | Stages 1, 3, 5 accept injected callables | |

**User's choice:** Passthrough mode, but leave out impression for now (stage 5 stays stub)

### Data Flow (technique/important_fields source)

| Option | Description | Selected |
|--------|-------------|----------|
| From the incoming message | Radiologist's message includes technique info and importance flags | |
| From Stage 3 extraction | LLM extraction returns technique/important_fields alongside findings | |
| Mixed | Technique from message, importance from LLM | |

**User's choice:** From Stage 3 extraction

### Render Call

| Option | Description | Selected |
|--------|-------------|----------|
| Direct call | LLMPipeline calls render_report() factory directly | |
| Thin wrapper | Adds logging/timing around factory call | |

**User's choice:** Direct call (Recommended)

### Message Format for Passthrough

| Option | Description | Selected |
|--------|-------------|----------|
| Separate fields in message dict | study_type, findings, technique as top-level keys | |
| Structured content in 'ct' | ct contains JSON object with all data | |
| Function-based routing | Different fn values route to different pipeline paths | |

**User's choice:** Function-based routing

### Render Payload Format

| Option | Description | Selected |
|--------|-------------|----------|
| JSON in 'ct' | ct contains JSON: {study_type, findings, technique} | |
| Separate top-level keys | study_type, findings, technique as separate message keys | |

**User's choice:** JSON in 'ct' (Recommended)

### Render Payload Required Fields

| Option | Description | Selected |
|--------|-------------|----------|
| All required | study_type, findings required; technique required | |
| study_type + findings required, rest optional | technique, rest_normal, important_fields optional with defaults | |
| Only study_type required | Minimal, needs LLM for extraction | |

**User's choice:** study_type + findings required, rest optional

---

## Registry Lifecycle

### Initialization Location

| Option | Description | Selected |
|--------|-------------|----------|
| In LLMPipeline constructor | Pipeline owns the registry | |
| In backend.py at startup | Backend owns, passes to pipeline | |
| Lazy on first request | Created on first process() call | |

**User's choice:** In LLMPipeline constructor

### Templates Dir Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| CLI argument | --templates-dir flag with default | |
| Hardcoded default only | Always rpt_templates/ | |
| Environment variable | RPT_TEMPLATES_DIR env var with fallback | |

**User's choice:** Environment variable

### Startup Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — summary line | One line: loaded N templates (M aliases) | |
| Yes — detailed | Each template with aliases | |
| No extra logging | Errors only | |

**User's choice:** Yes — summary line

### Startup Failure

| Option | Description | Selected |
|--------|-------------|----------|
| Fatal — backend exits | Can't load templates = can't start | |
| Warn and fall back to TestPipeline | Stay alive for audio testing | |
| Fatal only for LLMPipeline | Pipeline raises, backend decides | |

**User's choice:** Fatal — backend exits
**Notes:** User emphasized pipeline must be separate from backend, callable independently

---

## Error Propagation

### Template Lookup Failure

| Option | Description | Selected |
|--------|-------------|----------|
| Human-readable error message | Error + known aliases list | |
| Error code + known aliases | JSON with error_code and aliases | |
| Error message only | Minimal error, no alias list | |

**User's choice:** Error message only (bandwidth-constrained)

### Rendering Failure

| Option | Description | Selected |
|--------|-------------|----------|
| Return error response | st='E', no partial report | |
| Return partial report + warning | st='S', remaining placeholders indicate failures | |
| You decide | Claude's discretion | |

**User's choice:** Return partial report + warning

### Audit Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — full audit | Every stage input/output logged | |
| Yes — input and output only | Draft + final report only | |
| Existing logging sufficient | No additional logging | |

**User's choice:** Yes — full audit (Recommended)

### NotImplementedError Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Catch and return user-friendly error | Specific message about which stage needs LLM | |
| Let it propagate to backend | Generic error handler | |
| Catch with specific error code | Machine-parseable NOT_IMPLEMENTED | |

**User's choice:** Catch and return user-friendly error

### Rest-Normal Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Flag in message dict | Frontend checkbox/keyword detection | |
| LLM detects from draft | Stage 3 recognises "rest normal" phrases | |
| Both | Explicit flag or LLM detection | |

**User's choice:** LLM detects from draft

---

## Pipeline Activation

### Pipeline Selection

| Option | Description | Selected |
|--------|-------------|----------|
| CLI flag | --pipeline test/llm | |
| Environment variable | PIPELINE_MODE env var | |
| Auto-detect | Check if rpt_templates/ exists | |

**User's choice:** Environment variable
**Notes:** User reiterated pipeline must be callable without backend.py

### Standalone Invocation

| Option | Description | Selected |
|--------|-------------|----------|
| Direct Python import | from lib.pipeline import LLMPipeline | |
| Import + convenience function | Plus top-level render_from_dict() | |
| Both import and CLI entry point | Plus python -m lib.pipeline | |

**User's choice:** Direct Python import

### Routing Location

| Option | Description | Selected |
|--------|-------------|----------|
| In the pipeline | LLMPipeline.process() handles fn routing | |
| In backend.py dispatch | Backend checks fn before calling pipeline | |

**User's choice:** In the pipeline (Recommended)

---

## Testing Strategy

### Test Level

| Option | Description | Selected |
|--------|-------------|----------|
| Integration tests only | Pipeline e2e with fn='render' | |
| Integration + unit tests | Plus routing, validation, error tests | |
| Integration + unit + snapshot | Plus golden-file output comparison | |

**User's choice:** Integration + unit + snapshot

### Snapshot Templates

| Option | Description | Selected |
|--------|-------------|----------|
| US HBS | Simple template with measurements | |
| CT AP (freeform) | Complex with sex-dependent fields, groups | |
| CT TAP (composite) | Composite template rendering | |
| CT AP (structured) | Table-based rendering | |

**User's choice:** All four selected

### Snapshot Location

| Option | Description | Selected |
|--------|-------------|----------|
| tests/snapshots/ | Dedicated snapshots directory | |
| tests/fixtures/ | Alongside existing fixtures | |
| Inline in test files | Multiline strings in tests | |

**User's choice:** tests/snapshots/

### Snapshot Update Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Manual only | Hand-authored, fail on mismatch | |
| Auto-update flag | --update-snapshots rewrites files | |

**User's choice:** Manual only (Recommended)

---

## Sex Filtering

| Option | Description | Selected |
|--------|-------------|----------|
| Optional 'sex' field in payload | Explicit sex field, include all if absent | |
| Inferred from findings keys | prostate=male, uterus/ovaries=female | |
| Deferred to LLM milestone | No filtering in fn='render' mode | |

**User's choice:** Inferred from findings keys

---

## Pipeline Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Keep same shape | Input {id, fn, ct}, output {id, st, ct} | |
| Extend output with metadata | Add study_type, template_used fields | |
| New response format | Richer structure with meta object | |

**User's choice:** Keep same shape (Recommended)

---

## Demo Script

### Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal render demo | Hardcoded US HBS findings, print report | |
| Interactive demo | Accept CLI input or JSON file | |
| Multi-template demo | Render US HBS, CT AP, CT TAP | |

**User's choice:** Minimal render demo

### Location

| Option | Description | Selected |
|--------|-------------|----------|
| python-backend/examples/ | Dedicated examples directory | |
| python-backend/demo_ushbs.py | Top-level in backend dir | |
| You decide | Claude's discretion | |

**User's choice:** python-backend/examples/

---

## Claude's Discretion

- Internal method structure for fn-based routing dispatch
- Exact environment variable naming beyond RPT_TEMPLATES_DIR and PIPELINE_MODE
- How sex inference from findings keys is implemented
- Demo script filename and exact sample findings content
- Test fixture design for integration and unit tests
- Logger message formatting for audit trail entries

## Deferred Ideas

None — discussion stayed within phase scope
