#!/usr/bin/env python3
"""
Generate projects/report-summarizer/fixtures/reports.json from fixtures/reports_input.json
using the Anthropic API (run locally; API key never shipped to GitHub Pages).

Usage (from repo root):
  export ANTHROPIC_API_KEY="..."
  pip3 install -r requirements-report-summarizer.txt
  python3 scripts/generate_report_summaries.py

Optional: ANTHROPIC_MODEL (default: claude-sonnet-4-6)
Loads .env from repo root if python-dotenv is installed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "projects" / "report-summarizer" / "fixtures" / "reports_input.json"
DEFAULT_OUTPUT = REPO_ROOT / "projects" / "report-summarizer" / "fixtures" / "reports.json"

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

SUMMARY_KEYS = (
    "impressionSummary",
    "keyFindings",
    "followUpRecommendations",
    "patientSummary",
)


def build_prompt(raw_report: str) -> str:
    return f"""You are helping build a software portfolio demo. The radiology report below is SYNTHETIC and fictional for illustration only—not a real patient.

Produce four audience-specific summaries as JSON with exactly these keys:
- "impressionSummary": string — concise, radiologist-style impression (plain language OK).
- "keyFindings": array of strings — bullet-style facts (3–6 items).
- "followUpRecommendations": string — practical follow-up / correlation / when to escalate (not a substitute for a clinician).
- "patientSummary": string — short plain-language explanation for a lay reader.

Return ONLY a single JSON object with those four keys. No markdown fences, no commentary before or after the JSON.

Report text:
---
{raw_report}
---
"""


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() in ("```", ""):
            lines.pop()
        text = "\n".join(lines).strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model response")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise TypeError("Top-level JSON must be an object")
    return obj


def validate_summaries(obj: dict, report_id: str) -> dict:
    missing = [k for k in SUMMARY_KEYS if k not in obj]
    if missing:
        raise ValueError(f"Report {report_id}: missing keys {missing}")
    if not isinstance(obj["impressionSummary"], str):
        raise TypeError(f"Report {report_id}: impressionSummary must be a string")
    if not isinstance(obj["keyFindings"], list) or not all(
        isinstance(x, str) for x in obj["keyFindings"]
    ):
        raise TypeError(f"Report {report_id}: keyFindings must be an array of strings")
    if not isinstance(obj["followUpRecommendations"], str):
        raise TypeError(f"Report {report_id}: followUpRecommendations must be a string")
    if not isinstance(obj["patientSummary"], str):
        raise TypeError(f"Report {report_id}: patientSummary must be a string")
    return {
        "impressionSummary": obj["impressionSummary"].strip(),
        "keyFindings": [s.strip() for s in obj["keyFindings"] if s.strip()],
        "followUpRecommendations": obj["followUpRecommendations"].strip(),
        "patientSummary": obj["patientSummary"].strip(),
    }


def call_anthropic(model: str, prompt: str) -> dict:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Export it or add it to .env in the repo root.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    block = message.content[0]
    if block.type != "text":
        raise RuntimeError(f"Unexpected block type: {block.type}")
    return extract_json_object(block.text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reports.json via Anthropic API.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input JSON (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model id (default: env ANTHROPIC_MODEL or {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    disclaimer = data.get("disclaimer", "")
    reports_in = data.get("reports")
    if not isinstance(reports_in, list):
        print("Error: 'reports' must be an array.", file=sys.stderr)
        sys.exit(1)

    out_reports = []
    for i, rep in enumerate(reports_in):
        rid = rep.get("id", f"index-{i}")
        for key in ("id", "title", "modality", "rawReport"):
            if key not in rep:
                print(f"Error: report {rid} missing '{key}'", file=sys.stderr)
                sys.exit(1)
        print(f"Generating summaries for {rid} ({i + 1}/{len(reports_in)})...", flush=True)
        prompt = build_prompt(rep["rawReport"])
        raw_obj = call_anthropic(args.model, prompt)
        summaries = validate_summaries(raw_obj, rid)
        out_reports.append(
            {
                "id": rep["id"],
                "title": rep["title"],
                "modality": rep["modality"],
                "rawReport": rep["rawReport"],
                "summaries": summaries,
            }
        )

    output = {"disclaimer": disclaimer, "reports": out_reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
