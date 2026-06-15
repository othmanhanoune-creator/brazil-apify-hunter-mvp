import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd


INPUT_PATH = Path("data/lake/bronze/apify_google_maps/brazil_apify_raw.csv")
SILVER_PATH = Path("data/lake/silver/leads_cleaned/brazil_silver_leads.csv")
GOLD_PATH = Path("data/lake/gold/qualified_b2b_leads/brazil_qualified_b2b_leads.csv")
WAREHOUSE_PATH = Path("data/warehouse/brazil_b2b_leads.db")


def safe_text(value: Any) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def clean_website(value: Any) -> str:
    website = safe_text(value)
    if not website:
        return ""
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website


def extract_domain(website: str) -> str:
    website = clean_website(website)
    if not website:
        return ""

    parsed = urlparse(website)
    domain = parsed.netloc.lower().strip()
    domain = domain.replace("www.", "")
    domain = domain.split(":")[0]

    if "." not in domain:
        return ""

    return domain


def clean_phone(value: Any) -> str:
    phone = safe_text(value)
    return phone.replace("\n", " ").replace("\r", " ").strip()


def combine_categories(row: pd.Series) -> str:
    category_cols = [col for col in row.index if col.startswith("categories/")]
    values = []

    for col in category_cols:
        text = safe_text(row.get(col))
        if text:
            values.append(text)

    category_name = safe_text(row.get("categoryName"))
    if category_name:
        values.append(category_name)

    # Remove duplicates while preserving order
    seen = set()
    clean_values = []
    for item in values:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            clean_values.append(item)

    return " | ".join(clean_values)


FLOORING_KEYWORDS = [
    "piso", "pisos", "revestimento", "revestimentos",
    "vinílico", "vinilico", "laminado", "laminados",
    "assoalho", "assoalhos", "porcelanato", "cerâmica", "ceramica",
    "acabamento", "acabamentos"
]

B2B_KEYWORDS = [
    "distribuidora", "distribuidor", "distribuição", "distribuicao",
    "atacado", "atacadista", "fornecedor", "fornecedora",
    "importadora", "importador", "importe", "comercial",
    "depósito", "deposito", "warehouse",
    "materiais de construção", "materiais de construcao"
]

NEGATIVE_KEYWORDS = [
    "instalador", "colocador", "limpeza", "reforma",
    "marceneiro", "decoração", "decoracao", "designer de interiores",
    "alimentos", "bebidas", "carne", "banana",
    "farmácia", "farmacia", "medicamentos",
    "autopeças", "auto peças", "peças automotivas",
    "gás", "gas", "petroleo", "petróleo",
    "restaurante", "hotel", "escola", "hospital",
    "ótica", "otica", "óculos", "oculos"
]


def contains_any(text: str, keywords: list[str]) -> bool:
    text = text.lower()
    return any(keyword in text for keyword in keywords)


def score_lead(row: pd.Series) -> tuple[int, str, str]:
    name = safe_text(row.get("name"))
    category = safe_text(row.get("category"))
    categories = safe_text(row.get("categories"))
    website = safe_text(row.get("website"))
    phone = safe_text(row.get("phone"))
    rating = row.get("rating", 0)
    reviews_count = row.get("reviews_count", 0)

    blob = f"{name} {category} {categories}".lower()

    has_flooring = contains_any(blob, FLOORING_KEYWORDS)
    has_b2b = contains_any(blob, B2B_KEYWORDS)
    has_negative = contains_any(blob, NEGATIVE_KEYWORDS)

    score = 0
    reasons = []

    if has_flooring:
        score += 4
        reasons.append("flooring/revestimentos signal")

    if has_b2b:
        score += 4
        reasons.append("B2B/distributor/wholesale signal")

    if website:
        score += 2
        reasons.append("website available")

    if phone:
        score += 2
        reasons.append("phone available")

    try:
        if float(rating or 0) >= 4:
            score += 1
            reasons.append("strong rating")
    except Exception:
        pass

    try:
        if float(reviews_count or 0) >= 50:
            score += 1
            reasons.append("many reviews")
    except Exception:
        pass

    if has_negative:
        score -= 5
        reasons.append("negative/bad-fit signal")

    if has_negative and not has_flooring:
        status = "low_relevance"
    elif has_flooring and has_b2b and website and phone and score >= 10:
        status = "strong_b2b"
    elif has_flooring and (has_b2b or website or phone) and score >= 7:
        status = "medium_b2b"
    elif has_flooring or has_b2b:
        status = "needs_review"
    else:
        status = "low_relevance"

    return score, status, "; ".join(reasons)


def build_standard_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    records = []

    for _, row in raw_df.iterrows():
        website = clean_website(row.get("website"))
        domain = extract_domain(website)
        categories = combine_categories(row)

        record = {
            "name": safe_text(row.get("title")),
            "address": safe_text(row.get("street")),
            "city": safe_text(row.get("city")),
            "state": safe_text(row.get("state")),
            "country": "Brazil" if safe_text(row.get("countryCode")).upper() == "BR" else safe_text(row.get("countryCode")),
            "phone": clean_phone(row.get("phone")),
            "website": website,
            "domain": domain,
            "email": "",
            "category": safe_text(row.get("categoryName")),
            "categories": categories,
            "rating": row.get("totalScore", ""),
            "reviews_count": row.get("reviewsCount", ""),
            "source": "apify_google_maps",
            "source_url": safe_text(row.get("url")),
            "search_term": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        records.append(record)

    df = pd.DataFrame(records)

    scores = df.apply(score_lead, axis=1)
    df["b2b_score"] = [item[0] for item in scores]
    df["review_status"] = [item[1] for item in scores]
    df["qualification_reason"] = [item[2] for item in scores]

    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["dedupe_key"] = ""

    df.loc[df["domain"].fillna("") != "", "dedupe_key"] = "domain:" + df["domain"].fillna("")
    df.loc[(df["dedupe_key"] == "") & (df["phone"].fillna("") != ""), "dedupe_key"] = "phone:" + df["phone"].fillna("")
    df.loc[df["dedupe_key"] == "", "dedupe_key"] = (
        "name_city:"
        + df["name"].fillna("").str.lower().str.strip()
        + "|"
        + df["city"].fillna("").str.lower().str.strip()
    )

    df = df.sort_values(
        by=["b2b_score", "reviews_count"],
        ascending=[False, False],
    )

    df = df.drop_duplicates(subset=["dedupe_key"], keep="first")
    df = df.drop(columns=["dedupe_key"])

    return df


def save_to_sqlite(silver_df: pd.DataFrame, gold_df: pd.DataFrame) -> None:
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(WAREHOUSE_PATH)

    silver_df.to_sql(
        "silver_brazil_leads",
        conn,
        if_exists="replace",
        index=False,
    )

    gold_df.to_sql(
        "gold_brazil_qualified_b2b_leads",
        conn,
        if_exists="replace",
        index=False,
    )

    conn.close()


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    print(f"Raw Apify records read: {len(raw_df)}")

    silver_df = build_standard_dataframe(raw_df)
    silver_df = deduplicate(silver_df)

    gold_df = silver_df[
        silver_df["review_status"].isin(["strong_b2b", "medium_b2b"])
    ].copy()

    silver_df.to_csv(SILVER_PATH, index=False, encoding="utf-8-sig")
    gold_df.to_csv(GOLD_PATH, index=False, encoding="utf-8-sig")

    save_to_sqlite(silver_df, gold_df)

    print(f"Silver records written: {len(silver_df)}")
    print(f"Gold qualified records written: {len(gold_df)}")
    print("")
    print("Review status counts:")
    print(silver_df["review_status"].value_counts())
    print("")
    print(f"Silver saved to: {SILVER_PATH}")
    print(f"Gold saved to: {GOLD_PATH}")
    print(f"SQLite warehouse saved to: {WAREHOUSE_PATH}")


if __name__ == "__main__":
    main()