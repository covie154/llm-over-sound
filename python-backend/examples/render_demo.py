#!/usr/bin/env python3
"""Minimal render demo -- standalone pipeline usage without ggwave.

Demonstrates that LLMPipeline is importable and callable independently
of the backend audio loop (per D-18, D-27).

Usage:
    cd python-backend
    python examples/render_demo.py
"""

import json
import sys
import os

# Ensure python-backend is on the path when running from examples/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.pipeline import LLMPipeline


def main():
    # Instantiate pipeline (loads all templates from rpt_templates/)
    pipeline = LLMPipeline()

    # Prepare a US HBS render request
    payload = json.dumps({
        "study_type": "us hbs",
        "findings": {
            "liver": "Normal in size and echotexture. No focal lesion.",
            "gallbladder_cbd": (
                "Gallbladder is well distended with no calculi. "
                "CBD measures 4mm."
            ),
            "spleen": "Normal in size.",
            "pancreas": "Visualised portions are unremarkable.",
        },
        "technique": {"cbd_diameter_mm": "4"},
        "rest_normal": False,
    })

    msg = {"id": "demo01", "fn": "render", "ct": payload}

    print("=" * 60)
    print("LLM Pipeline Render Demo")
    print("=" * 60)
    print(f"\nStudy type: us hbs")
    print(f"Function: render (bypasses LLM stages)\n")

    result = pipeline.process(msg)

    print(f"Status: {result['st']}")
    print(f"\n{'=' * 60}")
    print("RENDERED REPORT:")
    print("=" * 60)
    print(result["ct"])


if __name__ == "__main__":
    main()
