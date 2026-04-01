"""Shared test fixtures for template system tests."""

import pathlib

import pytest
import frontmatter

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_template_path() -> pathlib.Path:
    """Path to the minimal sample template fixture."""
    return FIXTURES_DIR / "sample_template.md"


@pytest.fixture
def sample_template_post(sample_template_path):
    """Parsed frontmatter Post object from the sample template."""
    return frontmatter.load(str(sample_template_path))


@pytest.fixture
def sample_template_metadata(sample_template_post):
    """Raw metadata dict from the sample template."""
    return sample_template_post.metadata


@pytest.fixture
def sample_template_body(sample_template_post):
    """Markdown body string from the sample template."""
    return sample_template_post.content


@pytest.fixture
def registry_fixtures_dir() -> pathlib.Path:
    """Path to the multi-template registry test fixtures directory."""
    return FIXTURES_DIR / "registry_fixtures"


@pytest.fixture
def invalid_fixtures_dir() -> pathlib.Path:
    """Path to the invalid template fixtures directory."""
    return FIXTURES_DIR / "invalid"


@pytest.fixture
def registry(registry_fixtures_dir):
    """A fully loaded registry from the test fixtures."""
    from lib.templates.registry import TemplateRegistry
    return TemplateRegistry(registry_fixtures_dir)


@pytest.fixture
def renderer_fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR / "renderer"


@pytest.fixture
def freeform_template(renderer_fixtures_dir):
    from lib.templates.loader import load_template
    return load_template(renderer_fixtures_dir / "freeform_minimal.rpt.md")


@pytest.fixture
def structured_template(renderer_fixtures_dir):
    from lib.templates.loader import load_template
    return load_template(renderer_fixtures_dir / "structured_minimal.rpt.md")


@pytest.fixture
def groups_template(renderer_fixtures_dir):
    from lib.templates.loader import load_template
    return load_template(renderer_fixtures_dir / "groups_minimal.rpt.md")


@pytest.fixture
def measurements_template(renderer_fixtures_dir):
    from lib.templates.loader import load_template
    return load_template(renderer_fixtures_dir / "measurements_minimal.rpt.md")


@pytest.fixture
def composite_fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR / "composite"


@pytest.fixture
def composite_bases(composite_fixtures_dir):
    """Load base templates for composition testing."""
    from lib.templates.loader import load_template
    base_a = load_template(composite_fixtures_dir / "base_a.rpt.md")
    base_b = load_template(composite_fixtures_dir / "base_b.rpt.md")
    return {
        "composite/base_a.rpt.md": base_a,
        "composite/base_b.rpt.md": base_b,
    }


@pytest.fixture
def raw_composite(composite_fixtures_dir):
    """Load the composite template (raw, pre-composition)."""
    from lib.templates.loader import load_template
    return load_template(composite_fixtures_dir / "composite_ab.rpt.md")


@pytest.fixture
def production_templates_dir() -> pathlib.Path:
    """Path to the production templates directory."""
    return pathlib.Path(__file__).parent.parent / "rpt_templates"


@pytest.fixture
def llm_pipeline(production_templates_dir):
    """An LLMPipeline instance using production templates."""
    from lib.pipeline import LLMPipeline
    return LLMPipeline(str(production_templates_dir))
