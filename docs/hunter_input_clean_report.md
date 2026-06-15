# Clean Hunter Input Report

## Summary

| Metric | Count |
|---|---:|
| Original Hunter input rows | 28 |
| Excluded platform/listing domains | 1 |
| Rows before domain deduplication | 27 |
| Final clean Hunter rows | 27 |

## Output

`data\lake\gold\enriched_contacts\brazil_hunter_missing_email_input_clean.csv`

## Excluded Domains

| name                                        | website                                                        | hunter_domain_clean   |
|:--------------------------------------------|:---------------------------------------------------------------|:----------------------|
| LIZ DISTRIBUIDORA Piso vinílico e laminado. | https://mechameaqui.com.br/v2/liz-distribuidora-hortolandia-sp | mechameaqui.com.br    |

## Notes

This clean file should be used for Hunter or another paid domain-email API.
Do not send the original unclean file to paid enrichment.
