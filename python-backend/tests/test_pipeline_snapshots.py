"""Snapshot golden-file tests for pipeline rendering (D-25, D-26).

Golden files in tests/snapshots/ are manually authored. Tests fail
if rendered output doesn't match. Whitespace is normalised before
comparison (stripped, Unix line endings) per Pitfall 5 in RESEARCH.md.
"""

import json
import pathlib

import pytest

SNAPSHOTS_DIR = pathlib.Path(__file__).parent / "snapshots"


def _normalize(text: str) -> str:
    """Normalize whitespace for snapshot comparison."""
    return text.strip().replace("\r\n", "\n")


def _render_via_pipeline(
    llm_pipeline, study_type: str, findings: dict,
    technique: dict | None = None,
) -> str:
    """Helper: render through pipeline and return ct."""
    payload: dict = {"study_type": study_type, "findings": findings}
    if technique:
        payload["technique"] = technique
    ct = json.dumps(payload)
    result = llm_pipeline.process({"id": "snap", "fn": "render", "ct": ct})
    assert result["st"] == "S", f"Render failed: {result['ct']}"
    return result["ct"]


def _load_golden(name: str) -> str:
    """Load and normalize a golden snapshot file."""
    path = SNAPSHOTS_DIR / name
    return _normalize(path.read_text(encoding="utf-8"))


# ===== Snapshot Tests =====


def test_snapshot_us_hbs(llm_pipeline):
    findings = {
        "liver": "Normal in size and echotexture. No focal lesion.",
        "gallbladder_cbd": "Gallbladder is well distended with no calculi. CBD measures 4mm.",
        "spleen": "Normal in size.",
        "pancreas": "Visualised portions are unremarkable.",
    }
    technique = {"cbd_diameter_mm": "4"}
    rendered = _render_via_pipeline(llm_pipeline, "us hbs", findings, technique)
    assert _normalize(rendered) == _load_golden("us_hbs_render.txt")


def test_snapshot_ct_ap_freeform(llm_pipeline):
    findings = {
        "liver": "Normal in size and attenuation. No focal lesion.",
        "spleen": "Unremarkable.",
        "adrenals": "Unremarkable.",
        "pancreas": "Unremarkable.",
        "kidneys": "No hydronephrosis or calculi.",
    }
    rendered = _render_via_pipeline(llm_pipeline, "ct ap", findings)
    assert _normalize(rendered) == _load_golden("ct_ap_freeform_render.txt")


def test_snapshot_ct_ap_structured(llm_pipeline):
    findings = {
        "liver": "Normal in size and attenuation. No focal lesion.",
        "spleen": "Unremarkable.",
        "adrenals": "Unremarkable.",
        "pancreas": "Unremarkable.",
        "kidneys": "No hydronephrosis or calculi.",
    }
    rendered = _render_via_pipeline(llm_pipeline, "ct ap structured", findings)
    assert _normalize(rendered) == _load_golden("ct_ap_structured_render.txt")


def test_snapshot_ct_tap(llm_pipeline):
    findings = {
        "lungs": "Clear. No focal consolidation.",
        "pleura": "No effusion.",
        "liver": "Normal in size and attenuation.",
        "spleen": "Unremarkable.",
        "adrenals": "Unremarkable.",
        "pancreas": "Unremarkable.",
    }
    rendered = _render_via_pipeline(llm_pipeline, "ct tap", findings)
    assert _normalize(rendered) == _load_golden("ct_tap_render.txt")
