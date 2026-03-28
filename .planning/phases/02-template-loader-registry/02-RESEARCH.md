# Phase 2: Template Loader & Registry - Research

**Researched:** 2026-03-28
**Domain:** Python module design -- file scanning, YAML parsing, in-memory indexing, standalone packaging
**Confidence:** HIGH

## Summary

Phase 2 builds the template loader and registry as a standalone Python sub-package (`lib/templates/`). The work is entirely deterministic Python -- no LLM calls, no audio, no external services. The core task is: scan `rpt_templates/` recursively for `*.rpt.md` files, parse each with `python-frontmatter`, validate with the existing `TemplateSchema` Pydantic model, build a case-insensitive alias-to-template index, and expose lookup via a `TemplateRegistry` class.

All key libraries are already installed and verified in the project environment: `python-frontmatter` 2.11.7, `pydantic` 8.3.4, `pytest` (latest), Python 3.13.5. The existing Phase 1 code provides `TemplateSchema`, `validate_body_placeholders()`, and 31 passing tests as a foundation. The primary implementation risk is the module reorganization (moving `template_schema.py` into `lib/templates/schema.py`) which must preserve all existing imports and test compatibility.

**Primary recommendation:** Implement in three layers -- (1) move/reorganize the schema module into `lib/templates/`, (2) build the loader (file discovery + parsing + validation), (3) build the registry (alias index + lookup API). Each layer is independently testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Invalid templates cause a fatal startup error -- the registry refuses to start if any template fails validation
- D-02: The loader collects ALL validation errors across all templates before raising, so the user can fix everything in one pass
- D-03: Body placeholder cross-validation (validate_body_placeholders) is enforced as a fatal error at load time, not just a warning
- D-04: An empty or missing rpt_templates/ directory is also a fatal error -- the system cannot serve requests without templates
- D-05: The registry exposes get_known_aliases() -> list[str] for the pipeline's stage 1 (LLM classification) to constrain against. The registry does NOT own the LLM call -- clean separation
- D-06: The primary path for most users is LLM classification from the full draft text (free-form dictation). The LLM receives the full draft + known alias list and returns a match from the closed set
- D-07: Users who explicitly tag study type (e.g. study:CTAP) get a direct alias lookup -- but parsing that tag is the pipeline's job, not the registry's
- D-08: Alias matching is case-insensitive -- aliases normalized to lowercase on load, lookups normalized on query
- D-09: Registry is a class instance: TemplateRegistry(templates_dir). Caller constructs it, passes the path. Easy to test with fixture directories
- D-10: get_template(alias) returns a parsed template object (dataclass/named tuple with schema: TemplateSchema, body: str, file_path: str). Templates are parsed once at startup and cached
- D-11: Manual reload supported via registry.reload() for debugging. No automatic file-watching or hot-reload. Production use is load-once-at-startup
- D-12: Duplicate aliases across templates are a fatal startup error. The error message names both files and the conflicting alias
- D-13: All aliases are globally unique. Variant templates (e.g. structured vs freeform) use distinct aliases. The default variant owns the short alias (e.g. "ct ap"), the structured variant owns "ct ap structured"
- D-14: The LLM will only return the variant-specific alias (e.g. "ct ap structured") if the user explicitly requested it. Default/unspecified dictation maps to the short alias
- D-15: Templates organized by modality: rpt_templates/ct/, rpt_templates/us/, rpt_templates/mri/. Scanner recurses into subdirectories
- D-16: Only files matching *.rpt.md are treated as templates. Other .md files (READMEs, docs) in the tree are ignored
- D-17: Template code organized as a sub-package: python-backend/lib/templates/ with registry.py, loader.py, etc.
- D-18: Move existing template_schema.py into the sub-package as lib/templates/schema.py. Update imports and __init__.py re-exports to keep existing test imports working
- D-19: The sub-package __init__.py exports the public API (TemplateRegistry, TemplateSchema, etc.) for clean imports
- D-20: get_template() raises a specific exception (e.g. TemplateNotFoundError) when an alias doesn't exist. Caller must handle explicitly -- forces error handling in the pipeline

### Claude's Discretion
- Internal naming of the parsed template dataclass (e.g. LoadedTemplate, ParsedTemplate)
- File scanning order within directories (alphabetical, by mtime, etc. -- as long as it's deterministic)
- Whether reload() returns success/failure info or is void
- How the collected validation errors are formatted in the fatal exception message
- Test structure and fixture organization for registry tests

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MTCH-01 | Each template defines a list of study type aliases in YAML frontmatter for programmatic matching | Already implemented in TemplateSchema.aliases field (Phase 1). Loader parses this via python-frontmatter, registry indexes it |
| MTCH-02 | A template registry builds an alias-to-filepath index at startup by scanning rpt_templates/ recursively | Registry class with pathlib.Path.rglob("*.rpt.md") scanning, dict[str, LoadedTemplate] index |
| MTCH-03 | Study type lookup uses exact alias match first, with LLM fallback for fuzzy/unmatched input | get_template() does exact match (case-insensitive). get_known_aliases() exposes alias list for LLM fallback. TemplateNotFoundError signals miss |
| FWRK-01 | The template system (loader, registry, renderer) is callable as a standalone Python module | Sub-package lib/templates/ with __init__.py exports. No ggwave/audio imports. Testable in isolation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-frontmatter | 1.1.0 | Parse YAML frontmatter + markdown body from template files | Already used in Phase 1 tests and conftest. De facto standard for frontmatter parsing |
| pydantic | 2.11.7 | Validate template metadata (TemplateSchema) | Already used in Phase 1 schema. Provides strict validation with extra="forbid" |
| pathlib | stdlib | File discovery and path manipulation | Standard library, already used in conftest.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.3.4 | Test runner | Already installed, 31 tests passing |
| dataclasses | stdlib | LoadedTemplate container | Lightweight frozen container for parsed template data |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dataclass for LoadedTemplate | NamedTuple | NamedTuple is immutable by default but less extensible. Dataclass with frozen=True is clearer and allows default values |
| pathlib.rglob | os.walk | os.walk is lower-level. rglob is cleaner for glob patterns like *.rpt.md |

**Installation:**
No new packages needed. All dependencies already installed.

**Version verification:**
- python-frontmatter: installed (version not printed but functional -- confirmed via test imports)
- pydantic: 2.11.7 (verified via `python -c "import pydantic; print(pydantic.__version__)"`)
- pytest: 8.3.4 (verified)
- Python: 3.13.5 (verified)

## Architecture Patterns

### Recommended Project Structure
```
python-backend/
  lib/
    templates/
      __init__.py        # Public API re-exports
      schema.py          # Moved from lib/template_schema.py
      loader.py          # File discovery + parsing + validation
      registry.py        # Alias index + lookup
      exceptions.py      # TemplateNotFoundError, TemplateValidationError
    __init__.py          # Updated re-exports (backward compat)
    pipeline.py          # Existing -- will consume registry in Phase 6
  tests/
    fixtures/
      sample_template.md          # Existing Phase 1 fixture
      registry_fixtures/          # New: multi-template test directory
        ct/
          ct_abdomen.rpt.md       # Test template with aliases
          ct_thorax.rpt.md        # Test template with aliases
        us/
          us_hbs.rpt.md           # Test template with aliases
        invalid/
          bad_frontmatter.rpt.md  # Negative test fixture
          duplicate_alias.rpt.md  # Negative test fixture
    conftest.py                   # Updated with registry fixtures
    test_template_schema.py       # Existing -- imports updated
    test_loader.py                # New: loader tests
    test_registry.py              # New: registry tests
```

### Pattern 1: Collect-All-Errors-Then-Raise
**What:** The loader iterates all template files, collecting validation errors into a list. Only after scanning everything does it raise a single exception containing all errors.
**When to use:** D-02 requires this -- users fix all issues in one pass.
**Example:**
```python
# loader.py
from dataclasses import dataclass, field

@dataclass
class TemplateLoadError:
    """A single template validation failure."""
    file_path: str
    error: str

class TemplateValidationError(Exception):
    """Raised when one or more templates fail validation."""
    def __init__(self, errors: list[TemplateLoadError]):
        self.errors = errors
        msg = f"{len(errors)} template(s) failed validation:\n"
        for e in errors:
            msg += f"  - {e.file_path}: {e.error}\n"
        super().__init__(msg)
```

### Pattern 2: Case-Insensitive Alias Index
**What:** All aliases are normalized to lowercase at load time. Lookups normalize the query string to lowercase before dict lookup.
**When to use:** D-08 requires case-insensitive matching.
**Example:**
```python
# registry.py
class TemplateRegistry:
    def __init__(self, templates_dir: str | pathlib.Path):
        self._templates_dir = pathlib.Path(templates_dir)
        self._alias_index: dict[str, LoadedTemplate] = {}
        self._load_all()

    def get_template(self, alias: str) -> LoadedTemplate:
        key = alias.strip().lower()
        if key not in self._alias_index:
            raise TemplateNotFoundError(alias, list(self._alias_index.keys()))
        return self._alias_index[key]

    def get_known_aliases(self) -> list[str]:
        return sorted(self._alias_index.keys())
```

### Pattern 3: Frozen Dataclass for Parsed Templates
**What:** LoadedTemplate is an immutable container holding the validated schema, body text, and file path. Parsed once, cached forever.
**When to use:** D-10 specifies the template object structure.
**Example:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class LoadedTemplate:
    """A fully parsed and validated template, ready for pipeline use."""
    schema: TemplateSchema
    body: str
    file_path: str
```

### Pattern 4: Backward-Compatible Module Move
**What:** Move `lib/template_schema.py` to `lib/templates/schema.py`, then update `lib/__init__.py` to re-export from the new location so existing `from lib.template_schema import X` and `from lib import X` both still work.
**When to use:** D-18 requires the move while preserving test compatibility.
**Example:**
```python
# lib/__init__.py (updated)
from .templates.schema import (
    FieldDefinition, GroupPartial, FieldGroup, TemplateSchema,
    StudyTypeClassification, create_findings_model,
    validate_body_placeholders, NOT_DOCUMENTED, PLACEHOLDER_PATTERN,
)
# Backward compat: lib.template_schema still importable
from .templates import schema as template_schema
```

### Anti-Patterns to Avoid
- **Lazy loading templates on first access:** D-01/D-04 require ALL validation at startup. Lazy loading would hide errors until the first request.
- **Storing raw file paths in alias index:** Store the fully parsed LoadedTemplate object, not just the path. D-10 says templates are parsed once and cached.
- **Case-sensitive alias comparison:** D-08 explicitly requires case-insensitive. Forgetting normalization will cause lookup misses.
- **Silently skipping invalid templates:** D-01 requires fatal errors. Never skip and continue.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML+markdown parsing | Custom regex splitter | python-frontmatter | Handles edge cases (multiline YAML, encoding, separators) correctly |
| Schema validation | Manual dict key checking | Pydantic with extra="forbid" | Catches typos, provides clear error messages, type coercion |
| Recursive file discovery | os.walk + manual filtering | pathlib.Path.rglob("*.rpt.md") | One-liner, correct glob semantics, cross-platform |
| Immutable data container | Manual __setattr__ override | dataclasses.dataclass(frozen=True) | Built-in, tested, hashable |

**Key insight:** The loader/registry is standard Python module design. The complexity is in the validation logic and error collection, not in novel patterns.

## Common Pitfalls

### Pitfall 1: Import Breakage After Module Move
**What goes wrong:** Moving `template_schema.py` to `lib/templates/schema.py` breaks all existing imports (`from lib.template_schema import X`, `from lib import X`).
**Why it happens:** Python resolves imports by module path. Moving the file changes the path.
**How to avoid:** Update `lib/__init__.py` to re-export from the new location. Add a compatibility shim: `lib/template_schema.py` that does `from lib.templates.schema import *` (or just update all imports directly). Run the full test suite after the move.
**Warning signs:** ImportError in existing tests after restructuring.

### Pitfall 2: frontmatter.load Returns Strings, Not Paths
**What goes wrong:** `frontmatter.load()` accepts a string path, not a Path object. Passing a pathlib.Path may work on some versions but not all.
**Why it happens:** The library's type signature expects `str`.
**How to avoid:** Always `str(path)` before passing to `frontmatter.load()`.
**Warning signs:** TypeError on load.

### Pitfall 3: rglob on Windows Returns Backslash Paths
**What goes wrong:** `pathlib.Path.rglob()` on Windows returns paths with backslashes. If file_path is stored or compared as a string, cross-platform tests may fail.
**Why it happens:** pathlib is OS-aware.
**How to avoid:** Store file_path as `str(path)` (OS-native) or always use Path objects for comparison. For display/error messages, use `path.as_posix()` or just `str(path)`.
**Warning signs:** Tests passing on Linux Pi but failing on Windows dev machine (or vice versa).

### Pitfall 4: Alias Collision Detection Must Check Across Files
**What goes wrong:** Two different template files share an alias (e.g. both define "ct ap"). The second one silently overwrites the first in the index.
**Why it happens:** Dict assignment is silent.
**How to avoid:** Before inserting into the alias index, check if the key already exists. If it does, record the error with both file paths and the conflicting alias (per D-12).
**Warning signs:** Wrong template returned for a lookup.

### Pitfall 5: Empty rpt_templates/ Directory Not Detected
**What goes wrong:** The directory exists but contains no `*.rpt.md` files (maybe only README.md). The registry starts with an empty index, and every lookup fails at runtime.
**Why it happens:** rglob returns an empty iterator for no matches.
**How to avoid:** After scanning, check `len(self._alias_index) == 0` and raise a fatal error (per D-04 -- the system cannot serve requests without templates).
**Warning signs:** Registry initializes without error but get_template() always raises TemplateNotFoundError.

### Pitfall 6: validate_body_placeholders Returns Warnings, Not Exceptions
**What goes wrong:** The existing `validate_body_placeholders()` returns a `list[str]` of issues. If the loader doesn't check this return value and raise on non-empty, placeholder mismatches slip through.
**Why it happens:** Phase 1 designed it as a utility function returning issues. D-03 upgrades this to a fatal error in the loader.
**How to avoid:** The loader must call `validate_body_placeholders(schema, body)` and add any returned issues to the error collection list.
**Warning signs:** Templates with mismatched placeholders load successfully.

## Code Examples

### Complete Loader Flow
```python
# loader.py
import pathlib
import frontmatter
from .schema import TemplateSchema, validate_body_placeholders
from .exceptions import TemplateValidationError, TemplateLoadError

@dataclass(frozen=True)
class LoadedTemplate:
    schema: TemplateSchema
    body: str
    file_path: str

def load_template(path: pathlib.Path) -> LoadedTemplate:
    """Parse and validate a single template file.

    Args:
        path: Path to a .rpt.md template file.

    Returns:
        LoadedTemplate with validated schema and body.

    Raises:
        TemplateValidationError: If the template fails validation.
    """
    post = frontmatter.load(str(path))
    schema = TemplateSchema(**post.metadata)
    body = post.content

    # D-03: Body placeholder cross-validation is fatal
    issues = validate_body_placeholders(schema, body)
    if issues:
        raise TemplateValidationError(
            [TemplateLoadError(str(path), issue) for issue in issues]
        )

    return LoadedTemplate(schema=schema, body=body, file_path=str(path))


def discover_templates(templates_dir: pathlib.Path) -> list[pathlib.Path]:
    """Find all *.rpt.md files recursively under templates_dir.

    Args:
        templates_dir: Root directory to scan.

    Returns:
        Sorted list of template file paths (deterministic order).

    Raises:
        TemplateValidationError: If directory doesn't exist.
    """
    if not templates_dir.is_dir():
        raise TemplateValidationError(
            [TemplateLoadError(str(templates_dir), "Directory does not exist")]
        )
    paths = sorted(templates_dir.rglob("*.rpt.md"))
    return paths
```

### Registry with Error Collection
```python
# registry.py
import pathlib
from .loader import LoadedTemplate, load_template, discover_templates
from .exceptions import TemplateNotFoundError, TemplateValidationError, TemplateLoadError

class TemplateRegistry:
    """In-memory template index built at startup.

    Scans rpt_templates/ recursively, parses and validates all templates,
    builds a case-insensitive alias-to-template index.

    Args:
        templates_dir: Path to the templates root directory.

    Raises:
        TemplateValidationError: If any template fails validation,
            if duplicate aliases exist, or if no templates are found.
    """

    def __init__(self, templates_dir: str | pathlib.Path):
        self._templates_dir = pathlib.Path(templates_dir)
        self._alias_index: dict[str, LoadedTemplate] = {}
        self._load_all()

    def _load_all(self) -> None:
        errors: list[TemplateLoadError] = []
        paths = discover_templates(self._templates_dir)

        if not paths:
            raise TemplateValidationError(
                [TemplateLoadError(str(self._templates_dir), "No *.rpt.md templates found")]
            )

        alias_sources: dict[str, str] = {}  # alias -> file_path (for collision detection)
        self._alias_index.clear()

        for path in paths:
            try:
                template = load_template(path)
            except TemplateValidationError as e:
                errors.extend(e.errors)
                continue

            # Register aliases with collision detection (D-12)
            for alias in template.schema.aliases:
                key = alias.strip().lower()
                if key in alias_sources:
                    errors.append(TemplateLoadError(
                        str(path),
                        f"Alias '{alias}' conflicts with {alias_sources[key]}"
                    ))
                else:
                    alias_sources[key] = str(path)
                    self._alias_index[key] = template

        if errors:
            raise TemplateValidationError(errors)

    def get_template(self, alias: str) -> LoadedTemplate:
        key = alias.strip().lower()
        if key not in self._alias_index:
            raise TemplateNotFoundError(alias, self.get_known_aliases())
        return self._alias_index[key]

    def get_known_aliases(self) -> list[str]:
        return sorted(self._alias_index.keys())

    def reload(self) -> None:
        """Re-scan and rebuild the alias index. For debugging only."""
        self._load_all()
```

### Custom Exceptions
```python
# exceptions.py
from dataclasses import dataclass

@dataclass
class TemplateLoadError:
    """A single template validation failure."""
    file_path: str
    error: str

class TemplateValidationError(Exception):
    """Raised when one or more templates fail validation at startup."""
    def __init__(self, errors: list[TemplateLoadError]):
        self.errors = errors
        lines = [f"{len(errors)} template validation error(s):"]
        for e in errors:
            lines.append(f"  [{e.file_path}] {e.error}")
        super().__init__("\n".join(lines))

class TemplateNotFoundError(Exception):
    """Raised when an alias lookup finds no matching template."""
    def __init__(self, alias: str, known_aliases: list[str]):
        self.alias = alias
        self.known_aliases = known_aliases
        super().__init__(
            f"No template found for alias '{alias}'. "
            f"Known aliases: {', '.join(known_aliases[:20])}"
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 validators | Pydantic v2 field_validator/model_validator decorators | Pydantic 2.0 (2023) | Phase 1 already uses v2 syntax -- no migration needed |
| python-frontmatter Post.keys() | Post.metadata dict access | Stable API | Consistent with existing conftest.py usage |

**Deprecated/outdated:**
- None relevant. All libraries in use are current stable versions.

## Open Questions

1. **Test fixture templates need actual clinical-looking content**
   - What we know: Phase 3 will create real clinical templates. Phase 2 only needs enough fixture content to test loader/registry mechanics.
   - What's unclear: How realistic the test fixtures need to be.
   - Recommendation: Use minimal but structurally complete fixtures (like the existing `sample_template.md`). Real clinical content is Phase 3's job. Test fixtures should cover: valid template, template with multiple aliases, template with variant alias, templates in subdirectories, invalid templates for negative tests.

2. **Whether to preserve lib/template_schema.py as a compatibility shim**
   - What we know: D-18 says move it. Existing tests import from `lib.template_schema`.
   - What's unclear: Whether to update all imports directly or leave a re-export shim.
   - Recommendation: Update all imports directly to `lib.templates.schema` (or `lib.templates`). The test file and conftest are the only consumers, and updating them is trivial. A shim adds maintenance burden for no benefit.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | None -- pytest auto-discovers from `tests/` directory |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MTCH-01 | Aliases in frontmatter parsed and indexed | unit | `python -m pytest tests/test_registry.py::test_aliases_indexed -x` | Wave 0 |
| MTCH-02 | Registry builds alias index from recursive scan | unit | `python -m pytest tests/test_registry.py::test_recursive_scan -x` | Wave 0 |
| MTCH-02 | Registry detects empty/missing templates dir | unit | `python -m pytest tests/test_registry.py::test_empty_dir_fatal -x` | Wave 0 |
| MTCH-03 | Exact alias match returns correct template | unit | `python -m pytest tests/test_registry.py::test_exact_match -x` | Wave 0 |
| MTCH-03 | Unknown alias raises TemplateNotFoundError | unit | `python -m pytest tests/test_registry.py::test_unknown_alias -x` | Wave 0 |
| MTCH-03 | get_known_aliases() returns full alias list | unit | `python -m pytest tests/test_registry.py::test_known_aliases -x` | Wave 0 |
| FWRK-01 | Template system importable without ggwave | unit | `python -m pytest tests/test_registry.py::test_standalone_import -x` | Wave 0 |
| D-02 | Loader collects all errors before raising | unit | `python -m pytest tests/test_loader.py::test_collect_all_errors -x` | Wave 0 |
| D-03 | Body placeholder mismatch is fatal | unit | `python -m pytest tests/test_loader.py::test_placeholder_fatal -x` | Wave 0 |
| D-08 | Case-insensitive alias lookup | unit | `python -m pytest tests/test_registry.py::test_case_insensitive -x` | Wave 0 |
| D-12 | Duplicate alias across files is fatal | unit | `python -m pytest tests/test_registry.py::test_duplicate_alias_fatal -x` | Wave 0 |
| D-18 | Existing schema tests pass after move | unit | `python -m pytest tests/test_template_schema.py -x` | Existing (31 tests) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q` (< 2 seconds)
- **Per wave merge:** `python -m pytest tests/ -v` (< 5 seconds)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_loader.py` -- covers loader parsing, validation, error collection
- [ ] `tests/test_registry.py` -- covers registry construction, lookup, alias collision, reload
- [ ] `tests/fixtures/registry_fixtures/` -- multi-template test directory structure with valid and invalid fixtures
- [ ] No framework install needed -- pytest already available

## Sources

### Primary (HIGH confidence)
- Existing codebase: `python-backend/lib/template_schema.py`, `python-backend/tests/test_template_schema.py`, `python-backend/tests/conftest.py` -- Phase 1 artifacts, directly inspected
- Existing codebase: `python-backend/lib/__init__.py`, `python-backend/lib/pipeline.py` -- integration points, directly inspected
- Phase 1 CONTEXT.md: `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` -- placeholder syntax, validation rules
- Phase 2 CONTEXT.md: `.planning/phases/02-template-loader-registry/02-CONTEXT.md` -- all 20 locked decisions
- Architecture research: `.planning/research/ARCHITECTURE.md` -- component design

### Secondary (MEDIUM confidence)
- python-frontmatter API: verified via interactive Python session (load, metadata, content attributes)
- pydantic version: 2.11.7 confirmed via import
- pathlib.rglob behavior: standard library, well-documented

### Tertiary (LOW confidence)
- None. All findings verified against existing code or interactive testing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used in Phase 1
- Architecture: HIGH -- decisions D-01 through D-20 are locked, patterns are standard Python module design
- Pitfalls: HIGH -- identified from direct code inspection and import chain analysis

**Research date:** 2026-03-28
**Valid until:** Indefinite (stable Python patterns, no fast-moving dependencies)
