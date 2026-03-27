# Radiology report summarizer (static demo)

The page at `projects/report-summarizer/` loads **`fixtures/reports.json` only**—no API calls, no keys in the browser, GitHub Pages safe.

## Synthetic data

Reports and summaries are **illustrative only**. They are **not** real patient information, **not** clinical guidance, and **not** medical advice.

## Regenerating summaries (local, Anthropic API)

Source inputs live in **`fixtures/reports_input.json`** (disclaimer + `id` / `title` / `modality` / `rawReport` per report). To fill or refresh **`fixtures/reports.json`** using Claude:

1. Copy `.env.example` to `.env` and set **`ANTHROPIC_API_KEY`** (never commit `.env`).
2. Install Python deps (build machine only):

   ```bash
   pip3 install -r requirements-report-summarizer.txt
   ```

3. From the repo root:

   ```bash
   python3 scripts/generate_report_summaries.py
   ```

Optional: **`ANTHROPIC_MODEL`** in `.env` (default: `claude-sonnet-4-6`). See [Anthropic model IDs](https://docs.anthropic.com/en/docs/about-claude/models) if you need to switch. The script writes `fixtures/reports.json`; commit it when you are happy with the output.

## Local preview

Serve from the repo root so `fetch()` works (not `file://`):

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080/projects/report-summarizer/`.
