"""
Report formatting pipeline.

This module will contain the five-stage LLM pipeline described in CLAUDE.md:
  1. Study type classification (LLM)
  2. Template retrieval (deterministic)
  3. Findings extraction and mapping (LLM)
  4. Report rendering (LLM)
  5. Impression generation (LLM)

For now, only a test/echo implementation is provided.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("ggwave_backend")


# ---------------------------------------------------------------------------
# Abstract base — implement this for different LLM backends
# ---------------------------------------------------------------------------

class ReportPipeline(ABC):
    """Base class for report formatting pipelines."""

    @abstractmethod
    def process(self, msg_dict: dict) -> dict:
        """Run the full pipeline on a decoded message from the frontend.

        Args:
            msg_dict: Reassembled message dict.  Expected keys:
                id  – unique message ID (str, len 7)
                fn  – function name (str)
                ct  – draft content (str)

        Returns:
            Response dict with keys:
                id – same message ID
                st – status: "S" for success, "E" for error
                ct – response content (str)
        """
        ...


# ---------------------------------------------------------------------------
# Test / echo implementation (current behaviour)
# ---------------------------------------------------------------------------

class TestPipeline(ReportPipeline):
    """Simple echo pipeline used during development and hardware testing."""

    def process(self, msg_dict: dict) -> dict:
        if not isinstance(msg_dict, dict):
            return {"id": "", "st": "E", "ct": "Invalid message format"}

        return {
            "id": msg_dict.get("id", ""),
            "st": "S",
            "ct": f"Processed function {msg_dict.get('fn', '')} with content: {msg_dict.get('ct', '')}",
        }


# ---------------------------------------------------------------------------
# LLM implementation stub — fill in when ready
# ---------------------------------------------------------------------------

class LLMPipeline(ReportPipeline):
    """LLM-powered radiology report formatting pipeline.

    Stages:
        1. classify_study_type()
        2. retrieve_template()
        3. extract_findings()
        4. render_report()
        5. generate_impression()
    """

    def __init__(self, templates_dir: str | None = None):
        self.templates_dir = templates_dir
        # TODO: Build template alias index at startup
        # TODO: Initialise LLM client

    def process(self, msg_dict: dict) -> dict:
        if not isinstance(msg_dict, dict):
            return {"id": "", "st": "E", "ct": "Invalid message format"}

        msg_id = msg_dict.get("id", "")
        draft = msg_dict.get("ct", "")

        try:
            study_type = self.classify_study_type(draft)
            template = self.retrieve_template(study_type)
            findings = self.extract_findings(draft, template)
            report = self.render_report(template, findings)
            impression = self.generate_impression(report)

            # Combine rendered report with impression
            final = f"{report}\n\nIMPRESSION:\n{impression}"
            return {"id": msg_id, "st": "S", "ct": final}
        except Exception as e:
            logger.error(f"[LLM_PIPELINE] ID: {msg_id} | Error: {e}")
            return {"id": msg_id, "st": "E", "ct": str(e)}

    # -- Stage implementations (stubs) ------------------------------------

    def classify_study_type(self, draft: str) -> str:
        """Stage 1: Identify imaging modality and body region from draft."""
        raise NotImplementedError("classify_study_type not yet implemented")

    def retrieve_template(self, study_type: str) -> dict:
        """Stage 2: Load and parse the matching markdown template."""
        raise NotImplementedError("retrieve_template not yet implemented")

    def extract_findings(self, draft: str, template: dict) -> dict:
        """Stage 3: Extract findings from draft and map to template fields."""
        raise NotImplementedError("extract_findings not yet implemented")

    def render_report(self, template: dict, findings: dict) -> str:
        """Stage 4: Populate the template skeleton with extracted findings."""
        raise NotImplementedError("render_report not yet implemented")

    def generate_impression(self, report: str) -> str:
        """Stage 5: Generate the impression / conclusion."""
        raise NotImplementedError("generate_impression not yet implemented")
