"""Comprehensive tests for TemplateRegistry — alias indexing, lookup, and error handling.

Covers: MTCH-01 (alias indexing), MTCH-02 (recursive scan), MTCH-03 (exact match
and unknown alias), D-02 (error collection), D-04 (empty/missing dir), D-05 (sorted
aliases), D-08 (case insensitive), D-10 (return type), D-11 (reload), D-12 (duplicate
detection), D-20 (TemplateNotFoundError), FWRK-01 (standalone import).
"""

import pathlib
import shutil
import sys

import pytest

from lib.templates.registry import TemplateRegistry
from lib.templates.exceptions import TemplateNotFoundError, TemplateValidationError
from lib.templates.schema import TemplateSchema


# -- Index building ----------------------------------------------------------

def test_registry_builds_index(registry):
    """TemplateRegistry loads all fixtures and indexes 8 aliases."""
    aliases = registry.get_known_aliases()
    assert len(aliases) == 8


def test_aliases_indexed(registry):
    """MTCH-01: Every alias from all 3 fixture templates is present."""
    aliases = set(registry.get_known_aliases())
    expected = {
        "ct ap", "ct abdomen", "ct abdomen pelvis",
        "ct thorax", "ct chest",
        "us hbs", "us hepatobiliary", "ultrasound liver",
    }
    assert aliases == expected


# -- Recursive scan ----------------------------------------------------------

def test_recursive_scan(registry):
    """MTCH-02: Registry discovers templates in ct/ and us/ subdirs."""
    # If recursive scan failed, we wouldn't have all 8 aliases from 3 files
    # in separate subdirectories (ct/, us/).
    aliases = registry.get_known_aliases()
    # ct/ subdir aliases
    assert "ct ap" in aliases
    assert "ct thorax" in aliases
    # us/ subdir aliases
    assert "us hbs" in aliases


# -- Exact match -------------------------------------------------------------

def test_exact_match(registry):
    """MTCH-03: get_template('ct ap') returns the CT Abdomen and Pelvis template."""
    template = registry.get_template("ct ap")
    assert template.schema.study_name == "CT Abdomen and Pelvis"


# -- Case insensitive --------------------------------------------------------

def test_case_insensitive(registry):
    """D-08: Alias lookup is case-insensitive."""
    t_lower = registry.get_template("ct ap")
    t_upper = registry.get_template("CT AP")
    t_mixed = registry.get_template("Ct Ap")
    assert t_lower is t_upper
    assert t_lower is t_mixed


# -- Unknown alias -----------------------------------------------------------

def test_unknown_alias(registry):
    """MTCH-03: get_template for non-existent alias raises TemplateNotFoundError."""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        registry.get_template("nonexistent")
    assert exc_info.value.alias == "nonexistent"
    assert isinstance(exc_info.value.known_aliases, list)
    assert len(exc_info.value.known_aliases) == 8


# -- Sorted aliases ----------------------------------------------------------

def test_known_aliases_sorted(registry):
    """D-05: get_known_aliases returns alphabetically sorted list."""
    aliases = registry.get_known_aliases()
    assert aliases == sorted(aliases)


# -- Empty directory ---------------------------------------------------------

def test_empty_dir_fatal(tmp_path):
    """D-04: Registry with no *.rpt.md files raises TemplateValidationError."""
    with pytest.raises(TemplateValidationError):
        TemplateRegistry(tmp_path)


# -- Nonexistent directory ---------------------------------------------------

def test_nonexistent_dir_fatal(tmp_path):
    """D-04: Registry with nonexistent path raises TemplateValidationError."""
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(TemplateValidationError):
        TemplateRegistry(nonexistent)


# -- Duplicate alias detection -----------------------------------------------

def test_duplicate_alias_fatal(tmp_path, registry_fixtures_dir, invalid_fixtures_dir):
    """D-12: Duplicate alias 'ct ap' across two templates is a fatal error."""
    # Copy ct_abdomen (has "ct ap") and duplicate_alias (also has "ct ap")
    sub = tmp_path / "templates"
    sub.mkdir()
    shutil.copy(registry_fixtures_dir / "ct" / "ct_abdomen.rpt.md", sub / "ct_abdomen.rpt.md")
    shutil.copy(invalid_fixtures_dir / "duplicate_alias.rpt.md", sub / "duplicate_alias.rpt.md")

    with pytest.raises(TemplateValidationError) as exc_info:
        TemplateRegistry(sub)
    error_msg = str(exc_info.value)
    assert "ct ap" in error_msg


# -- Error collection --------------------------------------------------------

def test_collect_all_errors(tmp_path, invalid_fixtures_dir, registry_fixtures_dir):
    """D-02: Multiple validation errors are collected before raising."""
    sub = tmp_path / "templates"
    sub.mkdir()
    # bad_frontmatter will fail to parse, duplicate_alias + ct_abdomen will collide
    shutil.copy(invalid_fixtures_dir / "bad_frontmatter.rpt.md", sub / "bad_frontmatter.rpt.md")
    shutil.copy(invalid_fixtures_dir / "duplicate_alias.rpt.md", sub / "duplicate_alias.rpt.md")
    shutil.copy(registry_fixtures_dir / "ct" / "ct_abdomen.rpt.md", sub / "ct_abdomen.rpt.md")

    with pytest.raises(TemplateValidationError) as exc_info:
        TemplateRegistry(sub)
    assert len(exc_info.value.errors) > 1


# -- Reload ------------------------------------------------------------------

def test_reload(registry):
    """D-11: reload() re-scans and rebuilds the index successfully."""
    original_count = len(registry.get_known_aliases())
    registry.reload()
    assert len(registry.get_known_aliases()) == original_count


# -- Return type -------------------------------------------------------------

def test_get_template_returns_loaded_template(registry):
    """D-10: Returned object has .schema (TemplateSchema), .body (str), .file_path (str)."""
    template = registry.get_template("ct ap")
    assert isinstance(template.schema, TemplateSchema)
    assert isinstance(template.body, str)
    assert isinstance(template.file_path, str)
    assert "{{liver}}" in template.body


# -- Standalone import -------------------------------------------------------

# -- Production composite aliases ---------------------------------------------

TEMPLATES_ROOT = pathlib.Path(__file__).parent.parent / "rpt_templates"


def test_registry_includes_composite_aliases():
    """Registry built from production templates includes ct tap alias."""
    registry = TemplateRegistry(TEMPLATES_ROOT)
    aliases = registry.get_known_aliases()
    assert "ct tap" in aliases
    assert "ct thorax abdomen pelvis" in aliases


# -- Standalone import -------------------------------------------------------

def test_standalone_import():
    """FWRK-01: Template sub-package source has no ggwave/pyaudio imports.

    Per Phase 02 decision: check source code for audio imports rather than
    sys.modules, since other test modules may load ggwave as a side effect.
    """
    import inspect
    from lib.templates import registry as reg_mod
    from lib.templates import loader as loader_mod
    from lib.templates import schema as schema_mod
    from lib.templates import exceptions as exc_mod

    for mod in (reg_mod, loader_mod, schema_mod, exc_mod):
        source = inspect.getsource(mod)
        assert "import ggwave" not in source, f"{mod.__name__} imports ggwave"
        assert "import pyaudio" not in source, f"{mod.__name__} imports pyaudio"
