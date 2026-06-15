from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests


# ============================================================
# PATHS
# ============================================================

DEFAULT_HUNTER_INPUT_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_hunter_missing_email_input_clean.csv"
)

ENRICHED_GOLD_PATH = Path(
    "data/lake/gold/enriched_contacts/brazil_gold_strong_b2b_email_enriched.csv"
)

OUTPUT_DIR = Path("data/lake/gold/enriched_contacts")

HUNTER_RESULTS_PATH = OUTPUT_DIR / "brazil_hunter_api_results.csv"

FINAL_ENRICHED_OUTPUT_PATH = (
    OUTPUT_DIR / "brazil_gold_strong_b2b_email_enriched_final.csv"
)

REPORT_PATH = Path("docs/hunter_api_enrichment_report.md")


# ============================================================
# SETTINGS
# ============================================================

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"

REQUEST_TIMEOUT = 20
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_MIN_CONFIDENCE = 50

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
    "orcamento",
    "orçamento",
]

BAD_EMAIL_KEYWORDS = [
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "abuse",
    "postmaster",
    "mailer-daemon",
    "privacy",
    "test",
    "teste",
    "example",
]

REQUIRED_HUNTER_RESULT_COLUMNS = [
    "hunter_domain_clean",
    "hunter_email",
    "hunter_confidence",
    "hunter_type",
    "hunter_position",
    "hunter_source_count",
    "hunter_status",
    "hunter_raw_emails",
    "hunter_error",
    "hunter_enriched_at",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_text(value: Any) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_api_key() -> str:
    api_key = os.getenv("HUNTER_API_KEY", "").strip()

    if not api_key or api_key == "your_key_here":
        raise ValueError(
            "Missing or invalid Hunter API key.\n\n"
            "Check it with:\n"
            "python -c \"import os; print('FOUND' if os.getenv('HUNTER_API_KEY') else 'NOT FOUND')\"\n\n"
            "Set it in the current PowerShell window with:\n"
            "$env:HUNTER_API_KEY=\"PASTE_YOUR_REAL_HUNTER_KEY_HERE\""
        )

    return api_key


def confidence_label(score: Any) -> str:
    try:
        score = int(score)
    except Exception:
        return "unknown"

    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    if score > 0:
        return "low"

    return "unknown"


def normalize_website(value: Any) -> str:
    website = safe_text(value)

    if not website:
        return ""

    if website.startswith("www."):
        website = "https://" + website

    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    return website


def extract_domain_from_url(value: Any) -> str:
    website = normalize_website(value)

    if not website:
        return ""

    parsed = urlparse(website)
    domain = parsed.netloc.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def normalize_domain(domain: Any) -> str:
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
            domain = domain[len(prefix):]
            break

    return domain


def build_hunter_domain_for_gold_row(row: pd.Series) -> str:
    if safe_text(row.get("hunter_domain_clean")):
        return normalize_domain(row.get("hunter_domain_clean"))

    if safe_text(row.get("domain")):
        return normalize_domain(row.get("domain"))

    if safe_text(row.get("website")):
        return normalize_domain(extract_domain_from_url(row.get("website")))

    return ""


# ============================================================
# HUNTER EMAIL SELECTION
# ============================================================

def score_hunter_email(email_record: dict, target_domain: str) -> int:
    email = safe_text(email_record.get("value")).lower()
    email_type = safe_text(email_record.get("type")).lower()

    try:
        confidence = int(email_record.get("confidence", 0))
    except Exception:
        confidence = 0

    score = confidence

    if "@" in email:
        local_part, email_domain = email.split("@", 1)
    else:
        local_part, email_domain = email, ""

    if email_domain == target_domain:
        score += 40

    if email_type == "generic":
        score += 30

    if any(keyword in local_part for keyword in GOOD_EMAIL_KEYWORDS):
        score += 35

    if any(keyword in email for keyword in BAD_EMAIL_KEYWORDS):
        score -= 100

    if email_type == "personal":
        score -= 5

    return score


def choose_best_hunter_email(
    emails: list[dict],
    target_domain: str,
    min_confidence: int,
) -> dict:
    if not emails:
        return {}

    valid_emails = []

    for email_record in emails:
        email = safe_text(email_record.get("value")).lower()

        try:
            confidence = int(email_record.get("confidence", 0))
        except Exception:
            confidence = 0

        if not email or "@" not in email:
            continue

        if confidence < min_confidence:
            continue

        if any(bad in email for bad in BAD_EMAIL_KEYWORDS):
            continue

        valid_emails.append(email_record)

    if not valid_emails:
        return {}

    ranked = sorted(
        valid_emails,
        key=lambda item: score_hunter_email(item, target_domain),
        reverse=True,
    )

    return ranked[0]


# ============================================================
# HUNTER API CALL
# ============================================================

def empty_hunter_result(status: str, error: str = "") -> dict:
    return {
        "hunter_status": status,
        "hunter_email": "",
        "hunter_confidence": "",
        "hunter_type": "",
        "hunter_position": "",
        "hunter_source_count": 0,
        "hunter_raw_emails": "",
        "hunter_error": error,
    }


def call_hunter_domain_search(
    domain: str,
    api_key: str,
    min_confidence: int,
) -> dict:
    params = {
        "domain": domain,
        "api_key": api_key,
        "limit": 10,
    }

    try:
        response = requests.get(
            HUNTER_DOMAIN_SEARCH_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        status_code = response.status_code

        if status_code == 401:
            return empty_hunter_result(
                status="api_key_error",
                error="401 unauthorized - check Hunter API key",
            )

        if status_code == 429:
            return empty_hunter_result(
                status="rate_limited",
                error="429 rate limited",
            )

        if status_code >= 400:
            return empty_hunter_result(
                status="api_error",
                error=f"http_error_{status_code}: {response.text[:200]}",
            )

        data = response.json()
        hunter_data = data.get("data", {})
        emails = hunter_data.get("emails", []) or []

        raw_email_values = [
            safe_text(item.get("value")).lower()
            for item in emails
            if safe_text(item.get("value"))
        ]

        best_email = choose_best_hunter_email(
            emails=emails,
            target_domain=domain,
            min_confidence=min_confidence,
        )

        if not best_email:
            return {
                "hunter_status": "not_found",
                "hunter_email": "",
                "hunter_confidence": "",
                "hunter_type": "",
                "hunter_position": "",
                "hunter_source_count": 0,
                "hunter_raw_emails": "; ".join(raw_email_values),
                "hunter_error": "",
            }

        sources = best_email.get("sources", []) or []

        return {
            "hunter_status": "found",
            "hunter_email": safe_text(best_email.get("value")).lower(),
            "hunter_confidence": best_email.get("confidence", ""),
            "hunter_type": safe_text(best_email.get("type")),
            "hunter_position": safe_text(best_email.get("position")),
            "hunter_source_count": len(sources),
            "hunter_raw_emails": "; ".join(raw_email_values),
            "hunter_error": "",
        }

    except requests.exceptions.Timeout:
        return empty_hunter_result("timeout", "request timeout")

    except requests.exceptions.ConnectionError:
        return empty_hunter_result("connection_error", "connection error")

    except Exception as exc:
        return empty_hunter_result(
            "unexpected_error",
            f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# MERGE HUNTER RESULTS INTO FINAL GOLD
# ============================================================

def make_sure_hunter_columns_exist(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_HUNTER_RESULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df


def merge_hunter_results_into_enriched_gold(
    enriched_gold: pd.DataFrame,
    hunter_results: pd.DataFrame,
) -> pd.DataFrame:
    final_df = enriched_gold.copy()

    final_df["hunter_domain_clean"] = final_df.apply(
        build_hunter_domain_for_gold_row,
        axis=1,
    )

    hunter_results = make_sure_hunter_columns_exist(hunter_results)

    hunter_results_small = hunter_results[
        [
            "hunter_domain_clean",
            "hunter_email",
            "hunter_confidence",
            "hunter_type",
            "hunter_position",
            "hunter_source_count",
            "hunter_status",
            "hunter_raw_emails",
            "hunter_error",
            "hunter_enriched_at",
        ]
    ].copy()

    final_df = final_df.merge(
        hunter_results_small,
        on="hunter_domain_clean",
        how="left",
    )

    for col in ["email", "email_source", "email_status", "email_confidence"]:
        if col not in final_df.columns:
            final_df[col] = ""

    found_mask = (
        final_df["email"].fillna("").astype(str).str.strip().eq("")
        & final_df["hunter_email"].fillna("").astype(str).str.strip().ne("")
        & final_df["hunter_status"].fillna("").astype(str).eq("found")
    )

    final_df.loc[found_mask, "email"] = final_df.loc[found_mask, "hunter_email"]
    final_df.loc[found_mask, "email_status"] = "found"
    final_df.loc[found_mask, "email_source"] = "hunter_domain_search"
    final_df.loc[found_mask, "email_confidence"] = final_df.loc[
        found_mask, "hunter_confidence"
    ].apply(confidence_label)

    return final_df


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use Hunter Domain Search API to enrich missing emails."
    )

    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Optional Hunter input CSV path. If empty, uses the full clean Hunter input file.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of domains to process. Default is 5 to protect free credits.",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all domains in the selected Hunter input file.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Seconds to sleep between Hunter API calls.",
    )

    parser.add_argument(
        "--min-confidence",
        type=int,
        default=DEFAULT_MIN_CONFIDENCE,
        help="Minimum Hunter confidence score to accept an email.",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    args = parse_args()
    ensure_dirs()

    api_key = get_api_key()

    input_path = Path(args.input) if args.input else DEFAULT_HUNTER_INPUT_PATH

    if not input_path.exists():
        raise FileNotFoundError(f"Hunter input not found: {input_path}")

    if not ENRICHED_GOLD_PATH.exists():
        raise FileNotFoundError(f"Enriched Gold file not found: {ENRICHED_GOLD_PATH}")

    hunter_input = pd.read_csv(input_path, encoding="utf-8-sig")
    enriched_gold = pd.read_csv(ENRICHED_GOLD_PATH, encoding="utf-8-sig")

    if "hunter_domain_clean" not in hunter_input.columns:
        raise ValueError("Hunter input must contain hunter_domain_clean column.")

    hunter_input["hunter_domain_clean"] = (
        hunter_input["hunter_domain_clean"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )

    hunter_input = hunter_input[
        hunter_input["hunter_domain_clean"].ne("")
    ].copy()

    hunter_input = hunter_input.drop_duplicates(
        subset=["hunter_domain_clean"],
        keep="first",
    ).copy()

    if args.all:
        run_df = hunter_input.copy()
    else:
        run_df = hunter_input.head(args.limit).copy()

    print("=" * 80)
    print("HUNTER API EMAIL ENRICHMENT STARTED")
    print("=" * 80)
    print(f"Hunter input file: {input_path}")
    print(f"Hunter input rows: {len(hunter_input)}")
    print(f"Rows to process now: {len(run_df)}")
    print(f"Min confidence: {args.min_confidence}")
    print("=" * 80)

    result_rows = []

    for _, row in run_df.iterrows():
        domain = safe_text(row.get("hunter_domain_clean")).lower()
        name = safe_text(row.get("name"))

        print(f"[{len(result_rows) + 1}/{len(run_df)}] {name} | {domain}")

        result = call_hunter_domain_search(
            domain=domain,
            api_key=api_key,
            min_confidence=args.min_confidence,
        )

        output_row = row.to_dict()
        output_row.update(result)
        output_row["hunter_enriched_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        result_rows.append(output_row)

        print(
            f"    status={output_row.get('hunter_status')} | "
            f"email={output_row.get('hunter_email', '') or '-'} | "
            f"confidence={output_row.get('hunter_confidence', '') or '-'}"
        )

        if output_row.get("hunter_status") == "api_key_error":
            print("")
            print("Hunter API key error detected. Stopping early.")
            print("Fix HUNTER_API_KEY before running again.")
            break

        time.sleep(args.sleep)

    hunter_results = pd.DataFrame(result_rows)
    hunter_results = make_sure_hunter_columns_exist(hunter_results)

    hunter_results.to_csv(
        HUNTER_RESULTS_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    final_df = merge_hunter_results_into_enriched_gold(
        enriched_gold=enriched_gold,
        hunter_results=hunter_results,
    )

    final_df.to_csv(
        FINAL_ENRICHED_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    found_count = int((hunter_results["hunter_status"] == "found").sum())
    processed_count = len(hunter_results)

    report = f"""# Hunter API Enrichment Report

Generated at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

| Metric | Count |
|---|---:|
| Hunter input file | {input_path} |
| Hunter input domains | {len(hunter_input)} |
| Domains processed in this run | {processed_count} |
| Hunter emails found | {found_count} |
| Hunter emails not found / errors | {processed_count - found_count} |

## Files

Hunter API results:

`{HUNTER_RESULTS_PATH}`

Final enriched Gold output:

`{FINAL_ENRICHED_OUTPUT_PATH}`

## Notes

Default mode processes only 5 domains to protect free credits.

Use `--all` only when you intentionally want to process all rows in the selected input file.
"""

    REPORT_PATH.write_text(report, encoding="utf-8")

    print("=" * 80)
    print("HUNTER API EMAIL ENRICHMENT FINISHED")
    print("=" * 80)
    print(f"Hunter results: {HUNTER_RESULTS_PATH}")
    print(f"Final enriched output: {FINAL_ENRICHED_OUTPUT_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("")
    print(f"Processed: {processed_count}")
    print(f"Hunter emails found: {found_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()