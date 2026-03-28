# Phase 2: Template Loader & Registry - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-28
**Phase:** 02-template-loader-registry
**Areas discussed:** Loader error handling, LLM fallback interface, Registry API design, Alias collision handling, Template directory structure, Module packaging, Lookup miss behavior

---

## Loader Error Handling

### Q1: When a template file fails Pydantic validation during startup scan, what should happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Log and skip | Invalid templates logged and excluded, others still load | |
| Abort startup | Any invalid template is fatal — registry refuses to start | ✓ |
| Log, skip, and surface | Like log and skip but exposes failed list to calling code | |

**User's choice:** Abort startup
**Notes:** None

### Q2: Should the abort collect ALL validation errors first, or fail on the first bad template?

| Option | Description | Selected |
|--------|-------------|----------|
| Collect all errors | Scan all templates, accumulate failures, raise single error listing all | ✓ |
| Fail on first | Stop on first invalid template | |

**User's choice:** Collect all errors
**Notes:** None

### Q3: Should body placeholder cross-validation also be enforced as a fatal error?

| Option | Description | Selected |
|--------|-------------|----------|
| Fatal error | Placeholder mismatches are validation failures — part of abort behavior | ✓ |
| Warnings only | Log mismatches but still load the template | |

**User's choice:** Fatal error
**Notes:** None

### Q4: If rpt_templates/ is empty or missing at startup, should that be fatal?

| Option | Description | Selected |
|--------|-------------|----------|
| Fatal if empty | No templates = nothing to serve, system shouldn't start | ✓ |
| Allow empty startup | Start with empty registry for dev/testing | |

**User's choice:** Fatal if empty
**Notes:** None

---

## LLM Fallback Interface

### Q1: What information should the LLM fallback receive to resolve an unmatched study type?

| Option | Description | Selected |
|--------|-------------|----------|
| User text + alias list | Pass unmatched input string and known aliases | |
| User text + alias list + study names | Also include study_name for each template | |
| User text + full draft context | Pass entire radiologist draft plus aliases | ✓ |

**User's choice:** Other (closest to option 3)
**Notes:** Dictation will be free-form with no structure forced. Users will dictate free text and the LLM parses this into the template structure. There will be no GUI in the final version. While the user's text usually defines the study name explicitly (e.g. "study:CTAP"), other users may not do this. The LLM should infer the template to match to from the full draft content.

### Q2: Should the registry expose an alias list, or own the LLM call itself?

| Option | Description | Selected |
|--------|-------------|----------|
| Registry exposes alias list | get_known_aliases() -> list[str], pipeline stage 1 handles LLM | ✓ |
| Registry owns LLM fallback | Registry has resolve(draft_text) with injected LLM classifier | |
| Callback/strategy pattern | Registry accepts fallback_resolver callback | |

**User's choice:** Registry exposes alias list
**Notes:** None

### Q3: Should alias matching be case-insensitive?

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive | Normalize to lowercase on load | ✓ |
| Case-sensitive | Exact match required | |

**User's choice:** Case-insensitive
**Notes:** None

### Q4: Should the registry define parsing for explicit study tags (e.g. 'study:CTAP')?

| Option | Description | Selected |
|--------|-------------|----------|
| Pipeline's job | Registry does lookup by alias; tag parsing is pipeline stage 1 | ✓ |
| Registry parses it | Registry has convenience method to find tags in draft text | |

**User's choice:** Pipeline's job
**Notes:** None

### Process walkthrough requested:

User asked for the full end-to-end flow to be repeated. Confirmed the 9-step process: dictate -> AHK compress/transmit -> backend receive -> stage 1 LLM classify (using registry alias list) -> stage 2 template retrieval (registry lookup) -> stage 3 LLM extraction -> stage 4 rendering -> transmit back -> radiologist review.

---

## Registry API Design

### Q1: How should the registry be instantiated?

| Option | Description | Selected |
|--------|-------------|----------|
| Class instance | TemplateRegistry(templates_dir) — caller constructs, passes path | ✓ |
| Module-level singleton | registry = TemplateRegistry.load() at import time | |
| Module-level functions | Standalone functions with module-level state | |

**User's choice:** Class instance
**Notes:** None

### Q2: What should get_template() return?

| Option | Description | Selected |
|--------|-------------|----------|
| Parsed template object | Dataclass with schema, body, file_path — parsed once, cached | ✓ |
| File path only | Returns path, caller re-parses | |
| Schema + body tuple | (TemplateSchema, str) tuple | |

**User's choice:** Parsed template object
**Notes:** None

### Q3: Should the registry support hot-reload?

| Option | Description | Selected |
|--------|-------------|----------|
| No hot-reload | Load once at startup, restart to pick up changes | |
| Manual reload method | registry.reload() callable for debugging | ✓ |
| File watcher | Automatic file change detection | |

**User's choice:** Manual reload method
**Notes:** User wants reload for debugging, not needed in production.

---

## Alias Collision Handling

### Q1: When two templates define the same alias, what should happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Fatal error | Duplicate alias = broken registry, abort startup | ✓ |
| Last file wins | Silently overwrite | |
| Warn and skip second | First keeps alias, second logged as warning | |

**User's choice:** Fatal error
**Notes:** None

### Q2: Should variant templates share common aliases or must all be globally unique?

| Option | Description | Selected |
|--------|-------------|----------|
| Globally unique | Every alias across all templates must be unique | ✓ |
| Allow shared + variant suffix | Shared base alias with disambiguation logic | |

**User's choice:** Globally unique
**Notes:** One variant should be the default — not deliberately passing "structured" should invoke the default ct ap template, not the structured variant. The short alias belongs to the default.

---

## Template Directory Structure

### Q1: How should templates be organized under rpt_templates/?

| Option | Description | Selected |
|--------|-------------|----------|
| By modality | rpt_templates/ct/, rpt_templates/us/, rpt_templates/mri/ | ✓ |
| Flat directory | All templates in root of rpt_templates/ | |
| By body region | rpt_templates/thorax/, rpt_templates/abdomen/ | |

**User's choice:** By modality
**Notes:** None

### Q2: Should the scanner pick up any .md file, or a specific extension?

| Option | Description | Selected |
|--------|-------------|----------|
| Any .md file | Scan for *.md recursively | |
| Specific extension (.rpt.md) | Only *.rpt.md files treated as templates | ✓ |

**User's choice:** Specific extension (.rpt.md)
**Notes:** None

---

## Module Packaging

### Q1: How should loader/registry code be organized?

| Option | Description | Selected |
|--------|-------------|----------|
| Single file | lib/template_registry.py alongside template_schema.py | |
| Sub-package | lib/templates/ package with registry.py, loader.py, etc. | ✓ |
| Extend template_schema.py | Add to existing file | |

**User's choice:** Sub-package
**Notes:** None

### Q2: Should template_schema.py move into the sub-package?

| Option | Description | Selected |
|--------|-------------|----------|
| Move into sub-package | Move to lib/templates/schema.py, update imports | ✓ |
| Keep in lib/ | Stay at lib/template_schema.py, sub-package imports from it | |

**User's choice:** Move into sub-package
**Notes:** None

---

## Lookup Miss Behavior

### Q1: When get_template() is called with a nonexistent alias, what happens?

| Option | Description | Selected |
|--------|-------------|----------|
| Raise KeyError | Specific exception (e.g. TemplateNotFoundError) | ✓ |
| Return None | Caller checks for None | |
| get() with default pattern | Both raising and Optional variants | |

**User's choice:** Raise KeyError (specific exception)
**Notes:** None

---

## Claude's Discretion

- Internal naming of parsed template dataclass
- File scanning order within directories
- Whether reload() returns success/failure info or is void
- Validation error message formatting
- Test structure and fixture organization

## Deferred Ideas

None — discussion stayed within phase scope
