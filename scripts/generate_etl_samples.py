#!/usr/bin/env python3
"""
Deterministically regenerate static CSV samples for the ETL Playground.
Run from repo root: python3 scripts/generate_etl_samples.py

Outputs UTF-8 with \\n line endings only (no runtime dependency on the site).
"""
from __future__ import annotations

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "etl-samples"


def write_customers() -> None:
    lines = [
        "customer_id,name,signup_date,email,notes",
        "1,  Alice Smith ,2023-01-15,alice@example.com,ok",
        "2,Bob Jones,01/15/2023,bob@example.com,",
        "3,  alice smith ,N/A,alice@example.com,duplicate spacing",
        "4,Carol White,2023-13-40,carol@example.com,bad date",
        "5,Dan Lee,null,dan@example.com,null token",
        "6,Eve Park,2023-06-01,eve@example.com,",
        "7,Fay Kim,06/01/2023,fay@example.com,US format",
        "8,Bob Jones,01/15/2023,bob@example.com,duplicate row",
        "",
    ]
    (OUT_DIR / "customers_dirty.csv").write_text("\n".join(lines), encoding="utf-8")


def write_sales() -> None:
    lines = [
        "order_id,amount,region",
        'A1,"1,250.50",west',
        "A2,  99.0  ,east",
        "A3,not_a_number,north",
        "A4,500000,outlier",
        "A5,12.5,south",
        ",,east",
        'A7,"1,250.00",west',
        "",
    ]
    (OUT_DIR / "sales_messy.csv").write_text("\n".join(lines), encoding="utf-8")


def write_events() -> None:
    lines = [
        "event_id,event_date,source",
        "E1,2024-03-01,web",
        "E2,03/15/2024,mobile",
        "E3,2024-03-20,web",
        "E1,2024-03-01,web",
        "E4,15/03/2024,api",
        "E5,2024-99-01,bad",
        "",
    ]
    (OUT_DIR / "events_log.csv").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_customers()
    write_sales()
    write_events()
    print(f"Wrote samples to {OUT_DIR}")


if __name__ == "__main__":
    main()
