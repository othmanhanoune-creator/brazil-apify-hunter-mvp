from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# INPUT / OUTPUT PATHS
# ============================================================

INPUT_PATH = Path("data/lake/gold/qualified_b2b_leads/brazil_gold_strong_b2b.csv")

OUTPUT_DIR = Path("data/lake/gold/enriched_contacts")
OUTPUT_PATH = OUTPUT_DIR / "brazil_gold_strong_b2b_email_enriched.csv"
FIXED_OUTPUT_PATH = OUTPUT_DIR / "brazil_gold_strong_b2b_email_enriched_fixed.csv"

REPORT_DIR = Path("docs")
REPORT_PATH = REPORT_DIR / "email_enrichment_report.md"


# ============================================================
# SETTINGS
# ============================================================

REQUEST_TIMEOUT = 12
SLEEP_SECONDS = 1.0
MAX_CONTACT_LINKS = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

CONTACT_PATHS = [
    "",
    "/",
    "/contato",
    "/contact",
    "/fale-conosco",
    "/faleconosco",
    "/atendimento",
    "/sac",
    "/vendas",
    "/comercial",
    "/orcamento",
    "/orçamento",
    "/quem-somos",
    "/sobre",
    "/sobre-nos",
    "/empresa",
    "/lojas",
]

GOOD_EMAIL_KEYWORDS = [
    "vendas",
    "comercial",
    "contato",
    "contact",
    "sales",
    "export",
    "atendimento",
    "sac",
    "info",
    "administrativo",
]

BAD_EMAIL_KEYWORDS = [
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "example",
    "teste",
    "test",
    "privacy",
    "abuse",
    "postmaster",
    "mailer-daemon",
]

FREE_EMAIL_DOMAINS = [
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "live.com",
    "bol.com.br",
    "uol.com.br",
    "terra.com.br",
]

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    flags=re.IGNORECASE,
)

ENRICHMENT_COLUMNS = [
    "email",
    "email_status",
    "email_source",
    "email_confidence",
    "emails_found_all",
    "contact_form_url",
    "email_pages_checked",
    "email_enriched_at",
    "enrichment_error",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_text(value: Any) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def ensure_output_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_website(value: Any) -> str:
    website = safe_text(value)

    if not website:
        return ""

    if website.startswith("www."):
        website = "https://" + website

    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    return website.rstrip("/")


def get_domain(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def get_base_url(url: str) -> str:
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}"


def deobfuscate_text(text: str) -> str:
    replacements = {
        " [at] ": "@",
        " (at) ": "@",
        " at ": "@",
        " arroba ": "@",
        " [dot] ": ".",
        " (dot) ": ".",
        " dot ": ".",
        " ponto ": ".",
    }

    text = f" {text} "

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.strip()


def clean_email(email: str) -> str:
    email = email.strip().lower()
    email = email.strip(".,;:()[]{}<>\"'")
    return email


def is_probably_valid_email(email: str) -> bool:
    email = clean_email(email)

    if not EMAIL_REGEX.fullmatch(email):
        return False

    local_part, domain = email.split("@", 1)

    if len(local_part) < 2:
        return False

    if any(bad in email for bad in BAD_EMAIL_KEYWORDS):
        return False

    if email.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
        return False

    if domain in ["example.com", "domain.com", "email.com"]:
        return False

    return True


# ============================================================
# SCRAPING HELPERS
# ============================================================

def fetch_html(url: str) -> tuple[str, str]:
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        status_code = response.status_code

        if status_code in [401, 403, 429]:
            return "", f"blocked_or_forbidden_http_{status_code}"

        if status_code >= 400:
            return "", f"http_error_{status_code}"

        content_type = response.headers.get("content-type", "").lower()

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return "", f"not_html_content_type_{content_type[:40]}"

        return response.text, ""

    except requests.exceptions.Timeout:
        return "", "timeout"

    except requests.exceptions.SSLError:
        return "", "ssl_error"

    except requests.exceptions.ConnectionError:
        return "", "connection_error"

    except Exception as exc:
        return "", f"fetch_error_{type(exc).__name__}"


def extract_emails_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")

    emails = set()

    for tag in soup.find_all("a", href=True):
        href = safe_text(tag.get("href"))

        if href.lower().startswith("mailto:"):
            raw_email = href.split("mailto:", 1)[1].split("?", 1)[0]
            raw_email = clean_email(raw_email)

            if is_probably_valid_email(raw_email):
                emails.add(raw_email)

    text = soup.get_text(" ", strip=True)
    text = deobfuscate_text(text)

    for match in EMAIL_REGEX.findall(text):
        email = clean_email(match)

        if is_probably_valid_email(email):
            emails.add(email)

    html_text = deobfuscate_text(html)

    for match in EMAIL_REGEX.findall(html_text):
        email = clean_email(match)

        if is_probably_valid_email(email):
            emails.add(email)

    return sorted(emails)


def extract_contact_links(html: str, page_url: str, base_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")

    contact_links = []

    contact_terms = [
        "contato",
        "contact",
        "fale",
        "atendimento",
        "sac",
        "vendas",
        "comercial",
        "orcamento",
        "orçamento",
        "sobre",
        "empresa",
        "quem-somos",
    ]

    for tag in soup.find_all("a", href=True):
        href = safe_text(tag.get("href"))
        link_text = safe_text(tag.get_text(" ", strip=True)).lower()
        href_lower = href.lower()

        combined = f"{href_lower} {link_text}"

        if not any(term in combined for term in contact_terms):
            continue

        full_url = urljoin(page_url, href)
        link_domain = get_domain(full_url)

        if link_domain and base_domain and link_domain != base_domain:
            continue

        clean_url = full_url.split("#", 1)[0].rstrip("/")

        if clean_url not in contact_links:
            contact_links.append(clean_url)

    return contact_links[:MAX_CONTACT_LINKS]


def detect_contact_form(html: str, page_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    forms = soup.find_all("form")

    if not forms:
        return ""

    return page_url


# ============================================================
# EMAIL SCORING
# ============================================================

def score_email(email: str, company_domain: str) -> int:
    email = clean_email(email)
    local_part, email_domain = email.split("@", 1)

    score = 0

    if company_domain and email_domain == company_domain:
        score += 60

    if any(keyword in local_part for keyword in GOOD_EMAIL_KEYWORDS):
        score += 40

    if email_domain in FREE_EMAIL_DOMAINS:
        score -= 15

    if any(keyword in email for keyword in BAD_EMAIL_KEYWORDS):
        score -= 100

    return score


def choose_best_email(emails: list[str], company_domain: str) -> tuple[str, str]:
    if not emails:
        return "", "none"

    scored = sorted(
        emails,
        key=lambda email: score_email(email, company_domain),
        reverse=True,
    )

    best = scored[0]
    best_score = score_email(best, company_domain)
    best_domain = best.split("@", 1)[1]

    if company_domain and best_domain == company_domain and best_score >= 90:
        confidence = "high"
    elif company_domain and best_domain == company_domain:
        confidence = "medium"
    elif best_domain in FREE_EMAIL_DOMAINS:
        confidence = "low"
    else:
        confidence = "medium"

    return best, confidence


# ============================================================
# DATAFRAME COMBINE / REPAIR HELPERS
# ============================================================

def combine_original_with_enrichment(
    df: pd.DataFrame,
    enrichment_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combines original Gold leads with enrichment results.

    Important:
    It removes old enrichment columns first, so we do not create duplicate
    columns like email and email.1.
    """

    df_clean = df.drop(
        columns=[col for col in ENRICHMENT_COLUMNS if col in df.columns],
        errors="ignore",
    )

    final_df = pd.concat(
        [
            df_clean.reset_index(drop=True),
            enrichment_df.reset_index(drop=True),
        ],
        axis=1,
    )

    return final_df


def is_empty(value: Any) -> bool:
    if pd.isna(value):
        return True

    text = str(value).strip().lower()

    return text in ["", "nan", "none", "null"]


def duplicate_columns_for(df: pd.DataFrame, base_col: str) -> list[str]:
    return [
        col for col in df.columns
        if col == base_col or col.startswith(base_col + ".")
    ]


def choose_rightmost_non_empty(row: pd.Series, cols: list[str]) -> Any:
    for col in reversed(cols):
        value = row.get(col)

        if not is_empty(value):
            return value

    return ""


def repair_existing_output() -> None:
    """
    Fixes existing enriched CSV without scraping again.

    It repairs duplicate columns such as:
    email / email.1
    email_status / email_status.1
    """

    ensure_output_dirs()

    if not OUTPUT_PATH.exists():
        raise FileNotFoundError(f"Existing enriched file not found: {OUTPUT_PATH}")

    df = pd.read_csv(OUTPUT_PATH, encoding="utf-8-sig")

    print("=" * 80)
    print("REPAIRING EXISTING EMAIL ENRICHMENT OUTPUT")
    print("=" * 80)
    print(f"Input: {OUTPUT_PATH}")
    print(f"Original shape: {df.shape}")
    print("Columns:")
    print(df.columns.tolist())
    print("=" * 80)

    columns_to_drop = []

    for base_col in ENRICHMENT_COLUMNS:
        duplicate_cols = duplicate_columns_for(df, base_col)

        if not duplicate_cols:
            continue

        print(f"{base_col}: {duplicate_cols}")

        df[base_col] = df.apply(
            lambda row: choose_rightmost_non_empty(row, duplicate_cols),
            axis=1,
        )

        for col in duplicate_cols:
            if col != base_col:
                columns_to_drop.append(col)

    if columns_to_drop:
        df = df.drop(columns=columns_to_drop, errors="ignore")

    df.to_csv(FIXED_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print("=" * 80)
    print("REPAIR COMPLETE")
    print("=" * 80)
    print(f"Fixed output: {FIXED_OUTPUT_PATH}")
    print(f"Fixed shape: {df.shape}")

    if "email_status" in df.columns:
        print("")
        print(df["email_status"].value_counts(dropna=False).to_string())

    if "email" in df.columns:
        print("")
        preview_cols = ["name", "website", "email", "email_status", "email_confidence"]
        preview_cols = [col for col in preview_cols if col in df.columns]
        print(df[preview_cols].head(25).to_string(index=False))


def test_combine_only() -> None:
    """
    Tests the dataframe fix only.
    No websites are scraped.
    """

    df = pd.DataFrame(
        {
            "name": ["Test Company"],
            "website": ["https://test.com"],
            "email": [""],
        }
    )

    enrichment_df = pd.DataFrame(
        {
            "email": ["sales@test.com"],
            "email_status": ["found"],
            "email_source": ["website_scraper"],
            "email_confidence": ["high"],
            "emails_found_all": ["sales@test.com"],
            "contact_form_url": [""],
            "email_pages_checked": ["https://test.com"],
            "email_enriched_at": ["2026-06-04 10:00:00"],
            "enrichment_error": [""],
        }
    )

    final_df = combine_original_with_enrichment(df, enrichment_df)

    print("=" * 80)
    print("TEST COMBINE ONLY")
    print("=" * 80)
    print(final_df.columns.tolist())
    print(final_df.to_string(index=False))
    print("=" * 80)

    if "email.1" in final_df.columns:
        raise AssertionError("Test failed: duplicate email.1 column exists.")

    if final_df.loc[0, "email"] != "sales@test.com":
        raise AssertionError("Test failed: enriched email was not preserved.")

    print("TEST PASSED: no duplicate email column, enriched email preserved.")


# ============================================================
# MAIN ENRICHMENT LOGIC
# ============================================================

def get_website_column(df: pd.DataFrame) -> str:
    possible_cols = ["website", "site", "url", "company_website"]

    for col in possible_cols:
        if col in df.columns:
            return col

    raise ValueError(
        "No website column found. Expected one of: website, site, url, company_website"
    )


def enrich_one_lead(row: pd.Series, website_col: str) -> dict:
    website = normalize_website(row.get(website_col, ""))

    if not website:
        return {
            "email": "",
            "email_status": "no_website",
            "email_source": "website_scraper",
            "email_confidence": "none",
            "emails_found_all": "",
            "contact_form_url": "",
            "email_pages_checked": "",
            "email_enriched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "enrichment_error": "no website available",
        }

    base_url = get_base_url(website)
    domain = get_domain(website)

    urls_to_check = []

    for path in CONTACT_PATHS:
        candidate_url = urljoin(base_url, path).rstrip("/")

        if candidate_url not in urls_to_check:
            urls_to_check.append(candidate_url)

    all_emails = set()
    pages_checked = []
    errors = []
    contact_form_url = ""

    for url in urls_to_check:
        html, error = fetch_html(url)
        pages_checked.append(url)

        if error:
            errors.append(f"{url}: {error}")
            continue

        found = extract_emails_from_html(html)
        all_emails.update(found)

        if not contact_form_url:
            detected_form = detect_contact_form(html, url)
            if detected_form:
                contact_form_url = detected_form

        discovered_links = extract_contact_links(html, url, domain)

        for link in discovered_links:
            if link not in urls_to_check:
                urls_to_check.append(link)

        if len(all_emails) >= 3:
            break

        time.sleep(SLEEP_SECONDS)

    all_emails_list = sorted(all_emails)
    best_email, confidence = choose_best_email(all_emails_list, domain)

    if best_email:
        status = "found"
        error_summary = ""
    elif contact_form_url:
        status = "contact_form_only"
        error_summary = "; ".join(errors[:3])
    else:
        blocked_errors = [err for err in errors if "blocked" in err or "forbidden" in err]
        timeout_errors = [err for err in errors if "timeout" in err]

        if blocked_errors:
            status = "blocked_or_forbidden"
        elif timeout_errors:
            status = "timeout_or_unreachable"
        else:
            status = "not_found"

        error_summary = "; ".join(errors[:3])

    return {
        "email": best_email,
        "email_status": status,
        "email_source": "website_scraper",
        "email_confidence": confidence,
        "emails_found_all": "; ".join(all_emails_list),
        "contact_form_url": contact_form_url,
        "email_pages_checked": "; ".join(pages_checked[:10]),
        "email_enriched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "enrichment_error": error_summary,
    }


def write_report(df: pd.DataFrame) -> None:
    total = len(df)
    found = int((df["email_status"] == "found").sum())
    contact_form_only = int((df["email_status"] == "contact_form_only").sum())
    no_website = int((df["email_status"] == "no_website").sum())
    blocked = int((df["email_status"] == "blocked_or_forbidden").sum())
    timeout = int((df["email_status"] == "timeout_or_unreachable").sum())
    not_found = int((df["email_status"] == "not_found").sum())

    report = f"""# Email Enrichment Report

Generated at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

| Metric | Count |
|---|---:|
| Total leads | {total} |
| Emails found | {found} |
| Contact form only | {contact_form_only} |
| No website | {no_website} |
| Blocked / forbidden | {blocked} |
| Timeout / unreachable | {timeout} |
| Not found | {not_found} |

## Output

Enriched file:

`{OUTPUT_PATH}`

## Next Step

Use Hunter only for rows where:

`email_status != found`

and where website/domain exists.
"""

    REPORT_PATH.write_text(report, encoding="utf-8")


def run_scraper() -> None:
    ensure_output_dirs()

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}\n"
            "Make sure your Strong Gold file exists before running enrichment."
        )

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    website_col = get_website_column(df)

    print("=" * 80)
    print("EMAIL ENRICHMENT STARTED")
    print("=" * 80)
    print(f"Input file: {INPUT_PATH}")
    print(f"Rows: {len(df)}")
    print(f"Website column: {website_col}")
    print("=" * 80)

    enriched_rows = []

    for idx, row in df.iterrows():
        company_name = safe_text(row.get("name", row.get("company_name", "")))
        website = safe_text(row.get(website_col, ""))

        print(f"[{idx + 1}/{len(df)}] {company_name} | {website}")

        enrichment = enrich_one_lead(row, website_col)
        enriched_rows.append(enrichment)

        print(
            f"    status={enrichment['email_status']} | "
            f"email={enrichment['email'] or '-'}"
        )

    enrichment_df = pd.DataFrame(enriched_rows)
    final_df = combine_original_with_enrichment(df, enrichment_df)

    final_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    write_report(final_df)

    print("=" * 80)
    print("EMAIL ENRICHMENT FINISHED")
    print("=" * 80)
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Report file: {REPORT_PATH}")
    print(final_df["email_status"].value_counts(dropna=False).to_string())
    print("=" * 80)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Email enrichment for Brazil Strong Gold B2B leads."
    )

    parser.add_argument(
        "--test-combine",
        action="store_true",
        help="Test dataframe combine logic only. Does not scrape websites.",
    )

    parser.add_argument(
        "--repair-existing",
        action="store_true",
        help="Repair existing enriched CSV duplicate columns. Does not scrape websites.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.test_combine:
        test_combine_only()
        return

    if args.repair_existing:
        repair_existing_output()
        return

    run_scraper()


if __name__ == "__main__":
    main()