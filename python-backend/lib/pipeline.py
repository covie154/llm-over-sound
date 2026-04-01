"""
Report formatting pipeline.

This module contains the five-stage LLM pipeline described in CLAUDE.md:
  1. Study type classification (LLM) — stub
  2. Template retrieval (deterministic) — real, via TemplateRegistry
  3. Findings extraction and mapping (LLM) — stub
  4. Report rendering (deterministic) — real, via render_report
  5. Impression generation (LLM) — stub

fn-based routing:
  fn='render' — stages 2+4 only (template lookup + render), caller provides findings
  fn='report' — full pipeline (stages 1-5), hits stubs for LLM stages
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from abc import ABC, abstractmethod

from lib.templates.registry import TemplateRegistry
from lib.templates.renderer import render_report as template_render_report
from lib.templates.loader import LoadedTemplate
from lib.templates.exceptions import TemplateNotFoundError

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
# LLM implementation — fn-based routing with real template system
# ---------------------------------------------------------------------------

class LLMPipeline(ReportPipeline):
    """LLM-powered radiology report formatting pipeline.

    Owns a TemplateRegistry for study type lookup and template rendering.
    Routes incoming messages by fn field:
      fn='render' — deterministic template lookup + render (stages 2+4)
      fn='report' — full 5-stage pipeline (stages 1,3,5 are LLM stubs)

    Args:
        templates_dir: Path to templates directory. Falls back to
            RPT_TEMPLATES_DIR env var, then python-backend/rpt_templates/.
    """

    def __init__(self, templates_dir: str | None = None):
        resolved_dir = (
            templates_dir
            or os.environ.get("RPT_TEMPLATES_DIR")
            or str(pathlib.Path(__file__).parent.parent / "rpt_templates")
        )
        # TemplateLoadError / TemplateValidationError from registry are fatal (D-12)
        self._registry = TemplateRegistry(resolved_dir)

        # Log summary of loaded templates
        unique_templates = len(set(
            id(t) for t in self._registry._alias_index.values()
        ))
        alias_count = len(self._registry.get_known_aliases())
        logger.info(
            f"Loaded {unique_templates} templates ({alias_count} aliases) "
            f"from {resolved_dir}"
        )

    def process(self, msg_dict: dict) -> dict:
        """Route message by fn field to appropriate handler.

        Args:
            msg_dict: Decoded message dict with id, fn, ct keys.

        Returns:
            Response dict with id, st, ct keys.
        """
        if not isinstance(msg_dict, dict):
            return {"id": "", "st": "E", "ct": "Invalid message format"}

        msg_id = msg_dict.get("id", "")
        fn = msg_dict.get("fn", "")

        if fn == "render":
            return self._handle_render(msg_id, msg_dict.get("ct", ""))
        elif fn == "report":
            return self._handle_report(msg_id, msg_dict.get("ct", ""))
        else:
            return {"id": msg_id, "st": "E", "ct": f"Unknown function: {fn}"}

    # -- fn='render': deterministic template lookup + render (stages 2+4) --

    def _handle_render(self, msg_id: str, ct: str) -> dict:
        """Handle fn='render' — parse payload, lookup template, render report.

        Expects ct to be a JSON string with:
            study_type (str): Study type alias for template lookup.
            findings (dict): Field name -> finding text mapping.
            technique (dict, optional): Technique values. Defaults to {}.
            rest_normal (bool, optional): Override interpolate_normal. Defaults to False.
            important_fields (list[str], optional): Fields to prioritise.

        Args:
            msg_id: Message ID for response and audit logging.
            ct: JSON-encoded payload string.

        Returns:
            Response dict with rendered report on success, error on failure.
        """
        # Parse JSON payload
        try:
            payload = json.loads(ct)
        except (json.JSONDecodeError, TypeError) as e:
            return {"id": msg_id, "st": "E", "ct": f"Invalid render payload: {e}"}

        # Validate required fields
        study_type = payload.get("study_type")
        findings = payload.get("findings")
        if not study_type or findings is None:
            return {
                "id": msg_id,
                "st": "E",
                "ct": "Missing required fields: study_type, findings",
            }

        # Extract optional fields
        technique = payload.get("technique", {})
        rest_normal = payload.get("rest_normal", False)
        important_fields = payload.get("important_fields")

        # Template lookup (stage 2)
        try:
            template = self._registry.get_template(study_type)
        except TemplateNotFoundError:
            return {"id": msg_id, "st": "E", "ct": "Unknown study type"}

        # Sex inference and field filtering (D-20)
        sex = self._infer_sex(findings)
        if sex is not None:
            findings = self._filter_sex_fields(findings, template, sex)

        # Audit log
        logger.info(
            f"[RENDER] ID: {msg_id} | Study: {study_type} | Fields: {len(findings)}"
        )

        # Render report (stage 4)
        report = template_render_report(
            template=template,
            findings=findings,
            technique=technique,
            important_fields=important_fields,
            rest_normal=rest_normal,
        )

        logger.info(f"[RENDER_OK] ID: {msg_id} | Length: {len(report)}")
        return {"id": msg_id, "st": "S", "ct": report}

    # -- fn='report': full 5-stage pipeline (stages 1,3,5 are stubs) ------

    def _handle_report(self, msg_id: str, draft: str) -> dict:
        """Handle fn='report' — full pipeline with LLM stubs.

        Runs all 5 stages. Stages 1, 3, 5 raise NotImplementedError
        until LLM integration is complete.

        Args:
            msg_id: Message ID for response and audit logging.
            draft: Radiologist's draft text.

        Returns:
            Response dict with formatted report on success, error on failure.
        """
        try:
            study_type = self._classify_study_type(draft)
            template = self._registry.get_template(study_type)
            findings = self._extract_findings(draft, template)
            report = template_render_report(
                template=template,
                findings=findings,
                technique={},
            )
            impression = self._generate_impression(report)
            final = f"{report}\n\nIMPRESSION:\n{impression}"
            return {"id": msg_id, "st": "S", "ct": final}
        except NotImplementedError as e:
            return {
                "id": msg_id,
                "st": "E",
                "ct": f"Stage not implemented: {str(e)} requires LLM connection",
            }
        except TemplateNotFoundError:
            return {"id": msg_id, "st": "E", "ct": "Unknown study type"}
        except Exception as e:
            logger.error(f"[REPORT_FAIL] ID: {msg_id} | Error: {e}")
            return {"id": msg_id, "st": "E", "ct": str(e)}

    # -- Sex inference (D-20) ----------------------------------------------

    def _infer_sex(self, findings: dict) -> str | None:
        """Infer patient sex from findings keys.

        Checks for sex-specific anatomy keys to determine filtering.

        Args:
            findings: Field name -> finding text mapping.

        Returns:
            'male' if prostate present, 'female' if uterus/ovaries present, None otherwise.
        """
        keys = set(findings.keys())
        if keys & {"prostate"}:
            return "male"
        if keys & {"uterus", "ovaries"}:
            return "female"
        return None

    def _filter_sex_fields(
        self, findings: dict, template: LoadedTemplate, sex: str
    ) -> dict:
        """Remove findings for fields tagged with the opposite sex.

        Args:
            findings: Field name -> finding text mapping.
            template: Loaded template with sex-tagged field definitions.
            sex: Inferred patient sex ('male' or 'female').

        Returns:
            Filtered findings dict without opposite-sex fields.
        """
        opposite = "female" if sex == "male" else "male"
        exclude = {f.name for f in template.schema.fields if f.sex == opposite}
        return {k: v for k, v in findings.items() if k not in exclude}

    # -- Stage stubs (LLM stages 1, 3, 5) ---------------------------------

    def _classify_study_type(self, draft: str) -> str:
        """Stage 1: Identify imaging modality and body region from draft."""
        raise NotImplementedError("Study type classification")

    def _extract_findings(self, draft: str, template: LoadedTemplate) -> dict:
        """Stage 3: Extract findings from draft and map to template fields."""
        raise NotImplementedError("Findings extraction")

    def _generate_impression(self, report: str) -> str:
        """Stage 5: Generate the impression / conclusion."""
        raise NotImplementedError("Impression generation")
