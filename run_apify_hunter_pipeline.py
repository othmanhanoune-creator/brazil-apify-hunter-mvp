from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BRONZE_INPUT = Path("data/lake/bronze/apify_google_maps/brazil_apify_raw.csv")

STEPS = [
    {
        "name": "Apify CSV to Silver + Gold + SQLite",
        "command": [
            sys.executable,
            "src/extractors/apify_google_maps_csv.py",
        ],
    },
    {
        "name": "Split Brazil Gold into Strong B2B and Review Queue",
        "command": [
            sys.executable,
            "src/transformers/split_brazil_gold.py",
        ],
    },
    {
        "name": "Website Email Enrichment for Strong Gold",
        "command": [
            sys.executable,
            "src/enrichment/email_enrich_strong_gold.py",
        ],
    },
    {
        "name": "Build Hunter Input",
        "command": [
            sys.executable,
            "src/enrichment/build_hunter_input.py",
        ],
    },
    {
        "name": "Clean Hunter Input",
        "command": [
            sys.executable,
            "src/enrichment/clean_hunter_input.py",
        ],
    },
    {
    "name": "Run Hunter API Enrichment",
    "command": [
        sys.executable,
        "src/enrichment/hunter_enrich_missing_emails.py",
        "--all",
    ],
},
    {
        "name": "Finalize Hunter Enrichment",
        "command": [
            sys.executable,
            "src/enrichment/finalize_hunter_enrichment.py",
        ],
    },
]


def run_step(name: str, command: list[str]) -> None:
    print("")
    print("=" * 90)
    print(f"RUNNING STEP: {name}")
    print("COMMAND:", " ".join(command))
    print("=" * 90)

    subprocess.run(command, check=True)


def main() -> None:
    if not BRONZE_INPUT.exists():
        raise FileNotFoundError(
            f"Missing Apify input file: {BRONZE_INPUT}\n"
            "Put your Apify Google Maps CSV there before running this pipeline."
        )

    if BRONZE_INPUT.stat().st_size == 0:
        raise ValueError(
            f"Apify input file exists but is empty: {BRONZE_INPUT}"
        )

    print("=" * 90)
    print("BRAZIL APIFY + HUNTER MVP PIPELINE")
    print("=" * 90)
    print(f"Input file: {BRONZE_INPUT}")
    print(f"Input size: {BRONZE_INPUT.stat().st_size:,} bytes")

    for step in STEPS:
        run_step(step["name"], step["command"])

    print("")
    print("=" * 90)
    print("PIPELINE COMPLETE")
    print("=" * 90)
    print("Main final output:")
    print("data/lake/gold/enriched_contacts/brazil_sales_ready_enriched_leads.csv")
    print("")
    print("Other key outputs:")
    print("data/lake/silver/leads_cleaned/brazil_silver_leads.csv")
    print("data/lake/gold/qualified_b2b_leads/brazil_qualified_b2b_leads.csv")
    print("data/lake/gold/qualified_b2b_leads/brazil_gold_strong_b2b.csv")
    print("data/warehouse/brazil_b2b_leads.db")
    print("=" * 90)


if __name__ == "__main__":
    main()