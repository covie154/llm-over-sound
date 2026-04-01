"""TDD RED tests for Task 1: LLMPipeline fn-based routing and registry ownership."""

import json
import pytest


@pytest.fixture
def pipeline():
    """LLMPipeline instance with production templates."""
    from lib.pipeline import LLMPipeline
    return LLMPipeline()


def test_render_fn_valid_returns_success(pipeline):
    """fn='render' with valid study_type and findings returns st='S' with rendered report text."""
    payload = json.dumps({"study_type": "us hbs", "findings": {"liver": "Normal in size and echotexture."}})
    result = pipeline.process({"id": "test001", "fn": "render", "ct": payload})
    assert result["st"] == "S"
    assert result["id"] == "test001"
    assert len(result["ct"]) > 0


def test_render_fn_unknown_study_type(pipeline):
    """fn='render' with unknown study_type returns st='E' with 'Unknown study type'."""
    payload = json.dumps({"study_type": "nonexistent", "findings": {"a": "b"}})
    result = pipeline.process({"id": "test002", "fn": "render", "ct": payload})
    assert result["st"] == "E"
    assert result["ct"] == "Unknown study type"


def test_render_fn_invalid_json(pipeline):
    """fn='render' with invalid JSON in ct returns st='E', ct starts with 'Invalid render payload'."""
    result = pipeline.process({"id": "test003", "fn": "render", "ct": "not json"})
    assert result["st"] == "E"
    assert result["ct"].startswith("Invalid render payload")


def test_render_fn_missing_study_type(pipeline):
    """fn='render' with missing study_type returns st='E'."""
    payload = json.dumps({"findings": {"liver": "Normal"}})
    result = pipeline.process({"id": "test004", "fn": "render", "ct": payload})
    assert result["st"] == "E"
    assert "Missing required fields: study_type, findings" in result["ct"]


def test_render_fn_missing_findings(pipeline):
    """fn='render' with missing findings returns st='E'."""
    payload = json.dumps({"study_type": "us hbs"})
    result = pipeline.process({"id": "test005", "fn": "render", "ct": payload})
    assert result["st"] == "E"
    assert "Missing required fields: study_type, findings" in result["ct"]


def test_report_fn_stub_error(pipeline):
    """fn='report' returns st='E', ct contains 'requires LLM connection'."""
    result = pipeline.process({"id": "test010", "fn": "report", "ct": "some draft"})
    assert result["st"] == "E"
    assert "requires LLM connection" in result["ct"]


def test_unknown_fn(pipeline):
    """Unknown fn value returns st='E', ct starts with 'Unknown function'."""
    result = pipeline.process({"id": "test020", "fn": "unknown", "ct": ""})
    assert result["st"] == "E"
    assert result["ct"].startswith("Unknown function")


def test_invalid_msg_dict(pipeline):
    """Invalid msg_dict (not a dict) returns st='E'."""
    result = pipeline.process("not a dict")
    assert result["st"] == "E"
    assert result["ct"] == "Invalid message format"


def test_sex_inference_male(pipeline):
    """findings containing 'prostate' key infers male."""
    assert pipeline._infer_sex({"prostate": "Normal"}) == "male"


def test_sex_inference_female(pipeline):
    """findings containing 'uterus' key infers female."""
    assert pipeline._infer_sex({"uterus": "Normal"}) == "female"


def test_sex_inference_none(pipeline):
    """findings without sex markers returns None."""
    assert pipeline._infer_sex({"liver": "Normal"}) is None
