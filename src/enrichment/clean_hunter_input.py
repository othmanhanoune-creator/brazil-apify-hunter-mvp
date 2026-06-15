from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


INPUT_PATH = Path("data/lake/gold/enriched_contacts/brazil_hunter_missing_email_input.csv")
OUTPUT_PATH = Path("data/lake/gold/enriched_contacts/brazil_hunter_missing_email_input_clean.csv")
REPORT_PATH = Path("docs/hunter_input_clean_report.md")


EXCLUDED_DOMAINS = {
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
    "mechameaqui.com.br",
    "google.com",
    "maps.google.com",
}


def safe_text(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def extract_domain_from_url(value: str) -> str:
    text = safe_text(value)

    if not text:
        return ""

    if not text.startswith(("http://", "https://")):
        text = "https://" + text

    parsed = urlparse(text)
    domain = parsed.netloc.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def normalize_domain(domain: str) -> str:
    """
    Converts obvious landing-page subdomains to the root domain.

    Example:
    lp.imperialrevestimentos.com.br
    becomes:
    imperialrevestimentos.com.br
    """

    domain = safe_text(domain).lower()

    if domain.startswith("www."):
        domain = domain[4:]

    removable_prefixes = [
        "lp.",
        "landing.",
        "pages.",
        "page.",
        "site.",
        "web.",
    ]

    for prefix in removable_prefixes:
        if domain.startswith(prefix):
            return domain[len(prefix):]

    return domain


def is_excluded_domain(domain: str) -> bool:
    domain = safe_text(domain).lower()

    if not domain:
        return True

    if domain in EXCLUDED_DOMAINS:
        return True

    for excluded in EXCLUDED_DOMAINS:
        if domain.endswith("." + excluded):
            return True

    return False


def domain_quality_score(row: pd.Series) -> int:
    """
    Higher score means this row is better to keep when duplicate domains exist.
    """

    score = 0

    if safe_text(row.get("phone")):
        score += 10

    if safe_text(row.get("website")):
        score += 10

    if safe_text(row.get("contact_form_url")):
        score += 5

    email_status = safe_text(row.get("email_status")).lower()

    if email_status == "contact_form_only":
        score += 8
    elif email_status == "blocked_or_forbidden":
        score += 6
    elif email_status == "timeout_or_unreachable":
        score += 4
    elif email_status == "not_found":
        score += 2

    try:
        score += int(float(row.get("b2b_score", 0)))
    except Exception:
        pass

    return score


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    if "hunter_domain" not in df.columns:
        if "website" not in df.columns:
            raise ValueError("Input must contain hunter_domain or website column.")
        df["hunter_domain"] = df["website"].apply(extract_domain_from_url)

    df["hunter_domain_raw"] = df["hunter_domain"].fillna("").astype(str)
    df["hunter_domain_clean"] = df["hunter_domain_raw"].apply(normalize_domain)

    before_rows = len(df)

    df["is_excluded_domain"] = df["hunter_domain_clean"].apply(is_excluded_domain)

    excluded_df = df[df["is_excluded_domain"]].copy()
    clean_df = df[~df["is_excluded_domain"]].copy()

    clean_df["domain_quality_score"] = clean_df.apply(domain_quality_score, axis=1)

    clean_df = clean_df.sort_values(
        by=["hunter_domain_clean", "domain_quality_score"],
        ascending=[True, False],
    )

    before_dedup = len(clean_df)

    clean_df = clean_df.drop_duplicates(
        subset=["hunter_domain_clean"],
        keep="first",
    ).copy()

    output_cols = [
        "name",
        "website",
        "hunter_domain_raw",
        "hunter_domain_clean",
        "city",
        "state",
        "country",
        "phone",
        "email_status",
        "email_confidence",
        "contact_form_url",
        "b2b_score",
        "gold_split_status",
        "gold_split_reason",
        "source_url",
        "hunter_input_reason",
        "domain_quality_score",
    ]

    output_cols = [col for col in output_cols if col in clean_df.columns]

    clean_df[output_cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    report = f"""# Clean Hunter Input Report

## Summary

| Metric | Count |
|---|---:|
| Original Hunter input rows | {before_rows} |
| Excluded platform/listing domains | {len(excluded_df)} |
| Rows before domain deduplication | {before_dedup} |
| Final clean Hunter rows | {len(clean_df)} |

## Output

`{OUTPUT_PATH}`

## Excluded Domains

{excluded_df[["name", "website", "hunter_domain_clean"]].to_markdown(index=False) if not excluded_df.empty else "None"}

## Notes

This clean file should be used for Hunter or another paid domain-email API.
Do not send the original unclean file to paid enrichment.
"""

    REPORT_PATH.write_text(report, encoding="utf-8")

    print("=" * 80)
    print("CLEAN HUNTER INPUT CREATED")
    print("=" * 80)
    print(f"Input: {INPUT_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("")
    print(f"Original rows: {before_rows}")
    print(f"Excluded platform/listing domains: {len(excluded_df)}")
    print(f"Before deduplication: {before_dedup}")
    print(f"Final clean Hunter rows: {len(clean_df)}")
    print("=" * 80)

    if len(clean_df) > 0:
        print("")
        print("Preview:")
        print(clean_df[output_cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()