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
