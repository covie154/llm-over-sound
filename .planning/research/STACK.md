# Technology Stack

**Project:** LLM Report Templates -- Radiology Report Formatting System
**Researched:** 2026-03-28

## Recommended Stack

### YAML Frontmatter Parsing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| python-frontmatter | 1.1.0 | Parse YAML frontmatter from markdown template files | Purpose-built for exactly this use case. Handles the `---` delimited YAML block and returns both metadata (as dict) and body (as string) in one call. Uses PyYAML under the hood. Stable -- v1.1.0 released Jan 2024, no breaking changes expected. |

**Usage pattern:**
```python
import frontmatter

post = frontmatter.load("rpt_templates/ct/ct_abdomen_pelvis.md")
metadata = post.metadata  # dict: study_name, aliases, fields, flags
body = post.content        # str: the markdown template skeleton
```

**Why not alternatives:**
- **Raw PyYAML + manual splitting**: Reinvents what python-frontmatter already does. You would need to handle the `---` delimiter parsing, edge cases with multiple `---` in content, and encoding. No benefit.
- **ruamel.yaml**: Overkill. Its key advantage is roundtrip comment preservation when _writing_ YAML back to files. We only _read_ template frontmatter; we never modify and re-save it programmatically. ruamel.yaml adds complexity and a steeper learning curve for zero benefit here.
- **frontmatter** (the other PyPI package, v3.0.8): Confusingly similar name but different package. Less maintained, fewer features. Use `python-frontmatter` (import as `frontmatter`).

### YAML Parsing (underlying)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyYAML | 6.0.2+ | YAML parsing engine (dependency of python-frontmatter) | Installed automatically with python-frontmatter. YAML 1.1 support is sufficient -- our frontmatter uses simple key-value pairs, lists, and nested dicts. No YAML 1.2 features needed. |

### Data Validation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Pydantic | 2.10+ | Validate template frontmatter schema AND LLM-extracted findings JSON | Pydantic v2 is 5-50x faster than v1, generates JSON Schema automatically from Python type hints, and provides clear error messages. Critical for two validation points: (1) template frontmatter structure at load time, (2) LLM output conformance at extraction time. |

**Why Pydantic over jsonschema:**
- **LLM integration**: Pydantic models can be passed directly to LLM structured output APIs (OpenAI, Anthropic, LiteLLM all support Pydantic models for constrained output). Major advantage for Stage 3 (findings extraction).
- **Python-native**: Define schemas as Python classes with type hints. No separate JSON Schema files to maintain.
- **Automatic JSON Schema generation**: `model.model_json_schema()` generates it from the Pydantic model.
- **Validation + parsing in one step**: Pydantic coerces and validates simultaneously. jsonschema only validates.
- **Error messages**: Structured and actionable. Critical for debugging template load failures or malformed LLM output.

**Pydantic model sketch for template frontmatter:**
```python
from pydantic import BaseModel

class FieldDefinition(BaseModel):
    name: str
    default_normal: str | None = None
    required: bool = False
    sex_specific: str | None = None  # "M", "F", or None

class TemplateMetadata(BaseModel):
    study_name: str
    aliases: list[str]
    modality: str
    body_region: str
    fields: list[FieldDefinition]
    impression: bool = True
    interpolate_normal: bool = False
    composable_from: list[str] | None = None  # paths to base templates
```

### Template Rendering (Report Body)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| str.replace() / str.format_map() | stdlib | Populate template placeholders with extracted findings | Simple string interpolation -- no loops, no conditionals, no filters. Using a full template engine is unnecessary overhead. |

**Why NOT Jinja2:**
- Templates are markdown files with placeholder tokens. The rendering step is a `dict` -> `str.format_map()` call or a simple loop of `str.replace()`.
- Jinja2 adds: a dependency, syntax conflicts with markdown, template compilation overhead, and a learning curve for radiologists editing templates.
- If future requirements add conditional sections, handle that in Python code _before_ rendering, not in template syntax. Keep templates dumb.

### Markdown Processing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| None (raw string) | -- | Templates are markdown but we do not parse or render markdown to HTML | The output is plain text going over ggwave. We store templates as markdown for human readability and editability, but we never convert to HTML. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Frontmatter parsing | python-frontmatter | Manual PyYAML + string split | Reinvents the wheel; edge cases with delimiter detection |
| YAML engine | PyYAML (via python-frontmatter) | ruamel.yaml | Roundtrip preservation not needed; added complexity |
| Validation | Pydantic v2 | jsonschema | No LLM integration, separate schema files, validation-only |
| Validation | Pydantic v2 | marshmallow | Slower, less Python-native, no JSON Schema generation |
| Template rendering | str.replace / format_map | Jinja2 | Overkill for placeholder substitution; syntax conflicts |
| Markdown | None (raw string) | mistune / markdown | No HTML target; reports are plain text over ggwave |

## What NOT to Use

1. **ruamel.yaml**: Solves a problem we do not have (roundtrip YAML editing).
2. **Jinja2 for template rendering**: No control flow in templates. If you want `{% if %}`, move logic to Python.
3. **jsonschema as standalone validator**: Maintain Pydantic models as single source of truth. Generate JSON Schema from Pydantic if needed.
4. **Any markdown-to-HTML library**: Output is plain text over ggwave. No browser context.
5. **TOML or JSON frontmatter**: YAML is the standard for frontmatter and most readable for template authors.

## Installation

```bash
pip install python-frontmatter pydantic
```

**Versions to pin in requirements.txt:**
```
python-frontmatter>=1.1.0,<2.0
pydantic>=2.10,<3.0
```

**Python version requirement:** 3.10+ (required by Pydantic v2). Raspberry Pi OS Bookworm ships Python 3.11.

## Dependency Footprint

Total new dependencies: **2 direct** (python-frontmatter, pydantic). Deliberately minimal for Raspberry Pi deployment.

## Composable Template Pattern

For combined studies (e.g., CT TAP = CT Thorax + CT Abdomen/Pelvis):

```yaml
---
study_name: "CT Thorax, Abdomen and Pelvis"
aliases: ["CT TAP", "CT chest abdomen pelvis"]
composable_from:
  - "ct/ct_thorax.md"
  - "ct/ct_abdomen_pelvis.md"
impression: true
interpolate_normal: false
---
```

The combined template has no body of its own. At load time, the loader:
1. Loads and validates the combined template's frontmatter.
2. Loads each base template referenced in `composable_from`.
3. Concatenates the fields lists (thorax fields, then abdomen/pelvis fields).
4. Concatenates the body sections with a section separator.
5. Returns a single merged `TemplateMetadata` + body string.

## Confidence Assessment

| Decision | Confidence | Basis |
|----------|------------|-------|
| python-frontmatter for parsing | HIGH | PyPI data, active docs, exactly fits use case |
| PyYAML as underlying engine | HIGH | De facto standard, auto-installed, sufficient for our YAML subset |
| Pydantic v2 for validation | HIGH | Official docs, LLM ecosystem integration, performance benchmarks |
| str.replace for rendering | HIGH | Stdlib, matches template simplicity, no external dependency |
| No markdown library | HIGH | Architecture constraint -- output is plain text over ggwave |
| No Jinja2 | MEDIUM | Could revisit if templates ever need conditional logic |

## Sources

- [python-frontmatter on PyPI](https://pypi.org/project/python-frontmatter/)
- [python-frontmatter GitHub](https://github.com/eyeseast/python-frontmatter)
- [Pydantic JSON Schema docs](https://docs.pydantic.dev/latest/concepts/json_schema/)
- [jsonschema on PyPI](https://pypi.org/project/jsonschema/)
