# Brazil Apify + Hunter MVP Pipeline Guide

## Scope

This MVP keeps only the Brazil pipeline:

```text
Apify CSV -> Bronze raw data -> Silver cleaned/deduplicated leads -> B2B scoring -> Gold qualified leads -> Hunter enrichment -> warehouse/dashboard/export
```

## Required input

Put the Brazil Apify Google Maps CSV here:

```text
data/lake/bronze/apify_google_maps/brazil_apify_raw.csv
```

## One-command run

```powershell
python run_apify_hunter_pipeline.py
```

## Manual step-by-step run

```powershell
python src\extractors\apify_google_maps_csv.py
python src\transformers\split_brazil_gold.py
python src\enrichment\email_enrich_strong_gold.py --limit 0
python src\enrichment\build_hunter_input.py
python src\enrichment\clean_hunter_input.py
python src\enrichment\hunter_enrich_missing_emails.py --input "data\lake\gold\enriched_contacts\brazil_hunter_missing_email_input_clean.csv"
python src\enrichment\finalize_hunter_enrichment.py
```

## Main outputs

```text
data/lake/silver/leads_cleaned/brazil_silver_leads.csv
data/lake/gold/qualified_b2b_leads/brazil_gold_strong_b2b.csv
data/lake/gold/qualified_b2b_leads/brazil_gold_review_queue.csv
data/lake/gold/enriched_contacts/brazil_gold_strong_b2b_email_enriched.csv
data/lake/gold/enriched_contacts/brazil_hunter_api_results_all.csv
data/lake/gold/enriched_contacts/brazil_sales_ready_enriched_leads.csv
data/warehouse/brazil_b2b_leads.db
```

## Hunter API key

Set the key in your shell before Hunter enrichment:

```powershell
$env:HUNTER_API_KEY="your_hunter_api_key"
```

## Supabase upload

```powershell
python src\supabase_client\upload_leads_to_supabase.py --input "data\lake\gold\enriched_contacts\brazil_sales_ready_enriched_leads.csv" --market Brazil --mode upsert
```
