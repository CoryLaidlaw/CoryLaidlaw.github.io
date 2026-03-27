# CoryLaidlaw.github.io

Personal portfolio (GitHub Pages). Static HTML/CSS/JS.

## US grid mix dashboard

Interactive dashboard at `dashboard/`: linked charts and a rule-based insight panel driven by shared filters. Data is pre-aggregated JSON in `data/` so the live site stays static and fast.

### Regenerating dashboard data

Option A — EIA API (recommended)

Register for a key at [EIA Open Data](https://www.eia.gov/opendata/register.php). Do not commit the key (`.env` is gitignored; see `.env.example`).

From the repo root:

```bash
export EIA_API_KEY="your_key_here"
python3 scripts/build_eia_aggregate.py --fetch
# optional: --start-year 2001 --end-year 2024
```

This overwrites `data/eia_annual_input.csv`, rebuilds `data/eia-generation-annual.json`, and updates `data/eia-meta.json` (methodology + `last_data_build`). Default `--end-year` is `2024` so you avoid incomplete latest-year data.

Option B — Manual CSV

Edit `data/eia_annual_input.csv` (columns `year`, `coal`, `gas`, `nuclear`, `hydro`, `wind`, `solar`, `other`; values in `GWh`), then:

```bash
python3 scripts/build_eia_aggregate.py
```

Commit the updated `data/*.csv`, `data/eia-generation-annual.json`, and `data/eia-meta.json` when you are happy with the figures.

### Local preview

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080/dashboard/` (serving from the repo root avoids `fetch` failures from the `file://` protocol).

## Model comparison console

Static demo at `model-console/`: compares offline-trained scikit-learn pipelines on a phishing URL dataset using precomputed JSON in `data/model-eval-results.json` and methodology in `data/model-eval-meta.json`.

### Regenerating evaluation JSON

Install Python dependencies (build-time only):

```bash
pip3 install -r requirements-ml.txt
```

From the repo root:

```bash
python3 scripts/build_model_eval.py
# optional: --max-rows 100000  (default 75000 stratified rows; use 0 for full dataset — slow)
```

This overwrites `data/model-eval-results.json` and `data/model-eval-meta.json` (includes `last_data_build` and a short `results_id` hash).

Preview: `http://localhost:8080/model-console/`

## Pediatric chest X-ray demo (TensorFlow.js)

Static demo at `projects/cxr-demo/`: binary NORMAL vs PNEUMONIA on curated samples; model and metrics are generated offline. See [`docs/cxr-demo.md`](docs/cxr-demo.md) for dataset attribution, training, and export.

Preview: `http://localhost:8080/projects/cxr-demo/`

## Radiology report summarizer

Static demo at `projects/report-summarizer/`: the browser loads bundled JSON only (no live API on the site). You can **regenerate** `fixtures/reports.json` locally with `scripts/generate_report_summaries.py` and the Anthropic API using `fixtures/reports_input.json` as the source—see [`projects/report-summarizer/README.md`](projects/report-summarizer/README.md).

Preview: `http://localhost:8080/projects/report-summarizer/`

## DICOM study one-call demo

Static demo at `projects/dicom-study-demo/`: one anonymized DICOM study is preprocessed offline, representative slices are sent in a single direct Anthropic multimodal API call, and the site renders only generated static JSON and PNG files.

### Generate study analysis (local only)

1. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` (never commit `.env`).
2. Install build-time Python dependencies:

```bash
pip3 install -r requirements-dicom-study-demo.txt
```

3. Run from the repo root:

```bash
python3 scripts/generate_dicom_study_demo.py
```

This writes:
- `projects/dicom-study-demo/fixtures/study-analysis.json`
- `projects/dicom-study-demo/fixtures/request-metadata.json`
- `projects/dicom-study-demo/fixtures/images/*.png`

Cost-control guardrail: the script sends exactly one Anthropic API request per run (`api_calls: 1` is recorded in `request-metadata.json`).

Preview: `http://localhost:8080/projects/dicom-study-demo/`

Safety: demo output is educational only and not medical advice or diagnosis.

