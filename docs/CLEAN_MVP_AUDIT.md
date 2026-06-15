# Brazil MVP Cleanup Audit

## Kept

- Brazil Apify CSV ingestion
- Bronze/Silver/Gold folder structure
- Silver cleaning and deduplication
- B2B scoring rules for flooring/distributor/wholesale signals
- Gold strong/review split
- Website email enrichment
- Hunter API enrichment
- Final sales-ready enriched leads output
- SQLite warehouse output
- Streamlit dashboard/portal
- Supabase upload/repository layer for the current app workflow
- Brazil manual MVP output files already provided in the package

## Removed

- LocationIQ extractors
- Brazil LocationIQ backup scripts
- LocationIQ lookup enrichment
- Old raw/cache/noise files
- USA manual files
- Old backup apps
- Virtual environments
- Python cache files
- Test/cache artifacts

## Final MVP flow

```text
Brazil Apify CSV
  -> Bronze raw file
  -> Silver cleaned/deduplicated leads
  -> B2B scoring
  -> Gold strong/review tables
  -> Website + Hunter email enrichment
  -> Final sales-ready enriched leads
  -> SQLite/Supabase/dashboard/export
```
