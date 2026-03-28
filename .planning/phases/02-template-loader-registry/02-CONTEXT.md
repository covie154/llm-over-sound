# Phase 2: Template Loader & Registry - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Discover template files on disk, parse and validate them, build a case-insensitive alias-to-template index, and expose lookup by study type alias — usable as a standalone Python module (FWRK-01). This phase delivers the loader (file scanning + parsing), the registry (alias index + lookup), and the module packaging. No LLM integration, no rendering, no clinical template content — those are later phases.

</domain>

<decisions>
## Implementation Decisions

### Loader Error Handling
- **D-01:** Invalid templates cause a fatal startup error — the registry refuses to start if any template fails validation
- **D-02:** The loader collects ALL validation errors across all templates before raising, so the user can fix everything in one pass
- **D-03:** Body placeholder cross-validation (`validate_body_placeholders`) is enforced as a fatal error at load time, not just a warning
- **D-04:** An empty or missing `rpt_templates/` directory is also a fatal error — the system cannot serve requests without templates

### LLM Fallback Interface
- **D-05:** The registry exposes `get_known_aliases() -> list[str]` for the pipeline's stage 1 (LLM classification) to constrain against. The registry does NOT own the LLM call — clean separation
- **D-06:** The primary path for most users is LLM classification from the full draft text (free-form dictation). The LLM receives the full draft + known alias list and returns a match from the closed set
- **D-07:** Users who explicitly tag study type (e.g. `study:CTAP`) get a direct alias lookup — but parsing that tag is the pipeline's job, not the registry's
- **D-08:** Alias matching is case-insensitive — aliases normalized to lowercase on load, lookups normalized on query

### Registry API Design
- **D-09:** Registry is a class instance: `TemplateRegistry(templates_dir)`. Caller constructs it, passes the path. Easy to test with fixture directories
- **D-10:** `get_template(alias)` returns a parsed template object (dataclass/named tuple with `schema: TemplateSchema`, `body: str`, `file_path: str`). Templates are parsed once at startup and cached
- **D-11:** Manual reload supported via `registry.reload()` for debugging. No automatic file-watching or hot-reload. Production use is load-once-at-startup

### Alias Collision Handling
- **D-12:** Duplicate aliases across templates are a fatal startup error. The error message names both files and the conflicting alias
- **D-13:** All aliases are globally unique. Variant templates (e.g. structured vs freeform) use distinct aliases. The default variant owns the short alias (e.g. "ct ap"), the structured variant owns "ct ap structured"
- **D-14:** The LLM will only return the variant-specific alias (e.g. "ct ap structured") if the user explicitly requested it. Default/unspecified dictation maps to the short alias

### Template Directory Structure
- **D-15:** Templates organized by modality: `rpt_templates/ct/`, `rpt_templates/us/`, `rpt_templates/mri/`. Scanner recurses into subdirectories
- **D-16:** Only files matching `*.rpt.md` are treated as templates. Other `.md` files (READMEs, docs) in the tree are ignored

### Module Packaging
- **D-17:** Template code organized as a sub-package: `python-backend/lib/templates/` with `registry.py`, `loader.py`, etc.
- **D-18:** Move existing `template_schema.py` into the sub-package as `lib/templates/schema.py`. Update imports and `__init__.py` re-exports to keep existing test imports working
- **D-19:** The sub-package `__init__.py` exports the public API (TemplateRegistry, TemplateSchema, etc.) for clean imports

### Lookup Miss Behavior
- **D-20:** `get_template()` raises a specific exception (e.g. `TemplateNotFoundError`) when an alias doesn't exist. Caller must handle explicitly — forces error handling in the pipeline

### Claude's Discretion
- Internal naming of the parsed template dataclass (e.g. `LoadedTemplate`, `ParsedTemplate`)
- File scanning order within directories (alphabetical, by mtime, etc. — as long as it's deterministic)
- Whether `reload()` returns success/failure info or is void
- How the collected validation errors are formatted in the fatal exception message
- Test structure and fixture organization for registry tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Documentation
- `CLAUDE.md` — Master project documentation including report structure, pipeline stages, key constraints, and audio channel specs
- `python-backend/CLAUDE.md` — Backend-specific documentation including pipeline stage details and safety requirements

### Phase 1 Artifacts
- `.planning/phases/01-template-schema-data-model/01-CONTEXT.md` — Phase 1 decisions including placeholder syntax (D-01–D-04), field groups (D-05–D-12), validation strictness (D-26–D-28), and LLM output schema (D-16–D-21)

### Existing Code
- `python-backend/lib/template_schema.py` — Current location of TemplateSchema, FieldDefinition, FieldGroup, StudyTypeClassification, create_findings_model(), validate_body_placeholders() — will be moved to lib/templates/schema.py
- `python-backend/lib/pipeline.py` — ReportPipeline base class with retrieve_template() stub
- `python-backend/lib/__init__.py` — Current public API exports
- `python-backend/tests/test_template_schema.py` — Existing schema validation tests (31 tests) — imports will need updating after move

### Research
- `.planning/research/SUMMARY.md` — Stack recommendations (python-frontmatter, Pydantic 2.10+)
- `.planning/research/ARCHITECTURE.md` — Component design including registry/loader architecture

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 2 requirements: MTCH-01, MTCH-02, MTCH-03, FWRK-01

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TemplateSchema` Pydantic model — validates YAML frontmatter, already has aliases field and strict validation
- `validate_body_placeholders()` — cross-validates frontmatter fields against body placeholders, will be called by the loader
- `StudyTypeClassification` model — defines the LLM output for stage 1, references aliases from the registry
- `create_findings_model()` — generates dynamic Pydantic model per template, will be part of the parsed template object

### Established Patterns
- Pydantic `ConfigDict(extra="forbid")` for strict validation
- Type hints on all function signatures
- Modular structure under `python-backend/lib/` with `__init__.py` exports
- `python-frontmatter` for YAML+markdown parsing (from research recommendations)

### Integration Points
- `LLMPipeline.retrieve_template()` stub in `pipeline.py` — will call `registry.get_template()`
- `rpt_templates/` directory under `python-backend/` — empty, awaiting Phase 3 content
- `python-backend/tests/fixtures/` — test fixture templates exist here for schema tests

</code_context>

<specifics>
## Specific Ideas

- The default variant of a study type owns the short alias (e.g. "ct ap"), while explicit variants use longer aliases (e.g. "ct ap structured"). This means the LLM's default behavior (classifying based on draft content without variant-specific keywords) naturally routes to the default template
- The full end-to-end flow: dictate -> ggwave -> stage 1 (LLM classifies using registry.get_known_aliases()) -> stage 2 (registry.get_template(alias)) -> stage 3 (LLM extracts findings) -> stage 4 (render) -> ggwave back
- Most users will dictate free-form text without structure; the system must handle that as the primary path, not as a fallback

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-template-loader-registry*
*Context gathered: 2026-03-28*
