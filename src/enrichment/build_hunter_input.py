from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


INPUT_PATH = Path("data/lake/gold/enriched_contacts/brazil_gold_strong_b2b_email_enriched.csv")

OUTPUT_DIR = Path("data/lake/gold/enriched_contacts")
OUTPUT_PATH = OUTPUT_DIR / "brazil_hunter_missing_email_input.csv"

REPORT_PATH = Path("docs/hunter_input_report.md")


EXCLUDED_DOMAINS = [
    "instagram.com",
    "facebook.com",
    "fb.com",
    "wa.me",
    "whatsapp.com",
    "shopee.com.br",
    "mercadolivre.com.br",
    "bento.me",
    "linktr.ee",
    "negocio.site",
    "business.site",
    "lovable.app",
    "wixsite.com",
    "google.com",
    "maps.google.com",
]


EXCLUDED_DOMAIN_KEYWORDS = [
    "instagram",
    "facebook",
    "whatsapp",
    "shopee",
    "mercadolivre",
    "linktree",
    "bento",
    "negocio.site",
    "lovable",
    "wixsite",
]


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


def extract_domain(website: str) -> str:
    website = normalize_website(website)

    if not website:
        return ""

    parsed = urlparse(website)

    domain = parsed.netloc.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def is_excluded_domain(domain: str) -> bool:
    domain = safe_text(domain).lower()

    if not domain:
        return True

    for excluded in EXCLUDED_DOMAINS:
        if domain == excluded or domain.endswith("." + excluded):
            return True

    for keyword in EXCLUDED_DOMAIN_KEYWORDS:
        if keyword in domain:
            return True

    return False


def has_real_company_domain(domain: str) -> bool:
    domain = safe_text(domain).lower()

    if not domain:
        return False

    if "." not in domain:
        return False

    if is_excluded_domain(domain):
        return False

    return True


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    required_cols = ["name", "website", "email_status"]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if "email" not in df.columns:
        df["email"] = ""

    df["hunter_domain"] = df["website"].apply(extract_domain)

    missing_email_mask = (
        df["email"].fillna("").astype(str).str.strip().eq("")
        & df["email_status"].fillna("").astype(str).str.lower().ne("found")
    )

    real_domain_mask = df["hunter_domain"].apply(has_real_company_domain)

    hunter_df = df[missing_email_mask & real_domain_mask].copy()

    hunter_df["hunter_input_reason"] = (
        "missing_email_after_website_scraper_real_company_domain"
    )

    output_cols = [
        "name",
        "website",
        "hunter_domain",
        "city",
        "state",
        "country",
        "phone",
        "email",
        "email_status",
        "email_confidence",
        "contact_form_url",
        "b2b_score",
        "gold_split_status",
        "gold_split_reason",
        "source_url",
        "hunter_input_reason",
    ]

    output_cols = [col for col in output_cols if col in hunter_df.columns]

    hunter_df = hunter_df[output_cols].copy()

    hunter_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    total = len(df)
    missing_email = int(missing_email_mask.sum())
    real_domains = int(real_domain_mask.sum())
    hunter_eligible = len(hunter_df)

    excluded_missing = df[missing_email_mask & ~real_domain_mask].copy()

    report = f"""# Hunter Input Report

## Summary

| Metric | Count |
|---|---:|
| Total enriched strong Gold leads | {total} |
| Missing emails after website scraper | {missing_email} |
| Rows with real company domains | {real_domains} |
| Hunter-eligible missing-email rows | {hunter_eligible} |
| Missing-email rows excluded from Hunter | {len(excluded_missing)} |

## Output File

`{OUTPUT_PATH}`

## Logic

Hunter input includes only rows where:

- email is empty
- email_status is not found
- website has a real company domain
- website is not Instagram, Facebook, WhatsApp, Shopee, Bento, Wixsite, Lovable, or similar platform domain

## Next Step

Use this file for Hunter domain search or any paid fallback enrichment API.
"""

    REPORT_PATH.write_text(report, encoding="utf-8")

    print("=" * 80)
    print("HUNTER INPUT CREATED")
    print("=" * 80)
    print(f"Input file: {INPUT_PATH}")
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Report file: {REPORT_PATH}")
    print("")
    print(f"Total rows: {total}")
    print(f"Missing email rows: {missing_email}")
    print(f"Hunter eligible rows: {hunter_eligible}")
    print(f"Excluded missing-email rows: {len(excluded_missing)}")
    print("=" * 80)

    if hunter_eligible > 0:
        print("")
        print("Preview:")
        print(hunter_df.head(25).to_string(index=False))


if __name__ == "__main__":
    main()