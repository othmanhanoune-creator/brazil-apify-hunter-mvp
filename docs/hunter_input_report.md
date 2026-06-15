# Hunter Input Report

## Summary

| Metric | Count |
|---|---:|
| Total enriched strong Gold leads | 54 |
| Missing emails after website scraper | 37 |
| Rows with real company domains | 45 |
| Hunter-eligible missing-email rows | 28 |
| Missing-email rows excluded from Hunter | 9 |

## Output File

`data\lake\gold\enriched_contacts\brazil_hunter_missing_email_input.csv`

## Logic

Hunter input includes only rows where:

- email is empty
- email_status is not found
- website has a real company domain
- website is not Instagram, Facebook, WhatsApp, Shopee, Bento, Wixsite, Lovable, or similar platform domain

## Next Step

Use this file for Hunter domain search or any paid fallback enrichment API.
