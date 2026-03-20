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

