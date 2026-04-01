# Phase 6: Pipeline Integration - Research

**Researched:** 2026-04-01
**Domain:** Python backend pipeline wiring -- connecting template system to existing 5-stage LLMPipeline
**Confidence:** HIGH

## Summary

Phase 6 wires the template system (registry, loader, renderer) into the existing `LLMPipeline` class so that stages 2 (template lookup) and 4 (report rendering) have real implementations. Stages 1, 3, and 5 remain stubs (`NotImplementedError`). The phase also adds `fn`-based routing (`fn='report'` for full pipeline, `fn='render'` for direct render with pre-extracted data) and switches `backend.py` to use `LLMPipeline` via a `PIPELINE_MODE` environment variable.

All components already exist and are tested independently: `TemplateRegistry` (140 tests, production templates load cleanly), `render_report()` factory function, `LoadedTemplate` dataclass. The integration task is connecting these pieces inside `LLMPipeline.process()` and updating `backend.py` to conditionally instantiate `LLMPipeline`. The registry already handles composite templates via two-pass loading, so CT TAP works transparently.

**Primary recommendation:** Implement fn-based routing dispatch inside `LLMPipeline.process()`, wire stage 2 to `TemplateRegistry.get_template()` and stage 4 to `render_report()`, add `PIPELINE_MODE` env var switching in `backend.py`, create snapshot golden-file tests for all four templates, and build a minimal demo script.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Only stages 2 (template lookup) and 4 (report rendering) get real implementations in Phase 6. Stages 1, 3, 5 stay as `NotImplementedError`
- **D-02:** Stage 4 calls the `render_report()` factory function from `renderer.py` directly -- no wrapper logic
- **D-03:** Stage 3 (extraction) is responsible for returning technique dict, important_fields, and rest_normal alongside the findings dict. These flow through to stage 4
- **D-04:** Impression generation (stage 5) is excluded from this phase -- stays as a stub
- **D-05:** Different `fn` values route to different pipeline paths. `fn='report'` for full 5-stage pipeline, `fn='render'` for direct template render with pre-extracted data (bypasses stages 1 and 3)
- **D-06:** For `fn='render'`, the `ct` field contains a JSON object: `{"study_type": "...", "findings": {...}, "technique": {...}, "rest_normal": false, "important_fields": [...]}`
- **D-07:** For `fn='render'` payload: `study_type` and `findings` are required. `technique`, `rest_normal`, and `important_fields` are optional with defaults (empty dict, false, None)
- **D-08:** Routing logic lives in the pipeline module (inside `LLMPipeline.process()`), not in `backend.py`
- **D-09:** `TemplateRegistry` is initialized in the `LLMPipeline` constructor -- pipeline owns it
- **D-10:** Templates directory path resolved via `RPT_TEMPLATES_DIR` environment variable, with `rpt_templates/` as the fallback default
- **D-11:** Registry logs one summary line at startup: "Loaded N templates (M aliases) from rpt_templates/"
- **D-12:** If templates directory is missing or has no valid templates, it is fatal -- backend exits
- **D-13:** Unknown study type returns `st='E'`, `ct='Unknown study type'` -- minimal error message only
- **D-14:** Rendering failures return partial report with `st='S'` -- remaining `{{placeholders}}` indicate where it failed
- **D-15:** `NotImplementedError` from stub stages (1, 3, 5) is caught and returns a user-friendly error: `st='E'`, `ct='Stage not implemented: [stage name] requires LLM connection'`
- **D-16:** Full audit logging: log draft input, classified study type, extracted findings, and rendered report
- **D-17:** `backend.py` uses `PIPELINE_MODE` environment variable to switch between `TestPipeline` (default) and `LLMPipeline`
- **D-18:** The pipeline is fully independent of `backend.py` -- callable via direct Python import
- **D-19:** `process(msg_dict) -> dict` contract unchanged: input `{id, fn, ct}`, output `{id, st, ct}`
- **D-20:** Sex inferred from findings keys -- if findings dict contains `prostate` -> male, `uterus`/`ovaries` -> female. No explicit sex field
- **D-21:** Rest-normal override is detected from draft text by the LLM (stage 3). In `fn='render'` mode, it's an optional field in the payload
- **D-22 through D-26:** Testing strategy: integration tests, unit tests, snapshot golden-file tests for all four templates in `tests/snapshots/`
- **D-27:** Minimal render demo script in `python-backend/examples/`

### Claude's Discretion
- Internal method structure for fn-based routing dispatch
- Exact environment variable naming beyond RPT_TEMPLATES_DIR and PIPELINE_MODE
- How sex inference from findings keys is implemented (simple key check vs regex)
- Demo script filename and exact sample findings content
- Test fixture design for integration and unit tests
- Logger message formatting for audit trail entries

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FWRK-02 | The template system integrates with the existing 5-stage backend pipeline -- called after the backend receives a ggwave message | Wiring stages 2 and 4 in LLMPipeline, fn-based routing dispatch, PIPELINE_MODE env var in backend.py, error propagation patterns |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | (already installed) | Findings validation via `create_findings_model()` | Already used throughout template system |
| python-frontmatter | (already installed) | Template parsing | Already used by loader |
| pytest | (already installed) | Test framework | 140 existing tests use it |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new) | -- | -- | All dependencies already installed |

No new packages needed. Phase 6 uses only existing project dependencies.

## Architecture Patterns

### Current Pipeline Structure
```
python-backend/
├── backend.py                    # Main loop -- instantiates pipeline, dispatches messages
├── lib/
│   ├── __init__.py               # Public API exports
│   ├── pipeline.py               # ReportPipeline ABC, TestPipeline, LLMPipeline
│   ├── config.py                 # Logger setup
│   └── templates/
│       ├── registry.py           # TemplateRegistry (alias index)
│       ├── renderer.py           # render_report() factory
│       ├── loader.py             # LoadedTemplate, load_template()
│       ├── schema.py             # TemplateSchema, create_findings_model()
│       ├── composer.py           # compose_template()
│       └── exceptions.py         # TemplateNotFoundError, etc.
├── rpt_templates/                # Production templates
│   ├── ct/
│   │   ├── ct_ap.rpt.md
│   │   ├── ct_ap_structured.rpt.md
│   │   ├── ct_thorax.rpt.md
│   │   └── ct_tap.rpt.md        # Composite
│   └── us/
│       └── us_hbs.rpt.md
├── tests/
│   ├── conftest.py               # Shared fixtures
│   ├── fixtures/                 # Test template files
│   └── snapshots/                # NEW: golden-file test outputs (D-26)
└── examples/                     # NEW: demo scripts (D-27)
```

### Pattern 1: fn-Based Routing Inside LLMPipeline.process()

**What:** The `process()` method inspects `msg_dict['fn']` and dispatches to the appropriate code path. `fn='report'` runs the full 5-stage pipeline (stages 1, 3, 5 will raise NotImplementedError). `fn='render'` parses `ct` as JSON, looks up the template via registry, and calls `render_report()` directly (bypassing stages 1 and 3).

**When to use:** Always -- this is the sole dispatch mechanism.

**Example:**
```python
# Inside LLMPipeline.process()
def process(self, msg_dict: dict) -> dict:
    msg_id = msg_dict.get("id", "")
    fn = msg_dict.get("fn", "")

    if fn == "render":
        return self._handle_render(msg_id, msg_dict.get("ct", ""))
    elif fn == "report":
        return self._handle_report(msg_id, msg_dict.get("ct", ""))
    else:
        # Existing behavior for unknown/test fns
        return {"id": msg_id, "st": "E", "ct": f"Unknown function: {fn}"}
```

### Pattern 2: Registry Ownership in Constructor

**What:** `LLMPipeline.__init__()` creates and owns a `TemplateRegistry` instance. The registry loads all templates at construction time and logs a summary line.

**Example:**
```python
def __init__(self, templates_dir: str | None = None):
    import os
    from lib.templates.registry import TemplateRegistry

    resolved_dir = templates_dir or os.environ.get("RPT_TEMPLATES_DIR", "rpt_templates")
    self._registry = TemplateRegistry(resolved_dir)

    aliases = self._registry.get_known_aliases()
    logger.info(f"Loaded {len(set(...))} templates ({len(aliases)} aliases) from {resolved_dir}")
```

### Pattern 3: Sex Inference from Findings Keys

**What:** Determine patient sex from findings dict keys to filter sex-dependent template fields. Simple key membership check.

**Example:**
```python
def _infer_sex(self, findings: dict) -> str | None:
    keys = set(findings.keys())
    male_markers = {"prostate"}
    female_markers = {"uterus", "ovaries"}
    if keys & male_markers:
        return "male"
    if keys & female_markers:
        return "female"
    return None
```

### Pattern 4: PIPELINE_MODE Environment Variable in backend.py

**What:** `backend.py` reads `PIPELINE_MODE` env var to decide which pipeline to instantiate. Default is `TestPipeline` (backward compatible). Set to `llm` for `LLMPipeline`.

**Example:**
```python
import os
pipeline_mode = os.environ.get("PIPELINE_MODE", "test")
if pipeline_mode == "llm":
    pipeline = LLMPipeline()
else:
    pipeline = TestPipeline()
```

### Anti-Patterns to Avoid
- **Routing in backend.py:** D-08 explicitly places routing inside the pipeline module, not in backend.py. Backend only instantiates and calls `process()`.
- **Wrapping render_report():** D-02 says call `render_report()` directly -- no intermediate adapter.
- **Catching TemplateNotFoundError silently:** D-13 requires returning an error response, not swallowing the exception.
- **Auto-generating golden files:** D-26 says golden files are manually authored, not auto-updated.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template lookup by alias | Custom string matching | `TemplateRegistry.get_template()` | Already handles case-insensitive matching, composites, collision detection |
| Report rendering dispatch | Manual if/else on variant type | `render_report()` factory function | Already dispatches to FreeformRenderer/StructuredRenderer |
| Findings validation | Manual dict key checking | `create_findings_model()` | Generates dynamic Pydantic model from template fields |
| Template file loading | Custom YAML/markdown parser | `load_template()` from loader.py | Handles frontmatter parsing, validation, cross-reference |

## Common Pitfalls

### Pitfall 1: Circular Import Between pipeline.py and templates
**What goes wrong:** `pipeline.py` imports from `lib.templates.registry`, and `lib/__init__.py` already imports from both `pipeline` and `templates`. Import order could cause circular dependency.
**Why it happens:** Python's import system resolves imports at module load time. If pipeline.py imports templates and templates/__init__.py imports pipeline, deadlock.
**How to avoid:** Import `TemplateRegistry` and `render_report` inside `LLMPipeline.__init__()` or at the top of `pipeline.py` -- NOT through `lib/__init__.py`. The current `lib/__init__.py` already imports both, so top-level imports in pipeline.py from `lib.templates.registry` (using the direct submodule path) are safe.
**Warning signs:** `ImportError` or `AttributeError` at import time.

### Pitfall 2: NotImplementedError Stage Name Extraction
**What goes wrong:** When stages 1, 3, or 5 raise `NotImplementedError`, the error message per D-15 must include the stage name (e.g., "Study type classification requires LLM connection"). If you catch a bare `NotImplementedError`, you lose which stage failed.
**Why it happens:** All three stub stages raise the same exception type.
**How to avoid:** Either: (a) catch NotImplementedError per-stage with explicit error text, or (b) have each stub raise with a descriptive message and extract it from `str(e)`.
**Warning signs:** Generic "not implemented" error reaching the frontend.

### Pitfall 3: ct Field Double-Parsing for fn='render'
**What goes wrong:** The `ct` field for `fn='render'` contains a JSON string (per D-06). The chunking layer already JSON-decodes the message, so `msg_dict['ct']` is a string. It must be JSON-parsed again to extract the render payload.
**Why it happens:** The message protocol uses `ct` as a string field, so the inner JSON is a string-within-a-string.
**How to avoid:** Explicitly `json.loads(msg_dict['ct'])` inside `_handle_render()` and catch `json.JSONDecodeError`.
**Warning signs:** Getting a raw string where you expected a dict.

### Pitfall 4: Templates Directory Path Resolution
**What goes wrong:** `rpt_templates/` as a relative path resolves differently depending on cwd. When `backend.py` runs from `python-backend/`, it works. When tests run from the repo root, it breaks.
**Why it happens:** Relative paths are resolved against the current working directory.
**How to avoid:** In `LLMPipeline.__init__()`, resolve the default path relative to the backend module location: `pathlib.Path(__file__).parent.parent / "rpt_templates"`. The env var override (`RPT_TEMPLATES_DIR`) should accept absolute paths.
**Warning signs:** `TemplateValidationError` about "directory does not exist" in tests.

### Pitfall 5: Snapshot Test Brittleness
**What goes wrong:** Golden-file tests fail on trivial whitespace differences (trailing newlines, line endings, blank line counts).
**Why it happens:** Different platforms use different line endings; the renderer's blank-line cleanup may change between runs.
**How to avoid:** Normalize whitespace in comparison (strip both sides, normalize line endings to `\n`). Store golden files with Unix line endings.
**Warning signs:** Tests pass locally but fail in CI, or vice versa.

### Pitfall 6: render_report() Signature Mismatch
**What goes wrong:** The pipeline passes the wrong arguments to `render_report()`.
**Why it happens:** `render_report()` takes `(template, findings, technique, important_fields, rest_normal, generate_impression)` -- but the `fn='render'` payload has these as JSON fields with slightly different names.
**How to avoid:** Map payload keys to function parameters explicitly. `study_type` is used for lookup only, not passed to render. `findings`, `technique`, `rest_normal`, `important_fields` map directly.
**Warning signs:** `TypeError` about unexpected keyword arguments.

## Code Examples

### fn='render' Handler
```python
# Source: Derived from CONTEXT.md D-05 through D-07 and renderer.py API
import json
from lib.templates.renderer import render_report
from lib.templates.exceptions import TemplateNotFoundError

def _handle_render(self, msg_id: str, ct: str) -> dict:
    """Handle fn='render' -- direct template render with pre-extracted data."""
    try:
        payload = json.loads(ct)
    except json.JSONDecodeError as e:
        return {"id": msg_id, "st": "E", "ct": f"Invalid render payload: {e}"}

    study_type = payload.get("study_type")
    findings = payload.get("findings")
    if not study_type or findings is None:
        return {"id": msg_id, "st": "E", "ct": "Missing required fields: study_type, findings"}

    technique = payload.get("technique", {})
    rest_normal = payload.get("rest_normal", False)
    important_fields = payload.get("important_fields")

    # Stage 2: Template lookup
    try:
        template = self._registry.get_template(study_type)
    except TemplateNotFoundError:
        return {"id": msg_id, "st": "E", "ct": "Unknown study type"}

    # Sex inference (D-20)
    sex = self._infer_sex(findings)
    if sex:
        findings = self._filter_sex_fields(findings, template, sex)

    # Audit logging (D-16)
    logger.info(f"[RENDER] ID: {msg_id} | Study: {study_type} | Fields: {len(findings)}")

    # Stage 4: Render
    report = render_report(
        template=template,
        findings=findings,
        technique=technique,
        important_fields=important_fields,
        rest_normal=rest_normal,
    )

    logger.info(f"[RENDER_OK] ID: {msg_id} | Length: {len(report)}")
    return {"id": msg_id, "st": "S", "ct": report}
```

### fn='report' Handler (Stubs Hit)
```python
# Source: Derived from CONTEXT.md D-01, D-15
def _handle_report(self, msg_id: str, draft: str) -> dict:
    """Handle fn='report' -- full 5-stage pipeline."""
    try:
        # Stage 1: Study type classification (LLM stub)
        study_type = self.classify_study_type(draft)
        # Stage 2: Template lookup
        template = self._registry.get_template(study_type)
        # Stage 3: Findings extraction (LLM stub)
        extraction = self.extract_findings(draft, template)
        # Stage 4: Render
        report = render_report(template=template, **extraction)
        # Stage 5: Impression (LLM stub)
        impression = self.generate_impression(report)
        final = f"{report}\n\nIMPRESSION:\n{impression}"
        return {"id": msg_id, "st": "S", "ct": final}
    except NotImplementedError as e:
        stage_msg = str(e) if str(e) else "unknown stage"
        return {"id": msg_id, "st": "E", "ct": f"Stage not implemented: {stage_msg} requires LLM connection"}
    except TemplateNotFoundError:
        return {"id": msg_id, "st": "E", "ct": "Unknown study type"}
    except Exception as e:
        logger.error(f"[PIPELINE_ERROR] ID: {msg_id} | Error: {e}")
        return {"id": msg_id, "st": "E", "ct": str(e)}
```

### backend.py Pipeline Instantiation
```python
# Source: Derived from CONTEXT.md D-17
import os
from lib.pipeline import TestPipeline, LLMPipeline

pipeline_mode = os.environ.get("PIPELINE_MODE", "test")
if pipeline_mode == "llm":
    pipeline = LLMPipeline()
    logger.info(f"Pipeline: LLMPipeline (mode={pipeline_mode})")
else:
    pipeline = TestPipeline()
    logger.info(f"Pipeline: TestPipeline (mode={pipeline_mode})")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `LLMPipeline` -- all 5 stages are stubs | Stages 2+4 get real implementations | Phase 6 | Pipeline can render pre-extracted data end-to-end |
| `backend.py` hardcodes `TestPipeline()` | Env var `PIPELINE_MODE` switches pipeline | Phase 6 | Operator can switch to LLM pipeline without code changes |
| No fn-based routing | `fn='render'` bypasses LLM stages | Phase 6 | Enables testing and research use without LLM connection |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already installed) |
| Config file | none -- pytest discovers tests/ automatically |
| Quick run command | `cd python-backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd python-backend && python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FWRK-02 | fn='render' routes through registry + renderer | integration | `python -m pytest tests/test_pipeline_integration.py -x` | Wave 0 |
| FWRK-02 | fn='report' hits stub stages, returns friendly error | unit | `python -m pytest tests/test_pipeline_integration.py::test_report_fn_stub_error -x` | Wave 0 |
| FWRK-02 | Unknown study type returns st='E' | unit | `python -m pytest tests/test_pipeline_integration.py::test_unknown_study_type -x` | Wave 0 |
| FWRK-02 | PIPELINE_MODE env var switches pipeline | unit | `python -m pytest tests/test_pipeline_integration.py::test_pipeline_mode_env -x` | Wave 0 |
| D-25 | Snapshot golden-file tests for 4 templates | snapshot | `python -m pytest tests/test_pipeline_snapshots.py -x` | Wave 0 |
| D-18 | Pipeline importable standalone without backend | unit | `python -m pytest tests/test_pipeline_integration.py::test_standalone_import -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd python-backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd python-backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline_integration.py` -- covers FWRK-02 integration + unit tests
- [ ] `tests/test_pipeline_snapshots.py` -- covers D-25 golden-file tests
- [ ] `tests/snapshots/` directory -- golden output files for US HBS, CT AP freeform, CT AP structured, CT TAP
- [ ] `tests/conftest.py` update -- add pipeline fixtures (LLMPipeline with test templates dir)

## Open Questions

1. **Sex filtering implementation details**
   - What we know: D-20 says infer sex from findings keys (prostate = male, uterus/ovaries = female). Template fields have `sex` tags.
   - What's unclear: How exactly to filter -- do we remove the findings keys for the opposite sex, or do we pass the sex to the renderer? The renderer currently does not accept a `sex` parameter; it relies on findings dict having only the relevant keys.
   - Recommendation: Filter findings dict before passing to `render_report()` -- remove keys for fields tagged with the opposite sex. This is the simplest approach and matches how the renderer already handles optional fields (None/missing = omitted).

2. **Registry template count for D-11 summary line**
   - What we know: The registry stores aliases, not unique templates. Multiple aliases map to the same template.
   - What's unclear: How to count "N templates" vs "M aliases" since the registry only exposes aliases.
   - Recommendation: Count unique `LoadedTemplate` objects (by identity) for "N templates" and `len(get_known_aliases())` for "M aliases". This can be done with `len(set(id(t) for t in self._alias_index.values()))`.

## Project Constraints (from CLAUDE.md)

- Python backend follows `snake_case` naming for functions/variables, `PascalCase` for classes
- Logging via module-level `logger` from `lib.config` (not `print()`)
- Error responses use `st='E'`, success uses `st='S'`
- Message protocol keys: `id`, `fn`, `ct`, `st`, `ci`, `cc`
- The LLM must never fabricate findings -- `__NOT_DOCUMENTED__` for unmentioned fields
- All logging is file-based to `backend_log.txt`
- Type hints used in function signatures
- Docstrings for modules, classes, and public functions

## Sources

### Primary (HIGH confidence)
- `python-backend/lib/pipeline.py` -- Current LLMPipeline stub code (read directly)
- `python-backend/lib/templates/registry.py` -- TemplateRegistry implementation (read directly)
- `python-backend/lib/templates/renderer.py` -- render_report() API and signature (read directly)
- `python-backend/backend.py` -- Current backend main loop and pipeline instantiation (read directly)
- `python-backend/lib/__init__.py` -- Public API exports (read directly)
- `.planning/phases/06-pipeline-integration/06-CONTEXT.md` -- All 27 locked decisions (read directly)

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` -- FWRK-02 requirement text (read directly)
- `.planning/STATE.md` -- Project history and accumulated decisions (read directly)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing code verified by reading source
- Architecture: HIGH -- all integration points inspected, APIs verified, code patterns clear
- Pitfalls: HIGH -- derived from actual code structure and import graph analysis

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable -- no external dependencies changing)
