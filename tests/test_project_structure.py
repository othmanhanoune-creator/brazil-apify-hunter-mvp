from pathlib import Path


def test_required_files_exist():
    required = [
        "streamlit_app.py",
        "run_apify_hunter_pipeline.py",
        "src/extractors/apify_google_maps_csv.py",
        "src/transformers/split_brazil_gold.py",
        "src/enrichment/email_enrich_strong_gold.py",
        "src/enrichment/build_hunter_input.py",
        "src/enrichment/clean_hunter_input.py",
        "src/enrichment/hunter_enrich_missing_emails.py",
        "src/enrichment/finalize_hunter_enrichment.py",
        "src/supabase_client/lead_repository.py",
        "src/supabase_client/upload_leads_to_supabase.py",
        "docs/SUPABASE_SCHEMA.sql",
    ]

    for item in required:
        assert Path(item).exists(), f"Missing required file: {item}"
