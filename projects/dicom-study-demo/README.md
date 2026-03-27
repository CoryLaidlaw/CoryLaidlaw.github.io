# DICOM study one-call demo (static)

The page at `projects/dicom-study-demo/` reads local fixture files only:
- `fixtures/study-analysis.json`
- `fixtures/images/*.png`

No Anthropic calls happen in the browser.

## Workflow

1. Ensure `.env` contains `ANTHROPIC_API_KEY`.
2. Install dependencies:

```bash
pip3 install -r requirements-dicom-study-demo.txt
```

Note: this requirements file includes DICOM decoder plugins (`pylibjpeg*`) needed for compressed transfer syntaxes.

3. Generate outputs:

```bash
python3 scripts/generate_dicom_study_demo.py
```

4. Optional second pass: generate concise per-series summaries:

```bash
python3 scripts/generate_dicom_series_summaries.py
```

This script:
- scans `data/DICOM_Study/series-*`,
- picks 10 evenly spaced slices per series for model analysis,
- saves `start`, `middle`, and `end` slices per series for webpage display,
- builds curated metadata,
- sends one multimodal Anthropic request,
- includes model-reported confidence values for possible findings,
- writes static artifacts used by the page.
- optional second pass adds `concise_summary` under each `analysis.series_analysis` entry.

## Output files

- `fixtures/study-analysis.json` (single study-level structured JSON)
- `fixtures/request-metadata.json` (contains `api_calls: 1`, model, timestamp)
- `fixtures/images/*.png` (display thumbnails: start/middle/end per series)

## Local preview

Serve from repo root:

```bash
python3 -m http.server 8080
```

Then open: `http://localhost:8080/projects/dicom-study-demo/`

## Safety

Educational demo only. Not a medical device and not for diagnosis, screening, or treatment decisions.
