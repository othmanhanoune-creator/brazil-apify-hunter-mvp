from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


ENRICHED_GOLD_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_gold_strong_b2b_email_enriched.csv"
)

HUNTER_TEST5_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_hunter_api_results_test5.csv"
)

HUNTER_REMAINING_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_hunter_api_results.csv"
)

HUNTER_ALL_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_hunter_api_results_all.csv"
)

FINAL_OUTPUT_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_gold_strong_b2b_email_enriched_final_all.csv"
)

REPORT_PATH = Path("docs/final_email_enrichment_report.md")


def safe_text(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def normalize_website(value) -> str:
    website = safe_text(value)

    if not website:
        return ""

    if website.startswith("www."):
        website = "https://" + website

    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    return website


def extract_domain_from_url(value) -> str:
    website = normalize_website(value)

    if not website:
        return ""

    parsed = urlparse(website)
    domain = parsed.netloc.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return normalize_domain(domain)


def normalize_domain(domain) -> str:
    domain = safe_text(domain).lower()

    if domain.startswith("www."):
        domain = domain[4:]

    for prefix in ["lp.", "landing.", "pages.", "page.", "site.", "web."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            break

    return domain


def confidence_label(value) -> str:
    try:
        score = int(float(value))
    except Exception:
        return "unknown"

    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    if score > 0:
        return "low"

    return "unknown"


def recovered_test5_results() -> pd.DataFrame:
    """
    Used only if brazil_hunter_api_results_test5.csv was not saved before
    the remaining Hunter run overwrote brazil_hunter_api_results.csv.
    """

    rows = [
        {
            "name": "Cristal Pisos Distribuidora",
            "hunter_domain_clean": "cristalpisos.com.br",
            "hunter_email": "",
            "hunter_status": "not_found",
            "hunter_confidence": "",
            "hunter_type": "",
            "hunter_error": "recovered_from_run_log",
        },
        {
            "name": "Eucapisos | Atacado e Distribuição de Pisos Vinílicos, Laminados e Carpetes em Curitiba",
            "hunter_domain_clean": "eucapisos.com.br",
            "hunter_email": "eucapisos@eucapisos.com.br",
            "hunter_status": "found",
            "hunter_confidence": 78,
            "hunter_type": "generic",
            "hunter_error": "recovered_from_run_log",
        },
        {
            "name": "Galpão Revestimentos",
            "hunter_domain_clean": "galpaorevestimentos.com.br",
            "hunter_email": "vendas@galpaorevestimentos.com.br",
            "hunter_status": "found",
            "hunter_confidence": 75,
            "hunter_type": "generic",
            "hunter_error": "recovered_from_run_log",
        },
        {
            "name": "Imperial Revestimentos",
            "hunter_domain_clean": "imperialrevestimentos.com.br",
            "hunter_email": "",
            "hunter_status": "not_found",
            "hunter_confidence": "",
            "hunter_type": "",
            "hunter_error": "recovered_from_run_log",
        },
        {
            "name": "Importadora Luanjo",
            "hunter_domain_clean": "importadoraluanjo.com.br",
            "hunter_email": "",
            "hunter_status": "not_found",
            "hunter_confidence": "",
            "hunter_type": "",
            "hunter_error": "recovered_from_run_log",
        },
    ]

    return pd.DataFrame(rows)


def load_hunter_results() -> pd.DataFrame:
    """
    Load Hunter results without calling Hunter again.

    Preferred:
    - brazil_hunter_api_results_all.csv

    Fallback:
    - combine brazil_hunter_api_results_test5.csv
      and brazil_hunter_api_results.csv if they still exist.
    """

    if HUNTER_ALL_PATH.exists():
        all_results = pd.read_csv(HUNTER_ALL_PATH, encoding="utf-8-sig")
        source = "loaded_from_all_results_file"

    else:
        if not HUNTER_REMAINING_PATH.exists():
            raise FileNotFoundError(
                "No Hunter result file found.\n"
                f"Expected either:\n"
                f"1. {HUNTER_ALL_PATH}\n"
                f"or\n"
                f"2. {HUNTER_REMAINING_PATH}"
            )

        remaining = pd.read_csv(HUNTER_REMAINING_PATH, encoding="utf-8-sig")

        if HUNTER_TEST5_PATH.exists():
            test5 = pd.read_csv(HUNTER_TEST5_PATH, encoding="utf-8-sig")
            test5_source = "loaded_from_file"
        else:
            test5 = recovered_test5_results()
            test5_source = "recovered_from_run_log"
            test5.to_csv(HUNTER_TEST5_PATH, index=False, encoding="utf-8-sig")

        all_results = pd.concat([test5, remaining], ignore_index=True)
        source = f"combined_test5_and_remaining; test5_source={test5_source}"

    if "hunter_domain_clean" not in all_results.columns:
        raise ValueError("Hunter results must contain hunter_domain_clean")

    all_results["hunter_domain_clean"] = (
        all_results["hunter_domain_clean"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )

    all_results = all_results[
        all_results["hunter_domain_clean"].ne("")
    ].copy()

    all_results = all_results.drop_duplicates(
        subset=["hunter_domain_clean"],
        keep="last",
    ).copy()

    all_results.to_csv(HUNTER_ALL_PATH, index=False, encoding="utf-8-sig")

    print(f"Hunter results source: {source}")

    return all_results


def build_gold_domain(row: pd.Series) -> str:
    if safe_text(row.get("hunter_domain_clean")):
        return normalize_domain(row.get("hunter_domain_clean"))

    if safe_text(row.get("domain")):
        return normalize_domain(row.get("domain"))

    if safe_text(row.get("website")):
        return extract_domain_from_url(row.get("website"))

    return ""


def main() -> None:
    if not ENRICHED_GOLD_PATH.exists():
        raise FileNotFoundError(f"Missing enriched Gold file: {ENRICHED_GOLD_PATH}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINAL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    gold = pd.read_csv(ENRICHED_GOLD_PATH, encoding="utf-8-sig")
    hunter = load_hunter_results()

    gold["hunter_domain_clean"] = gold.apply(build_gold_domain, axis=1)

    hunter_cols = [
        "hunter_domain_clean",
        "hunter_email",
        "hunter_status",
        "hunter_confidence",
        "hunter_type",
        "hunter_error",
    ]

    for col in hunter_cols:
        if col not in hunter.columns:
            hunter[col] = ""

    hunter_small = hunter[hunter_cols].copy()

    final = gold.merge(
        hunter_small,
        on="hunter_domain_clean",
        how="left",
    )

    for col in ["email", "email_status", "email_source", "email_confidence"]:
        if col not in final.columns:
            final[col] = ""

    fill_mask = (
        final["email"].fillna("").astype(str).str.strip().eq("")
        & final["hunter_email"].fillna("").astype(str).str.strip().ne("")
        & final["hunter_status"].fillna("").astype(str).eq("found")
    )

    final.loc[fill_mask, "email"] = final.loc[fill_mask, "hunter_email"]
    final.loc[fill_mask, "email_status"] = "found"
    final.loc[fill_mask, "email_source"] = "hunter_domain_search"
    final.loc[fill_mask, "email_confidence"] = final.loc[
        fill_mask, "hunter_confidence"
    ].apply(confidence_label)

    final.to_csv(FINAL_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    total = len(final)
    final_emails = int(final["email"].fillna("").astype(str).str.strip().ne("").sum())
    website_scraper_emails = int(
        final["email_source"].fillna("").astype(str).eq("website_scraper").sum()
    )
    hunter_emails = int(
        final["email_source"].fillna("").astype(str).eq("hunter_domain_search").sum()
    )

    hunter_found = int(
        hunter["hunter_status"].fillna("").astype(str).eq("found").sum()
    )

    report = f"""# Final Email Enrichment Report

## Summary

| Metric | Count |
|---|---:|
| Total Strong Gold leads | {total} |
| Final leads with email | {final_emails} |
| Website scraper emails | {website_scraper_emails} |
| Hunter emails added | {hunter_emails} |
| Hunter domains found | {hunter_found} |

## Files

All Hunter results:

`{HUNTER_ALL_PATH}`

Final enriched Gold file:

`{FINAL_OUTPUT_PATH}`

## Next Step

Use the final enriched Gold file for Supabase upload.
"""

    REPORT_PATH.write_text(report, encoding="utf-8")

    print("=" * 80)
    print("FINAL EMAIL ENRICHMENT COMPLETE")
    print("=" * 80)
    print(f"All Hunter results: {HUNTER_ALL_PATH}")
    print(f"Final output: {FINAL_OUTPUT_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("")
    print(f"Total Strong Gold leads: {total}")
    print(f"Final leads with email: {final_emails}")
    print(f"Website scraper emails: {website_scraper_emails}")
    print(f"Hunter emails added: {hunter_emails}")
    print(f"Hunter domains found: {hunter_found}")
    print("=" * 80)

    preview_cols = [
        "name",
        "website",
        "email",
        "email_source",
        "email_status",
        "email_confidence",
    ]

    preview_cols = [col for col in preview_cols if col in final.columns]

    print("")
    print(final[preview_cols].head(60).to_string(index=False))


if __name__ == "__main__":
    main()