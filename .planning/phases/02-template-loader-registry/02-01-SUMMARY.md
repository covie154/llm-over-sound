---
phase: 02-template-loader-registry
plan: 01
subsystem: templates
tags: [pydantic, python-frontmatter, dataclass, template-loading, file-discovery]

# Dependency graph
requires:
  - phase: 01-template-schema-data-model
    provides: "TemplateSchema, validate_body_placeholders, FieldDefinition models"
provides:
  - "lib/templates/ sub-package with schema, exceptions, loader modules"
  - "LoadedTemplate frozen dataclass for parsed template output"
  - "discover_templates() recursive file finder for *.rpt.md"
  - "load_template() single-file parser with validation"
  - "TemplateValidationError, TemplateNotFoundError, TemplateLoadError exceptions"
  - "5 test fixture templates (3 valid, 2 invalid) for registry tests"
affects: [02-template-loader-registry, 03-llm-pipeline-stages]

# Tech tracking
tech-stack:
  added: [python-frontmatter]
  patterns: [sub-package with __init__ re-exports, backward-compat shim, frozen dataclass, error collection pattern]

key-files:
  created:
    - python-backend/lib/templates/__init__.py
    - python-backend/lib/templates/schema.py
    - python-backend/lib/templates/exceptions.py
    - python-backend/lib/templates/loader.py
    - python-backend/tests/test_loader.py
    - python-backend/tests/fixtures/registry_fixtures/ct/ct_abdomen.rpt.md
    - python-backend/tests/fixtures/registry_fixtures/ct/ct_thorax.rpt.md
    - python-backend/tests/fixtures/registry_fixtures/us/us_hbs.rpt.md
    - python-backend/tests/fixtures/invalid/bad_frontmatter.rpt.md
    - python-backend/tests/fixtures/invalid/duplicate_alias.rpt.md
  modified:
    - python-backend/lib/__init__.py
    - python-backend/lib/template_schema.py
    - python-backend/tests/conftest.py

key-decisions:
  - "Backward-compat shim in template_schema.py uses star-import plus explicit re-imports to preserve all existing import paths"
  - "Standalone import test checks source code for audio imports rather than sys.modules (shared test session contaminates modules)"

patterns-established:
  - "Sub-package re-export: lib/templates/__init__.py re-exports all public API for clean imports"
  - "Backward-compat shim: old module replaced with re-export wrapper, keeping all existing imports working"
  - "Error collection: TemplateValidationError collects list[TemplateLoadError] before raising"

requirements-completed: [MTCH-01, FWRK-01]

# Metrics
duration: 4min
completed: 2026-03-28
---

# Phase 02 Plan 01: Template Loader and Sub-Package Summary

**Template sub-package with file discovery, YAML+markdown parsing via python-frontmatter, and error-collecting validation -- 41 tests green**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-28T15:26:41Z
- **Completed:** 2026-03-28T15:30:48Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments
- Reorganized template_schema.py into lib/templates/ sub-package with backward-compatible imports
- Created loader module with discover_templates() and load_template() using python-frontmatter
- Defined three custom exceptions (TemplateValidationError, TemplateNotFoundError, TemplateLoadError)
- Built 5 test fixture templates (3 valid CT/US, 2 invalid) for registry tests in Plan 02
- 10 new loader tests covering parsing, validation, discovery, placeholder fatality, and import isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create lib/templates/ sub-package with moved schema and backward-compatible imports** - `c3a1a1c` (feat)
2. **Task 2: Create test fixture templates and loader module** - `46d708d` (feat)
3. **Task 3: Create loader tests** - `c7ba70e` (test)

## Files Created/Modified
- `python-backend/lib/templates/__init__.py` - Sub-package with full re-exports of schema, exceptions, loader
- `python-backend/lib/templates/schema.py` - Moved TemplateSchema and all models from template_schema.py
- `python-backend/lib/templates/exceptions.py` - TemplateValidationError, TemplateNotFoundError, TemplateLoadError
- `python-backend/lib/templates/loader.py` - LoadedTemplate dataclass, discover_templates(), load_template()
- `python-backend/lib/template_schema.py` - Backward-compatibility shim re-exporting from sub-package
- `python-backend/lib/__init__.py` - Updated to import from templates sub-package, added exception exports
- `python-backend/tests/test_loader.py` - 10 loader unit tests
- `python-backend/tests/conftest.py` - Added registry_fixtures_dir and invalid_fixtures_dir fixtures
- `python-backend/tests/fixtures/registry_fixtures/ct/ct_abdomen.rpt.md` - CT abdomen fixture (3 fields, 1 group)
- `python-backend/tests/fixtures/registry_fixtures/ct/ct_thorax.rpt.md` - CT thorax fixture (2 fields)
- `python-backend/tests/fixtures/registry_fixtures/us/us_hbs.rpt.md` - US hepatobiliary fixture (2 fields)
- `python-backend/tests/fixtures/invalid/bad_frontmatter.rpt.md` - Missing technique field
- `python-backend/tests/fixtures/invalid/duplicate_alias.rpt.md` - Colliding "ct ap" alias

## Decisions Made
- Backward-compat shim uses both star-import and explicit named imports to ensure all symbols are available
- Standalone import test inspects module source code instead of sys.modules to avoid false positives from shared test session

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed standalone import test approach**
- **Found during:** Task 3 (loader tests)
- **Issue:** Plan suggested checking sys.modules for audio imports, but in a shared pytest session lib.__init__ imports audio modules for other test files, causing false positive
- **Fix:** Changed test to inspect source code of lib.templates modules for audio import statements instead
- **Files modified:** python-backend/tests/test_loader.py
- **Verification:** Test passes in both isolated and shared session runs
- **Committed in:** c7ba70e (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test approach corrected for accuracy. No scope creep.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all modules are fully implemented with no placeholder data.

## Next Phase Readiness
- lib/templates/ sub-package is ready for Plan 02 (registry) to build upon
- LoadedTemplate, discover_templates(), and load_template() provide the foundation for TemplateRegistry
- Test fixtures in registry_fixtures/ are ready for registry alias-lookup tests
- duplicate_alias fixture is ready for testing alias collision detection

## Self-Check: PASSED

All 10 created files verified present. All 3 task commits (c3a1a1c, 46d708d, c7ba70e) verified in git log. 41/41 tests passing.

---
*Phase: 02-template-loader-registry*
*Completed: 2026-03-28*
