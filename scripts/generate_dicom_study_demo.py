#!/usr/bin/env python3
"""
Generate one study-level JSON analysis for data/DICOM_Study via Anthropic.

Behavior:
- Selects 10 evenly spaced slices per series for model context.
- Saves 3 representative slices per series (start/middle/end) for webpage display.
- Extracts curated metadata for each series.
- Sends exactly one multimodal Anthropic request (images + metadata + instructions).
- Saves one static JSON artifact for the demo webpage.

Usage (from repo root):
  pip3 install -r requirements-dicom-study-demo.txt
  export ANTHROPIC_API_KEY="..."
  python3 scripts/generate_dicom_study_demo.py

Optional env:
  DICOM_DEMO_MODEL=claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STUDY_DIR = REPO_ROOT / "data" / "DICOM_Study"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "projects" / "dicom-study-demo" / "fixtures"
DEFAULT_OUTPUT = DEFAULT_FIXTURE_DIR / "study-analysis.json"
DEFAULT_REQUEST_META = DEFAULT_FIXTURE_DIR / "request-metadata.json"
DEFAULT_MODEL = os.environ.get("DICOM_DEMO_MODEL", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))

DISCLAIMER = (
    "Educational portfolio demo only. This output is generated from anonymized sample DICOM data and "
    "is not medical advice, not a diagnosis, and not a substitute for licensed clinical review."
)

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass


@dataclass
class SelectedSlice:
    series_id: str
    source_path: Path
    label: str
    instance_number: int | None
    output_relpath: str
    width: int
    height: int
    encoded_png_b64: str


def _as_scalar(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict)):
        try:
            value_list = list(value)
        except TypeError:
            return value
        return value_list[0] if value_list else None
    return value


def _safe_float(value: Any) -> float | None:
    value = _as_scalar(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    value = _as_scalar(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stringify_list(value: Any, max_items: int = 6) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        items = list(value)
    except TypeError:
        return [str(value)]
    out: list[str] = []
    for item in items[:max_items]:
        out.append(str(item))
    return out


def _window_normalize(pixel_array: np.ndarray, ds: pydicom.Dataset) -> np.ndarray:
    arr = pixel_array.astype(np.float32)

    slope = _safe_float(getattr(ds, "RescaleSlope", None))
    intercept = _safe_float(getattr(ds, "RescaleIntercept", None))
    if slope is not None:
        arr *= slope
    if intercept is not None:
        arr += intercept

    wc = _safe_float(getattr(ds, "WindowCenter", None))
    ww = _safe_float(getattr(ds, "WindowWidth", None))
    if wc is not None and ww is not None and ww > 1:
        low = wc - ww / 2.0
        high = wc + ww / 2.0
        arr = np.clip(arr, low, high)
    else:
        p1 = float(np.percentile(arr, 1.0))
        p99 = float(np.percentile(arr, 99.0))
        if p99 <= p1:
            p1 = float(np.min(arr))
            p99 = float(np.max(arr))
        if p99 > p1:
            arr = np.clip(arr, p1, p99)

    min_v = float(np.min(arr))
    max_v = float(np.max(arr))
    if max_v <= min_v:
        out = np.zeros_like(arr, dtype=np.uint8)
    else:
        out = ((arr - min_v) / (max_v - min_v) * 255.0).astype(np.uint8)

    photometric = str(getattr(ds, "PhotometricInterpretation", "")).upper()
    if photometric == "MONOCHROME1":
        out = 255 - out
    return out


def _read_series_files(series_dir: Path) -> list[Path]:
    files = []
    for p in sorted(series_dir.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            files.append(p)
    return files


def _decoder_help_text(exc: Exception) -> str:
    msg = str(exc)
    if "missing required dependencies" in msg or "handlers are available to decode the pixel data" in msg:
        return (
            "Compressed DICOM pixel data needs decoder plugins. "
            "Install/upgrade with: pip3 install -r requirements-dicom-study-demo.txt "
            "(includes pylibjpeg, pylibjpeg-libjpeg, and pylibjpeg-openjpeg)."
        )
    return ""


def _instance_key(ds: pydicom.Dataset, fallback: int) -> tuple[int, int]:
    instance_number = _safe_int(getattr(ds, "InstanceNumber", None))
    return (0, instance_number) if instance_number is not None else (1, fallback)


def _select_indices(length: int) -> list[int]:
    if length <= 0:
        return []
    candidates = [0, length // 2, length - 1]
    dedup: list[int] = []
    for idx in candidates:
        if idx not in dedup:
            dedup.append(idx)
    return dedup


def _select_evenly_spaced_indices(length: int, count: int) -> list[int]:
    if length <= 0 or count <= 0:
        return []
    if length == 1:
        return [0]
    if count >= length:
        return list(range(length))
    out: list[int] = []
    for i in range(count):
        idx = round(i * (length - 1) / (count - 1))
        if idx not in out:
            out.append(idx)
    return out


def _extract_series_metadata(ds: pydicom.Dataset, series_id: str, instance_count: int) -> dict[str, Any]:
    return {
        "series_id": series_id,
        "series_instance_uid": str(getattr(ds, "SeriesInstanceUID", "")),
        "study_instance_uid": str(getattr(ds, "StudyInstanceUID", "")),
        "modality": str(getattr(ds, "Modality", "")),
        "series_description": str(getattr(ds, "SeriesDescription", "")),
        "protocol_name": str(getattr(ds, "ProtocolName", "")),
        "body_part_examined": str(getattr(ds, "BodyPartExamined", "")),
        "image_type": _stringify_list(getattr(ds, "ImageType", None)),
        "orientation": [v for v in (_as_scalar(x) for x in _stringify_list(getattr(ds, "ImageOrientationPatient", None), 12)) if v is not None],
        "rows": _safe_int(getattr(ds, "Rows", None)),
        "columns": _safe_int(getattr(ds, "Columns", None)),
        "pixel_spacing": _stringify_list(getattr(ds, "PixelSpacing", None), 4),
        "slice_thickness": _safe_float(getattr(ds, "SliceThickness", None)),
        "spacing_between_slices": _safe_float(getattr(ds, "SpacingBetweenSlices", None)),
        "window_center": _safe_float(getattr(ds, "WindowCenter", None)),
        "window_width": _safe_float(getattr(ds, "WindowWidth", None)),
        "rescale_slope": _safe_float(getattr(ds, "RescaleSlope", None)),
        "rescale_intercept": _safe_float(getattr(ds, "RescaleIntercept", None)),
        "photometric_interpretation": str(getattr(ds, "PhotometricInterpretation", "")),
        "instance_count": instance_count,
    }


def _build_prompt(study_id: str, series_meta: list[dict[str, Any]], selected_slices: list[dict[str, Any]]) -> str:
    schema = {
        "study_id": "string",
        "series_count": "number",
        "series_analysis": [
            {
                "series_id": "string",
                "likely_series_type": "string",
                "series_type_confidence": "number between 0 and 1",
                "rationale": "string",
                "visual_description": "string",
                "possible_findings": [
                    {
                        "finding": "string",
                        "confidence": "number between 0 and 1",
                        "evidence": "string",
                    }
                ],
                "uncertainties": ["string"],
            }
        ],
        "study_visual_description": "string",
        "possible_findings": [
            {
                "series_id": "string",
                "finding": "string",
                "confidence": "number between 0 and 1",
                "evidence": "string",
            }
        ],
        "uncertainties": ["string"],
        "safety_note": "string",
    }
    return (
        "You are assisting with a non-clinical software portfolio demo using anonymized sample DICOM data.\n\n"
        "Task:\n"
        "1) Describe what is visible in each imaging series.\n"
        "2) Infer likely series type/sequence when possible.\n"
        "3) Include possible findings and provide confidence for each finding.\n\n"
        "Confidence policy:\n"
        "- Always include a numeric confidence (0 to 1) for each possible finding.\n"
        "- Keep uncertainties explicit.\n\n"
        "Output rules:\n"
        "- Return exactly one JSON object.\n"
        "- No markdown fences.\n"
        "- No extra keys outside the schema.\n"
        "- Use empty arrays where needed.\n\n"
        f"Required schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Study ID: {study_id}\n\n"
        f"Series metadata:\n{json.dumps(series_meta, indent=2)}\n\n"
        f"Selected image manifest:\n{json.dumps(selected_slices, indent=2)}\n\n"
        "The final safety note must clearly state this is not medical advice."
    )


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
        raise TypeError("Top-level model output must be a JSON object.")
    return obj


def _validate_model_output(obj: dict[str, Any], study_id: str, expected_series: int) -> dict[str, Any]:
    required_keys = {
        "study_id",
        "series_count",
        "series_analysis",
        "study_visual_description",
        "possible_findings",
        "uncertainties",
        "safety_note",
    }
    missing = [k for k in required_keys if k not in obj]
    if missing:
        raise ValueError(f"Missing output keys: {missing}")

    if str(obj["study_id"]).strip() != study_id:
        raise ValueError("Model study_id does not match expected study_id.")
    if _safe_int(obj["series_count"]) != expected_series:
        raise ValueError("Model series_count does not match expected series count.")
    if not isinstance(obj["series_analysis"], list):
        raise TypeError("series_analysis must be an array.")
    if not isinstance(obj["possible_findings"], list):
        raise TypeError("possible_findings must be an array.")
    if not isinstance(obj["uncertainties"], list):
        raise TypeError("uncertainties must be an array of strings.")
    if not isinstance(obj["study_visual_description"], str):
        raise TypeError("study_visual_description must be a string.")
    if not isinstance(obj["safety_note"], str):
        raise TypeError("safety_note must be a string.")

    for finding in obj["possible_findings"]:
        if not isinstance(finding, dict):
            raise TypeError("Each possible finding must be an object.")
        conf = _safe_float(finding.get("confidence"))
        if conf is None:
            raise ValueError("Study-level finding is missing numeric confidence.")
        if conf < 0.0 or conf > 1.0:
            raise ValueError("Study-level finding confidence must be between 0 and 1.")

    for series in obj["series_analysis"]:
        if not isinstance(series, dict):
            raise TypeError("Each series_analysis item must be an object.")
        required_series = {
            "series_id",
            "likely_series_type",
            "series_type_confidence",
            "rationale",
            "visual_description",
            "possible_findings",
            "uncertainties",
        }
        missing_series = [k for k in required_series if k not in series]
        if missing_series:
            raise ValueError(f"Series output missing keys: {missing_series}")
        if not isinstance(series["possible_findings"], list):
            raise TypeError("series_analysis.possible_findings must be an array.")
        for finding in series["possible_findings"]:
            if not isinstance(finding, dict):
                raise TypeError("Series finding must be an object.")
            conf = _safe_float(finding.get("confidence"))
            if conf is None:
                raise ValueError("Series finding is missing numeric confidence.")
            if conf < 0.0 or conf > 1.0:
                raise ValueError("Series finding confidence must be between 0 and 1.")

    return obj


def _load_series_payload(
    study_dir: Path,
    fixture_dir: Path,
    image_dir_name: str = "images",
    max_dim: int = 768,
    analysis_slices_per_series: int = 10,
) -> tuple[str, list[dict[str, Any]], list[SelectedSlice], list[SelectedSlice]]:
    image_dir = fixture_dir / image_dir_name
    image_dir.mkdir(parents=True, exist_ok=True)

    series_dirs = sorted([p for p in study_dir.iterdir() if p.is_dir() and p.name.startswith("series-")])
    if not series_dirs:
        raise FileNotFoundError(f"No series directories found in {study_dir}")

    study_id = study_dir.name
    series_meta: list[dict[str, Any]] = []
    selected_for_analysis: list[SelectedSlice] = []
    selected_for_display: list[SelectedSlice] = []

    for series_dir in series_dirs:
        files = _read_series_files(series_dir)
        if not files:
            continue

        loaded: list[tuple[pydicom.Dataset, Path, int]] = []
        for idx, fp in enumerate(files):
            try:
                ds = pydicom.dcmread(fp, force=True)
            except Exception:
                continue
            loaded.append((ds, fp, idx))
        if not loaded:
            continue

        loaded.sort(key=lambda tup: _instance_key(tup[0], tup[2]))
        sample_ds = loaded[0][0]
        series_meta.append(_extract_series_metadata(sample_ds, series_dir.name, len(loaded)))

        display_indices = _select_indices(len(loaded))
        display_label_by_idx = {}
        display_labels = ["start", "middle", "end"]
        for k, idx in enumerate(display_indices):
            if k < len(display_labels):
                display_label_by_idx[idx] = display_labels[k]

        analysis_indices = _select_evenly_spaced_indices(len(loaded), analysis_slices_per_series)
        analysis_rank_by_idx = {idx: rank for rank, idx in enumerate(analysis_indices)}
        all_indices = sorted(set(analysis_indices) | set(display_indices))

        for idx in all_indices:
            ds, src_path, _ = loaded[idx]
            try:
                pix = ds.pixel_array
            except Exception as exc:
                decoder_hint = _decoder_help_text(exc)
                detail = f"Could not decode pixels for {src_path}: {exc}"
                if decoder_hint:
                    detail = f"{detail}\n{decoder_hint}"
                raise RuntimeError(detail) from exc
            img_u8 = _window_normalize(pix, ds)
            pil = Image.fromarray(img_u8)
            if pil.mode != "L":
                pil = pil.convert("L")
            pil.thumbnail((max_dim, max_dim))

            # Re-encode as PNG bytes for Anthropic image input.
            png_buffer = BytesIO()
            pil.save(png_buffer, format="PNG", optimize=True)
            png_bytes = png_buffer.getvalue()
            encoded_png = base64.b64encode(png_bytes).decode("ascii")

            if idx in analysis_rank_by_idx:
                analysis_rank = analysis_rank_by_idx[idx] + 1
                analysis_label = f"slice-{analysis_rank:02d}"
                analysis_ref = f"analysis://{series_dir.name}/{analysis_label}"
                analysis_slice = SelectedSlice(
                    series_id=series_dir.name,
                    source_path=src_path,
                    label=analysis_label,
                    instance_number=_safe_int(getattr(ds, "InstanceNumber", None)),
                    output_relpath=analysis_ref,
                    width=pil.width,
                    height=pil.height,
                    encoded_png_b64=encoded_png,
                )
                selected_for_analysis.append(analysis_slice)

            if idx in display_label_by_idx:
                display_label = display_label_by_idx[idx]
                out_name = f"{series_dir.name}_{display_label}_{idx:03d}.png"
                out_path = image_dir / out_name
                pil.save(out_path, format="PNG", optimize=True)
                rel_path = f"fixtures/{image_dir_name}/{out_name}"
                selected_for_display.append(
                    SelectedSlice(
                        series_id=series_dir.name,
                        source_path=src_path,
                        label=display_label,
                        instance_number=_safe_int(getattr(ds, "InstanceNumber", None)),
                        output_relpath=rel_path,
                        width=pil.width,
                        height=pil.height,
                        encoded_png_b64=encoded_png,
                    )
                )

    if not series_meta or not selected_for_analysis:
        raise RuntimeError("No valid series and slices found for processing.")
    return study_id, series_meta, selected_for_analysis, selected_for_display


def _call_anthropic_once(
    model: str,
    study_id: str,
    series_meta: list[dict[str, Any]],
    selected: list[SelectedSlice],
) -> dict[str, Any]:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to .env or export it in your shell.")

    content_blocks: list[dict[str, Any]] = []
    prompt = _build_prompt(
        study_id=study_id,
        series_meta=series_meta,
        selected_slices=[
            {
                "series_id": s.series_id,
                "slice_label": s.label,
                "instance_number": s.instance_number,
                "image_path": s.output_relpath,
                "width": s.width,
                "height": s.height,
            }
            for s in selected
        ],
    )
    content_blocks.append({"type": "text", "text": prompt})
    for s in selected:
        content_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": s.encoded_png_b64,
                },
            }
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        temperature=0.1,
        messages=[{"role": "user", "content": content_blocks}],
    )

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    if not text_blocks:
        raise RuntimeError("Anthropic response did not include a text block with JSON output.")
    full_text = "".join(text_blocks).strip()
    try:
        return _extract_json_object(full_text)
    except json.JSONDecodeError as exc:
        stop_reason = getattr(response, "stop_reason", "")
        if stop_reason == "max_tokens":
            raise RuntimeError(
                "Model output was truncated at max_tokens before JSON completed. "
                "Reduce prompt size or selected slices, or raise max_tokens."
            ) from exc
        raise RuntimeError(
            f"Could not parse model output as JSON (stop_reason={stop_reason or 'unknown'}): {exc}"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one-shot DICOM study analysis via Anthropic.")
    parser.add_argument("--study-dir", type=Path, default=DEFAULT_STUDY_DIR, help=f"DICOM study folder (default: {DEFAULT_STUDY_DIR})")
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR, help=f"Output fixtures folder (default: {DEFAULT_FIXTURE_DIR})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"Final study JSON path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--request-meta", type=Path, default=DEFAULT_REQUEST_META, help=f"Request metadata JSON path (default: {DEFAULT_REQUEST_META})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if not args.study_dir.is_dir():
        print(f"Error: study dir not found: {args.study_dir}", file=sys.stderr)
        sys.exit(1)

    study_id, series_meta, selected_analysis, selected_display = _load_series_payload(args.study_dir, args.fixture_dir)
    print(
        f"Prepared {len(selected_analysis)} analysis slices and {len(selected_display)} display slices "
        f"across {len(series_meta)} series.",
        flush=True,
    )
    print("Calling Anthropic once for study analysis...", flush=True)
    raw_output = _call_anthropic_once(args.model, study_id, series_meta, selected_analysis)
    validated = _validate_model_output(raw_output, study_id, len(series_meta))

    selected_manifest = [
        {
            "series_id": s.series_id,
            "slice_label": s.label,
            "instance_number": s.instance_number,
            "source_file": str(s.source_path.relative_to(REPO_ROOT)),
            "image_path": s.output_relpath,
            "width": s.width,
            "height": s.height,
        }
        for s in selected_display
    ]

    output_payload = {
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "study_id": study_id,
        "series_count": len(series_meta),
        "selected_slice_count": len(selected_manifest),
        "analysis_slice_count": len(selected_analysis),
        "series_metadata": series_meta,
        "selected_slices": selected_manifest,
        "analysis": validated,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    request_meta = {
        "generated_at": output_payload["generated_at"],
        "model": args.model,
        "api_calls": 1,
        "study_dir": str(args.study_dir),
        "output_json": str(args.output),
        "series_count": len(series_meta),
        "selected_slice_count": len(selected_manifest),
        "analysis_slice_count": len(selected_analysis),
    }
    args.request_meta.parent.mkdir(parents=True, exist_ok=True)
    with open(args.request_meta, "w", encoding="utf-8") as f:
        json.dump(request_meta, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {args.output}", flush=True)
    print(f"Wrote {args.request_meta}", flush=True)


if __name__ == "__main__":
    main()
