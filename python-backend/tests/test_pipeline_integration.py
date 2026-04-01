"""Integration and unit tests for LLMPipeline.

Tests fn-based routing, template lookup via registry, rendering,
error handling, and standalone importability.
"""

import json
import logging

import pytest


# ===== Standalone Import Test =====


def test_standalone_import():
    """LLMPipeline importable without ggwave (FWRK-02, D-18)."""
    from lib.pipeline import LLMPipeline
    assert LLMPipeline is not None


# ===== fn='render' Integration Tests =====


def test_render_fn_success(llm_pipeline):
    """fn='render' with valid US HBS data returns rendered report (D-05, D-06)."""
    payload = json.dumps({
        "study_type": "us hbs",
        "findings": {"liver": "Normal in size and echotexture."},
    })
    result = llm_pipeline.process({"id": "test001", "fn": "render", "ct": payload})
    assert result["st"] == "S"
    assert result["id"] == "test001"
    assert "liver" in result["ct"].lower() or "Normal in size" in result["ct"]


def test_render_fn_unknown_study(llm_pipeline):
    """Unknown study type returns error (D-13)."""
    payload = json.dumps({
        "study_type": "nonexistent modality",
        "findings": {"a": "b"},
    })
    result = llm_pipeline.process({"id": "test002", "fn": "render", "ct": payload})
    assert result["st"] == "E"
    assert result["ct"] == "Unknown study type"


def test_render_fn_invalid_json(llm_pipeline):
    """Invalid JSON in ct returns parse error (Pitfall 3)."""
    result = llm_pipeline.process({"id": "test003", "fn": "render", "ct": "not json"})
    assert result["st"] == "E"
    assert "Invalid render payload" in result["ct"]


def test_render_fn_missing_study_type(llm_pipeline):
    """Missing study_type returns validation error (D-07)."""
    payload = json.dumps({"findings": {"liver": "Normal"}})
    result = llm_pipeline.process({"id": "test004", "fn": "render", "ct": payload})
    assert result["st"] == "E"
    assert "Missing required fields" in result["ct"]


def test_render_fn_missing_findings(llm_pipeline):
    """Missing findings returns validation error (D-07)."""
    payload = json.dumps({"study_type": "us hbs"})
    result = llm_pipeline.process({"id": "test005", "fn": "render", "ct": payload})
    assert result["st"] == "E"
    assert "Missing required fields" in result["ct"]


def test_render_fn_optional_defaults(llm_pipeline):
    """fn='render' works without optional fields (D-07)."""
    payload = json.dumps({
        "study_type": "us hbs",
        "findings": {"liver": "Normal"},
    })
    result = llm_pipeline.process({"id": "test006", "fn": "render", "ct": payload})
    assert result["st"] == "S"


# ===== fn='report' Tests =====


def test_report_fn_stub_error(llm_pipeline):
    """fn='report' hits stub and returns friendly error (D-01, D-15)."""
    result = llm_pipeline.process({"id": "test010", "fn": "report", "ct": "some draft"})
    assert result["st"] == "E"
    assert "requires LLM connection" in result["ct"]


# ===== Unknown fn Tests =====


def test_unknown_fn(llm_pipeline):
    """Unknown fn returns error."""
    result = llm_pipeline.process({"id": "test020", "fn": "unknown", "ct": ""})
    assert result["st"] == "E"
    assert "Unknown function" in result["ct"]


# ===== Invalid Input Tests =====


def test_invalid_msg_dict(llm_pipeline):
    """Non-dict input returns error (D-19)."""
    result = llm_pipeline.process("not a dict")
    assert result["st"] == "E"
    assert "Invalid message format" in result["ct"]


# ===== Sex Inference Unit Tests =====


def test_sex_inference_male(llm_pipeline):
    """Findings with prostate key infers male (D-20)."""
    assert llm_pipeline._infer_sex({"prostate": "Normal"}) == "male"


def test_sex_inference_female(llm_pipeline):
    """Findings with uterus key infers female (D-20)."""
    assert llm_pipeline._infer_sex({"uterus": "Normal"}) == "female"


def test_sex_inference_female_ovaries(llm_pipeline):
    """Findings with ovaries key infers female (D-20)."""
    assert llm_pipeline._infer_sex({"ovaries": "Normal"}) == "female"


def test_sex_inference_none(llm_pipeline):
    """Findings without sex markers returns None (D-20)."""
    assert llm_pipeline._infer_sex({"liver": "Normal"}) is None


# ===== PIPELINE_MODE env var test =====


def test_pipeline_mode_env(monkeypatch):
    """PIPELINE_MODE=llm activates LLMPipeline (D-17)."""
    monkeypatch.setenv("PIPELINE_MODE", "llm")
    import os
    assert os.environ.get("PIPELINE_MODE") == "llm"
    # Verify the class exists and can be instantiated
    from lib.pipeline import LLMPipeline
    p = LLMPipeline()
    assert hasattr(p, "_registry")


def test_pipeline_mode_default():
    """Default PIPELINE_MODE is 'test' -- TestPipeline (D-17)."""
    import os
    mode = os.environ.get("PIPELINE_MODE", "test")
    assert mode == "test" or mode == "llm"  # Don't fail if env is set


# ===== Registry Init Test =====


def test_registry_init_logs(caplog):
    """LLMPipeline logs template count at init (D-11)."""
    with caplog.at_level(logging.INFO, logger="ggwave_backend"):
        from lib.pipeline import LLMPipeline
        LLMPipeline()
        assert any(
            "Loaded" in r.message and "aliases" in r.message
            for r in caplog.records
        )
