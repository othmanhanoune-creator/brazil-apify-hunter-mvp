from __future__ import annotations

import argparse
import hashlib
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from supabase import create_client

REQUIRED_OUTPUT_COLUMNS = [
    "lead_id", "market", "name", "city", "state", "country", "phone", "website", "email",
    "email_source", "email_status", "email_confidence", "contact_form_url", "b2b_score",
    "gold_split_status", "gold_split_reason", "source_url", "lead_status", "source_batch", "imported_at",
]

COLUMN_ALIASES = {
    "company": "name",
    "company_name": "name",
    "business_name": "name",
    "business": "name",
    "title": "name",
    "url": "website",
    "site": "website",
    "web": "website",
    "telephone": "phone",
    "phone_number": "phone",
    "mobile": "phone",
    "mail": "email",
    "e-mail": "email",
    "email_address": "email",
    "score": "b2b_score",
    "b2bscore": "b2b_score",
    "reason": "gold_split_reason",
    "qualification_reason": "gold_split_reason",
    "maps_url": "source_url",
    "google_maps_url": "source_url",
}


def get_supabase_client():
    url = ""
    key = ""
    try:
        url = st.secrets["supabase"].get("url", "")
        key = st.secrets["supabase"].get("service_role_key", "")
    except Exception:
        pass

    url = url or os.getenv("SUPABASE_URL", "")
    key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise RuntimeError("Missing Supabase credentials. Use .streamlit/secrets.toml or environment variables.")

    return create_client(url, key)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def dataframe_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    clean = df.copy().replace([float("inf"), float("-inf")], pd.NA).astype(object)
    clean = clean.where(pd.notna(clean), None)
    return [{k: json_safe_value(v) for k, v in row.items()} for row in clean.to_dict(orient="records")]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    df = df.rename(columns={col: COLUMN_ALIASES[col] for col in df.columns if col in COLUMN_ALIASES})

    if df.columns.duplicated().any():
        fixed = pd.DataFrame(index=df.index)
        for col in dict.fromkeys(df.columns):
            same_cols = df.loc[:, df.columns == col]
            fixed[col] = same_cols.iloc[:, 0] if same_cols.shape[1] == 1 else same_cols.bfill(axis=1).iloc[:, 0]
        df = fixed

    return df


def normalize_website(value: Any) -> str:
    website = safe_text(value)
    if not website or website.lower() in {"nan", "none", "null"}:
        return ""
    return website


def normalize_email(value: Any) -> str:
    email = safe_text(value).lower()
    return "" if email in {"nan", "none", "null"} else email


def normalize_phone(value: Any) -> str:
    phone = safe_text(value)
    return "" if phone.lower() in {"nan", "none", "null"} else phone


def clean_b2b_score(value: Any) -> int | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def make_lead_id(row: pd.Series, market: str) -> str:
    raw_key = "|".join([
        market.lower(), safe_text(row.get("name")), safe_text(row.get("website")),
        safe_text(row.get("phone")), safe_text(row.get("city")), safe_text(row.get("state")),
    ]).lower()
    return hashlib.sha1(raw_key.encode("utf-8")).hexdigest()[:16]


def read_input_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    raise ValueError("Input file must be .csv, .xlsx, or .xls")


def prepare_leads(df: pd.DataFrame, market: str, source_batch: str) -> pd.DataFrame:
    df = normalize_columns(df)
    if "claim" in df.columns:
        df = df.drop(columns=["claim"])

    for col in REQUIRED_OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df["market"] = market
    df["source_batch"] = source_batch
    df["imported_at"] = datetime.now(UTC).isoformat()
    df["lead_status"] = df["lead_status"].apply(lambda x: safe_text(x) if safe_text(x) else "available")
    df["country"] = df["country"].apply(lambda x: safe_text(x) if safe_text(x) else "Brazil")

    for col in ["name", "city", "state", "country", "email_source", "email_status", "email_confidence", "contact_form_url", "gold_split_status", "gold_split_reason", "source_url"]:
        df[col] = df[col].apply(safe_text)

    df["phone"] = df["phone"].apply(normalize_phone)
    df["website"] = df["website"].apply(normalize_website)
    df["email"] = df["email"].apply(normalize_email)
    df["b2b_score"] = df["b2b_score"].apply(clean_b2b_score)
    df["lead_id"] = df.apply(lambda row: make_lead_id(row, market), axis=1)

    df = df[df["name"].astype(str).str.strip().ne("")].copy()
    df = df.drop_duplicates(subset=["lead_id"], keep="first").copy()
    df = df[REQUIRED_OUTPUT_COLUMNS].copy().replace([float("inf"), float("-inf")], pd.NA)
    df = df.astype(object).where(pd.notna(df), None)
    return df


def chunk_records(records: list[Any], size: int = 250):
    for i in range(0, len(records), size):
        yield records[i:i + size]


def delete_market_data(supabase, market: str) -> None:
    print(f"Deleting old leads for market: {market}")
    existing = supabase.table("leads").select("lead_id").eq("market", market).execute()
    lead_ids = [row["lead_id"] for row in existing.data or []]

    if lead_ids:
        for batch in chunk_records(lead_ids):
            supabase.table("lead_claims").delete().in_("lead_id", batch).execute()

    supabase.table("leads").delete().eq("market", market).execute()
    print(f"Deleted old market data: {len(lead_ids)} leads")


def upload_records(supabase, df: pd.DataFrame) -> int:
    records = dataframe_to_json_records(df)
    total = 0
    for batch in chunk_records(records):
        supabase.table("leads").upsert(batch, on_conflict="lead_id").execute()
        total += len(batch)
        print(f"Uploaded/upserted: {total}/{len(records)}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload cleaned lead files into Supabase.")
    parser.add_argument("--input", required=True, help="Path to CSV/XLSX file to upload.")
    parser.add_argument("--market", required=True, choices=["Brazil"], help="Market label for uploaded Brazil leads.")
    parser.add_argument("--mode", choices=["upsert", "replace-market"], default="upsert")
    args = parser.parse_args()

    input_path = Path(args.input)
    market = args.market
    source_batch = f"{market}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print("=" * 80)
    print("LEAD UPLOAD STARTED")
    print("=" * 80)
    print(f"Input: {input_path}")
    print(f"Market: {market}")
    print(f"Mode: {args.mode}")
    print(f"Source batch: {source_batch}")

    raw = read_input_file(input_path)
    prepared = prepare_leads(raw, market=market, source_batch=source_batch)

    print(f"Rows read: {len(raw)}")
    print(f"Rows prepared: {len(prepared)}")
    preview_cols = [c for c in ["lead_id", "market", "name", "city", "state", "country", "phone", "website", "email"] if c in prepared.columns]
    print(prepared[preview_cols].head(20).to_string(index=False))

    if prepared.empty:
        print("No valid leads found. Nothing uploaded.")
        return

    supabase = get_supabase_client()
    if args.mode == "replace-market":
        delete_market_data(supabase, market)

    uploaded = upload_records(supabase, prepared)
    print("=" * 80)
    print("LEAD UPLOAD FINISHED")
    print(f"Uploaded/upserted: {uploaded}")
    print(f"Market: {market}")
    print("=" * 80)


if __name__ == "__main__":
    main()
