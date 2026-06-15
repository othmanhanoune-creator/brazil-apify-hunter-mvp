# Brazil B2B Flooring Lead Intelligence MVP

Clean MVP for transforming **Brazil Apify Google Maps CSV exports** into cleaned, scored, Gold qualified flooring leads, enriching missing emails with website scraping + Hunter API, and presenting/exporting leads through Streamlit/Supabase.

## MVP scope

```text
Apify CSV
  -> Bronze raw data
  -> Silver cleaned and deduplicated leads
  -> B2B scoring
  -> Gold qualified leads
  -> Hunter email enrichment
  -> SQLite warehouse / Supabase upload
  -> dashboard / export
```

## Core files

```text
run_apify_hunter_pipeline.py
src/extractors/apify_google_maps_csv.py
src/transformers/split_brazil_gold.py
src/enrichment/email_enrich_strong_gold.py
src/enrichment/build_hunter_input.py
src/enrichment/clean_hunter_input.py
src/enrichment/hunter_enrich_missing_emails.py
src/enrichment/finalize_hunter_enrichment.py
src/supabase_client/upload_leads_to_supabase.py
src/supabase_client/lead_repository.py
streamlit_app.py
```

## Data lake structure

```text
data/lake/bronze/apify_google_maps/brazil_apify_raw.csv
data/lake/silver/leads_cleaned/brazil_silver_leads.csv
data/lake/gold/qualified_b2b_leads/brazil_gold_strong_b2b.csv
data/lake/gold/qualified_b2b_leads/brazil_gold_review_queue.csv
data/lake/gold/enriched_contacts/brazil_sales_ready_enriched_leads.csv
data/warehouse/brazil_b2b_leads.db
```

## Run the ETL

Put your Apify Google Maps Brazil CSV here:

```text
data/lake/bronze/apify_google_maps/brazil_apify_raw.csv
```

Run the full Brazil MVP pipeline:

```powershell
python run_apify_hunter_pipeline.py
```

## Hunter API

Set the Hunter key before running Hunter enrichment:

```powershell
$env:HUNTER_API_KEY="your_hunter_api_key"
```

## Upload final enriched leads to Supabase

```powershell
python src\supabase_client\upload_leads_to_supabase.py --input "data\lake\gold\enriched_contacts\brazil_sales_ready_enriched_leads.csv" --market Brazil --mode upsert
```

## Run the dashboard

```powershell
streamlit run streamlit_app.py
```

## Notes

This package intentionally excludes LocationIQ and old experimental scripts. It is focused only on the Brazil Apify + Hunter MVP pipeline.
