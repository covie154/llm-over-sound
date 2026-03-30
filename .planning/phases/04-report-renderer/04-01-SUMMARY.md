---
phase: 04-report-renderer
plan: 01
subsystem: templates
tags: [renderer, pydantic, plain-text, radiology, template-engine]

requires:
  - phase: 03-base-template-authoring
    provides: Production templates (CT AP freeform/structured, CT thorax, US HBS) and test fixtures
  - phase: 02-template-loader-registry
    provides: LoadedTemplate dataclass, load_template function, TemplateRegistry
  - phase: 01-template-schema-data-model
    provides: TemplateSchema, FieldDefinition, FieldGroup, GroupPartial, NOT_DOCUMENTED, PLACEHOLDER_PATTERN
provides:
  - ReportRenderer base class with shared rendering logic
  - FreeformRenderer for prose-style report output
  - StructuredRenderer for table-to-plain-text conversion with Key/Other Findings
  - render_report() factory function dispatching on template variant field
  - variant field on TemplateSchema (Literal freeform/structured)
  - 4 minimal test fixture templates for renderer testing
  - 28 unit tests covering all renderer behaviors
affects: [05-composite-templates, 06-pipeline-integration]

tech-stack:
  added: []
  patterns: [two-pass placeholder substitution, factory dispatch on variant, schema override helper for testing]

key-files:
  created:
    - python-backend/lib/templates/renderer.py
    - python-backend/tests/test_renderer.py
    - python-backend/tests/fixtures/renderer/freeform_minimal.rpt.md
    - python-backend/tests/fixtures/renderer/structured_minimal.rpt.md
    - python-backend/tests/fixtures/renderer/groups_minimal.rpt.md
    - python-backend/tests/fixtures/renderer/measurements_minimal.rpt.md
  modified:
    - python-backend/lib/templates/schema.py
    - python-backend/lib/templates/__init__.py
    - python-backend/rpt_templates/ct/ct_ap.rpt.md
    - python-backend/rpt_templates/ct/ct_ap_structured.rpt.md
    - python-backend/rpt_templates/ct/ct_thorax.rpt.md
    - python-backend/rpt_templates/us/us_hbs.rpt.md
    - python-backend/tests/conftest.py
    - python-backend/tests/fixtures/sample_template.md

key-decisions:
  - "TABLE_ROW_PATTERN anchored with ^ and re.MULTILINE to prevent cross-line captures from separator rows"
  - "COMMENT section regex uses \\n? to handle templates ending without trailing newline"
  - "_with_schema_overrides helper pattern for testing schema flag variations without modifying fixture files"

patterns-established:
  - "Two-pass substitution: field/technique first, then measurements (for normal text containing measurement placeholders)"
  - "Factory dispatch via variant field: render_report() inspects template.schema.variant and instantiates the correct renderer subclass"
  - "Schema override helper for tests: _with_schema_overrides creates new LoadedTemplate with modified schema fields"

requirements-completed: [TMPL-04, TMPL-05, TMPL-06, TMPL-10, FLDS-03]

duration: 8min
completed: 2026-03-30
---

# Phase 4 Plan 1: Report Renderer Summary

**Report renderer with FreeformRenderer/StructuredRenderer subclasses, two-pass placeholder substitution, group collapse logic, and factory dispatch on template variant field**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-30T13:41:18Z
- **Completed:** 2026-03-30T13:49:46Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments
- Built complete renderer module with base class (shared logic for interpolation, groups, technique, measurements, guidance stripping, impression, headers, blank lines, validation) and two subclass variants
- Added variant field to TemplateSchema and updated all 4 production templates with explicit variant values
- Created 4 minimal test fixture templates and 28 unit tests covering all renderer behaviors (96 total tests passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add variant field to schema, update templates, create test fixtures** - `618f0b9` (feat)
2. **Task 2: Build renderer module with base class, subclasses, and factory function** - `b97d878` (feat)
3. **Task 3: Comprehensive unit tests for renderer behaviors** - `a10d31c` (test)

## Files Created/Modified
- `python-backend/lib/templates/renderer.py` - Core renderer module: ReportRenderer base, FreeformRenderer, StructuredRenderer, render_report factory
- `python-backend/lib/templates/schema.py` - Added variant: Literal["freeform", "structured"] field to TemplateSchema
- `python-backend/lib/templates/__init__.py` - Exported renderer classes and factory function
- `python-backend/tests/test_renderer.py` - 28 unit tests covering interpolation, groups, impression, important_first, structured, measurements, etc.
- `python-backend/tests/conftest.py` - Added renderer fixture loaders (freeform, structured, groups, measurements templates)
- `python-backend/tests/fixtures/renderer/*.rpt.md` - 4 minimal test fixture templates
- `python-backend/rpt_templates/ct/ct_ap.rpt.md` - Added variant: "freeform"
- `python-backend/rpt_templates/ct/ct_ap_structured.rpt.md` - Added variant: "structured"
- `python-backend/rpt_templates/ct/ct_thorax.rpt.md` - Added variant: "freeform"
- `python-backend/rpt_templates/us/us_hbs.rpt.md` - Added variant: "freeform"
- `python-backend/tests/fixtures/sample_template.md` - Added explicit variant: "freeform"

## Decisions Made
- TABLE_ROW_PATTERN anchored with `^` and `re.MULTILINE` to prevent the regex from starting a match in the table separator line and capturing a leading `|` in the label
- COMMENT section regex uses `\n?` instead of requiring `\n` to handle templates where `## COMMENT` is the last line without a trailing newline
- Used `_with_schema_overrides` helper pattern for tests to create modified templates without duplicating fixture files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TABLE_ROW_PATTERN capturing leading pipe from separator row**
- **Found during:** Task 3 (test_structured_table_to_plain)
- **Issue:** TABLE_ROW_PATTERN without line anchor would start matching at the `|` in the separator row `|-------|--------|`, causing `(.+?)` to capture `| Liver` instead of `Liver`
- **Fix:** Added `^` anchor and `re.MULTILINE` flag to TABLE_ROW_PATTERN
- **Files modified:** python-backend/lib/templates/renderer.py
- **Verification:** test_structured_table_to_plain passes, no pipe chars in output
- **Committed in:** a10d31c (Task 3 commit)

**2. [Rule 1 - Bug] COMMENT section regex failing on templates without trailing newline**
- **Found during:** Task 3 (test_impression_true_no_callable)
- **Issue:** Regex `(^## COMMENT\s*\n).*` required a newline after COMMENT but template body ended with `## COMMENT` (no trailing newline)
- **Fix:** Changed to `(^## COMMENT\s*\n?).*` to make the newline optional
- **Files modified:** python-backend/lib/templates/renderer.py
- **Verification:** test_impression_true_no_callable passes
- **Committed in:** a10d31c (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the bugs caught by tests (documented above as deviations).

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all renderer behaviors are fully implemented.

## Next Phase Readiness
- Renderer module complete and tested, ready for composite template support (Phase 5)
- Pipeline integration (Phase 6) can call render_report() factory function directly
- generate_impression callable interface defined and tested with both callable and None paths

---
*Phase: 04-report-renderer*
*Completed: 2026-03-30*
