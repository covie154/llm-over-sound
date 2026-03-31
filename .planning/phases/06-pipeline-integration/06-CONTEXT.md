# Phase 6: Pipeline Integration - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the template system (registry, loader, renderer) into the existing 5-stage `LLMPipeline` so that ggwave messages trigger template-based report formatting end-to-end. Stages 2 (template lookup) and 4 (report rendering) get real implementations using the template system. Stages 1, 3, 5 remain stubs (LLM integration is a separate milestone). The pipeline must be callable independently of the backend — importable as a standalone Python module for testing and research.

</domain>

<decisions>
## Implementation Decisions

### Stage Wiring Scope
- **D-01:** Only stages 2 (template lookup) and 4 (report rendering) get real implementations in Phase 6. Stages 1, 3, 5 stay as `NotImplementedError` — they require LLM integration (separate milestone)
- **D-02:** Stage 4 calls the `render_report()` factory function from `renderer.py` directly — no wrapper logic. The renderer is already fully featured
- **D-03:** Stage 3 (extraction) is responsible for returning technique dict, important_fields, and rest_normal alongside the findings dict. These flow through to stage 4
- **D-04:** Impression generation (stage 5) is excluded from this phase — stays as a stub

### Function-Based Routing
- **D-05:** Different `fn` values route to different pipeline paths. `fn='report'` for the full 5-stage pipeline, `fn='render'` for direct template render with pre-extracted data (bypasses stages 1 and 3)
- **D-06:** For `fn='render'`, the `ct` field contains a JSON object: `{"study_type": "...", "findings": {...}, "technique": {...}, "rest_normal": false, "important_fields": [...]}`
- **D-07:** For `fn='render'` payload: `study_type` and `findings` are required. `technique`, `rest_normal`, and `important_fields` are optional with defaults (empty dict, false, None)
- **D-08:** Routing logic lives in the pipeline module (inside `LLMPipeline.process()`), not in `backend.py`

### Registry Lifecycle
- **D-09:** `TemplateRegistry` is initialized in the `LLMPipeline` constructor — pipeline owns it
- **D-10:** Templates directory path resolved via `RPT_TEMPLATES_DIR` environment variable, with `rpt_templates/` as the fallback default
- **D-11:** Registry logs one summary line at startup: "Loaded N templates (M aliases) from rpt_templates/"
- **D-12:** If templates directory is missing or has no valid templates, it is fatal — backend exits. The operator fixes the path and restarts

### Error Propagation
- **D-13:** Unknown study type returns `st='E'`, `ct='Unknown study type'` — minimal error message only, no alias list (bandwidth-constrained channel)
- **D-14:** Rendering failures return partial report with `st='S'` — remaining `{{placeholders}}` indicate where it failed. Radiologist can work with partial output
- **D-15:** `NotImplementedError` from stub stages (1, 3, 5) is caught and returns a user-friendly error: `st='E'`, `ct='Stage not implemented: [stage name] requires LLM connection'`
- **D-16:** Full audit logging: log the draft input, classified study type, extracted findings, and rendered report. Every stage's input/output recorded for medico-legal traceability

### Pipeline Activation
- **D-17:** `backend.py` uses `PIPELINE_MODE` environment variable to switch between `TestPipeline` (default) and `LLMPipeline`
- **D-18:** The pipeline is fully independent of `backend.py` — callable via direct Python import: `from lib.pipeline import LLMPipeline; p = LLMPipeline(templates_dir); result = p.process(msg_dict)`
- **D-19:** `process(msg_dict) -> dict` contract unchanged: input `{id, fn, ct}`, output `{id, st, ct}`. The `ct` field carries the rendered report string on success, error message on failure

### Sex Filtering
- **D-20:** Sex inferred from findings keys — if findings dict contains `prostate` -> male, `uterus`/`ovaries` -> female. No explicit sex field in the payload
- **D-21:** Rest-normal override is detected from draft text by the LLM (stage 3). In `fn='render'` mode, it's an optional field in the payload

### Testing Strategy
- **D-22:** Integration tests + unit tests + snapshot tests
- **D-23:** Integration tests: pipeline end-to-end with `fn='render'` — pre-extracted data through template lookup and rendering
- **D-24:** Unit tests: routing logic (fn dispatch), payload validation, error handling paths
- **D-25:** Snapshot golden-file tests for all four templates: US HBS, CT AP (freeform), CT TAP (composite), CT AP (structured)
- **D-26:** Golden files live in `tests/snapshots/` — manually authored, not auto-updated. Test fails if output doesn't match

### Demo Script
- **D-27:** Minimal render demo script in `python-backend/examples/` — instantiates `LLMPipeline`, calls `process()` with `fn='render'` and hardcoded US HBS findings, prints the rendered report

### Claude's Discretion
- Internal method structure for fn-based routing dispatch
- Exact environment variable naming beyond RPT_TEMPLATES_DIR and PIPELINE_MODE
- How sex inference from findings keys is implemented (simple key check vs regex)
- Demo script filename and exact sample findings content
- Test fixture design for integration and unit tests
- Logger message formatting for audit trail entries

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline Architecture
- `python-backend/lib/pipeline.py` — Existing `ReportPipeline` base class, `TestPipeline`, and `LLMPipeline` with 5-stage stubs
- `python-backend/backend.py` — Backend main loop, message dispatch, current `TestPipeline` instantiation at line 93

### Template System
- `python-backend/lib/templates/registry.py` — `TemplateRegistry` class with `get_template()` and `get_known_aliases()` APIs
- `python-backend/lib/templates/renderer.py` — `render_report()` factory function, `FreeformRenderer`, `StructuredRenderer`
- `python-backend/lib/templates/loader.py` — `LoadedTemplate` dataclass, `load_template()`, `discover_templates()`
- `python-backend/lib/templates/schema.py` — `TemplateSchema`, `create_findings_model()`, `StudyTypeClassification`, `NOT_DOCUMENTED`
- `python-backend/lib/templates/exceptions.py` — `TemplateValidationError`, `TemplateNotFoundError`, `TemplateLoadError`
- `python-backend/lib/__init__.py` — Public API exports for the lib package

### Template Files
- `rpt_templates/` — Template directory scanned by registry at startup

### Prior Phase Context
- `.planning/phases/04-report-renderer/04-CONTEXT.md` — Renderer API decisions (D-18 impression callable, D-30 render() signature, D-31 accepts LoadedTemplate)
- `.planning/phases/05-composite-templates/05-CONTEXT.md` — Composition transparency (D-17/D-18 registry returns LoadedTemplate for composites), flat findings dict (D-20)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TemplateRegistry`: Fully implemented, production-ready. Builds alias index at startup, case-insensitive lookup
- `render_report()` factory: Dispatches to FreeformRenderer/StructuredRenderer based on template variant
- `create_findings_model()`: Generates dynamic Pydantic model for validating findings against template fields
- `LoadedTemplate` dataclass: Frozen, contains schema + body + file_path

### Established Patterns
- Pipeline uses `process(msg_dict) -> dict` contract with `{id, fn, ct, st}` message shape
- Error responses use `st='E'`, success uses `st='S'`
- Logging via module-level `logger` from `lib.config`
- `lib/__init__.py` exports all public APIs — pipeline and template system already co-exported

### Integration Points
- `LLMPipeline.__init__(templates_dir)` — constructor already accepts templates_dir parameter
- `LLMPipeline.process()` — orchestrator method that calls all 5 stages
- `backend.py` line 93 — pipeline instantiation point (`TestPipeline()` currently)
- `backend.py` line ~154-171 — message dispatch calling `pipeline.process()`

</code_context>

<specifics>
## Specific Ideas

- US HBS demo script in `python-backend/examples/` showing the pipeline callable standalone without backend.py
- Pipeline must be importable and testable completely independently of the ggwave backend (FWRK-01 alignment)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-pipeline-integration*
*Context gathered: 2026-04-01*
