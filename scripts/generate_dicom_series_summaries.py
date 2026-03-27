#!/usr/bin/env python3
"""
Generate concise per-series summaries for dicom-study-demo outputs.

This script is a second offline pass that reads the generated study JSON and
adds `concise_summary` to each `analysis.series_analysis[*]` item by calling
Anthropic once per series.

Usage (from repo root):
  python3 scripts/generate_dicom_series_summaries.py

Optional:
  python3 scripts/generate_dicom_series_summaries.py --input projects/dicom-study-demo/fixtures/study-analysis.json --output projects/dicom-study-demo/fixtures/study-analysis.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "projects" / "dicom-study-demo" / "fixtures" / "study-analysis.json"
DEFAULT_OUTPUT = DEFAULT_INPUT
DEFAULT_MODEL = os.environ.get("DICOM_DEMO_MODEL", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass


def _extract_json_object(text: str) -> dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() in ("```", ""):
            lines.pop()
        content = "\n".join(lines).strip()
    start = content.find("{")
    if start < 0:
        raise ValueError("No JSON object found in model response.")
    obj, _ = json.JSONDecoder().raw_decode(content[start:])
    if not isinstance(obj, dict):
        raise TypeError("Expected JSON object.")
    return obj


def _call_summary(model: str, series_obj: dict[str, Any]) -> str:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    payload = {
        "series_id": series_obj.get("series_id"),
        "likely_series_type": series_obj.get("likely_series_type"),
        "series_type_confidence": series_obj.get("series_type_confidence"),
        "visual_description": series_obj.get("visual_description"),
        "possible_findings": series_obj.get("possible_findings", []),
        "uncertainties": series_obj.get("uncertainties", []),
    }
    prompt = (
        "You are helping create concise portfolio demo copy.\n"
        "Summarize the series interpretation in 1-2 sentences.\n"
        "Include any notable possible findings with confidence when present.\n"
        "Mention uncertainty only if clinically relevant.\n"
        "Do not provide medical advice.\n\n"
        "Return JSON only:\n"
        '{ "concise_summary": "..." }\n\n'
        f"Series input:\n{json.dumps(payload, indent=2)}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=300,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    if not text_blocks:
        raise RuntimeError("No text response from Anthropic for series summary.")
    obj = _extract_json_object("".join(text_blocks))
    summary = obj.get("concise_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Invalid concise_summary in response.")
    return summary.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate concise per-series summaries via Anthropic.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help=f"Input study JSON (default: {DEFAULT_INPUT})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"Output study JSON (default: overwrite input)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model id (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    analysis = data.get("analysis")
    if not isinstance(analysis, dict):
        print("Error: missing 'analysis' object in input JSON.", file=sys.stderr)
        sys.exit(1)
    series_list = analysis.get("series_analysis")
    if not isinstance(series_list, list) or not series_list:
        print("Error: missing or empty 'analysis.series_analysis'.", file=sys.stderr)
        sys.exit(1)

    for i, series in enumerate(series_list):
        sid = series.get("series_id", f"index-{i}")
        print(f"Summarizing {sid} ({i + 1}/{len(series_list)})...", flush=True)
        series["concise_summary"] = _call_summary(args.model, series)

    data.setdefault("postprocessing", {})
    if isinstance(data["postprocessing"], dict):
        data["postprocessing"]["series_summary_model"] = args.model
        data["postprocessing"]["series_summary_count"] = len(series_list)
        data["postprocessing"]["series_summary_api_calls"] = len(series_list)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
