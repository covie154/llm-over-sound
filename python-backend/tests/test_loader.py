"""Tests for template file discovery and parsing (lib.templates.loader).

Covers: valid parsing, invalid template rejection, recursive discovery,
nonexistent/empty directories, placeholder cross-validation fatality,
frozen dataclass enforcement, and standalone import isolation.
"""

import pathlib
import sys

import pytest

from lib.templates.loader import LoadedTemplate, load_template, discover_templates
from lib.templates.exceptions import TemplateValidationError


class TestLoadValidTemplate:
    """Tests for successfully loading a valid template."""

    def test_load_valid_template(self, registry_fixtures_dir):
        """load_template() on ct_abdomen returns LoadedTemplate with correct fields."""
        path = registry_fixtures_dir / "ct" / "ct_abdomen.rpt.md"
        result = load_template(path)

        assert isinstance(result, LoadedTemplate)
        assert result.schema.study_name == "CT Abdomen and Pelvis"
        assert "{{liver}}" in result.body
        assert result.file_path.endswith("ct_abdomen.rpt.md")

    def test_load_valid_template_aliases(self, registry_fixtures_dir):
        """Loaded template preserves all aliases from frontmatter."""
        path = registry_fixtures_dir / "ct" / "ct_abdomen.rpt.md"
        result = load_template(path)

        assert "ct ap" in result.schema.aliases
        assert "ct abdomen" in result.schema.aliases
        assert "ct abdomen pelvis" in result.schema.aliases

    def test_load_valid_template_groups(self, registry_fixtures_dir):
        """Loaded template preserves group definitions."""
        path = registry_fixtures_dir / "ct" / "ct_abdomen.rpt.md"
        result = load_template(path)

        assert len(result.schema.groups) == 1
        assert result.schema.groups[0].name == "upper_abdo"


class TestLoadInvalidTemplate:
    """Tests for rejecting invalid templates."""

    def test_load_invalid_template(self, invalid_fixtures_dir):
        """load_template() on bad_frontmatter raises TemplateValidationError."""
        path = invalid_fixtures_dir / "bad_frontmatter.rpt.md"
        with pytest.raises(TemplateValidationError) as exc_info:
            load_template(path)

        assert len(exc_info.value.errors) >= 1


class TestDiscoverTemplates:
    """Tests for recursive template discovery."""

    def test_discover_templates_recursive(self, registry_fixtures_dir):
        """discover_templates() finds all 3 valid templates recursively."""
        paths = discover_templates(registry_fixtures_dir)

        assert len(paths) == 3
        assert all(str(p).endswith(".rpt.md") for p in paths)

        # Check all expected templates are found
        names = [p.name for p in paths]
        assert "ct_abdomen.rpt.md" in names
        assert "ct_thorax.rpt.md" in names
        assert "us_hbs.rpt.md" in names

    def test_discover_nonexistent_dir(self):
        """discover_templates() on nonexistent path raises TemplateValidationError."""
        fake_path = pathlib.Path("/nonexistent/templates/dir")
        with pytest.raises(TemplateValidationError):
            discover_templates(fake_path)

    def test_discover_empty_dir(self, tmp_path):
        """discover_templates() on empty dir returns empty list."""
        result = discover_templates(tmp_path)
        assert result == []


class TestPlaceholderValidation:
    """Tests for body placeholder cross-validation."""

    def test_placeholder_mismatch_fatal(self, tmp_path):
        """load_template() raises on placeholder not matching fields (per D-03)."""
        template_content = """---
study_name: "Mismatch Test"
aliases:
  - "mismatch"
technique: "Test technique."
fields:
  - name: "liver"
    normal: "Normal liver."
---

## FINDINGS

{{liver}}

{{kidneys}}
"""
        path = tmp_path / "mismatch.rpt.md"
        path.write_text(template_content)

        with pytest.raises(TemplateValidationError) as exc_info:
            load_template(path)

        # Should report the kidneys placeholder issue
        error_text = str(exc_info.value)
        assert "kidneys" in error_text


class TestLoadedTemplateDataclass:
    """Tests for the LoadedTemplate frozen dataclass."""

    def test_loaded_template_frozen(self, registry_fixtures_dir):
        """LoadedTemplate is frozen -- attribute assignment raises."""
        path = registry_fixtures_dir / "ct" / "ct_abdomen.rpt.md"
        result = load_template(path)

        with pytest.raises((AttributeError, TypeError)):
            result.body = "modified"


class TestStandaloneImport:
    """Tests for import isolation (FWRK-01)."""

    def test_standalone_import(self):
        """lib.templates module tree does not import ggwave, pyaudio, or audio.

        Verifies by inspecting the source code of lib/templates/ modules
        to confirm no audio-related imports exist. In a shared test session,
        sys.modules contains audio modules loaded by other test files that
        import the top-level lib package, so we check the module source instead.
        """
        import importlib
        import inspect

        # Check all modules in lib.templates for audio imports
        modules_to_check = [
            "lib.templates",
            "lib.templates.schema",
            "lib.templates.loader",
            "lib.templates.exceptions",
        ]
        audio_keywords = ("ggwave", "pyaudio", "lib.audio", ".audio")

        for mod_name in modules_to_check:
            mod = importlib.import_module(mod_name)
            source = inspect.getsource(mod)
            for keyword in audio_keywords:
                assert f"import {keyword}" not in source and f"from {keyword}" not in source, (
                    f"Module {mod_name} contains audio import: {keyword}"
                )
