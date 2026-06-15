import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


# This is the cleaned Brazil Silver file created by the Apify CSV importer.
# Silver = cleaned, standardized, deduplicated lead data.
SILVER_PATH = Path("data/lake/silver/leads_cleaned/brazil_silver_leads.csv")


# This output is for high-confidence sales-ready Brazil B2B leads.
# Sales can start with this file first.
STRONG_GOLD_PATH = Path(
    "data/lake/gold/qualified_b2b_leads/brazil_gold_strong_b2b.csv"
)


# This output is for leads that may be useful but need quick review first.
# These are not rejected, but they should not be the first sales batch.
REVIEW_QUEUE_PATH = Path(
    "data/lake/gold/qualified_b2b_leads/brazil_gold_review_queue.csv"
)


# This SQLite database is our simple MVP warehouse.
# It stores the Gold split tables so BI/dashboard tools can query them.
WAREHOUSE_PATH = Path("data/warehouse/brazil_b2b_leads.db")


def safe_text(value: Any) -> str:
    """
    Convert any value into clean text.

    Why this matters:
    CSV files often contain NaN, None, empty cells, numbers, and strings.
    Scoring logic should always work with clean strings.
    """

    if pd.isna(value) or value is None:
        return ""

    return str(value).strip()


def contains_any(text: str, keywords: list[str]) -> bool:
    """
    Check whether a text contains any keyword from a keyword list.

    Example:
    text = "Cristal Pisos Distribuidora"
    keywords = ["pisos", "distribuidora"]

    Result:
    True
    """

    text = text.lower()

    return any(keyword in text for keyword in keywords)


# These words indicate the company is related to flooring, coverings, or finishing products.
# This is the product-fit signal.
FLOORING_KEYWORDS = [
    "piso",
    "pisos",
    "piso vinílico",
    "piso vinilico",
    "pisos vinílicos",
    "pisos vinilicos",
    "laminado",
    "laminados",
    "revestimento",
    "revestimentos",
    "porcelanato",
    "cerâmica",
    "ceramica",
    "assoalho",
    "assoalhos",
    "rodapé",
    "rodape",
    "rodapés",
    "rodapes",
]


# These words indicate the company may be B2B, wholesale, distribution, or import related.
# This is the business-model signal.
STRONG_B2B_KEYWORDS = [
    "distribuidora",
    "distribuidor",
    "distribuição",
    "distribuicao",
    "atacado",
    "atacadão",
    "atacadao",
    "atacadista",
    "fornecedor",
    "fornecedora",
    "importadora",
    "importador",
    "wholesale",
    "warehouse",
]


# These words are relevant, but broader.
# They may describe construction, decor, or finishing material companies.
# These are useful for review queue, but not always strong sales-ready flooring leads.
BROAD_BUT_RELEVANT_KEYWORDS = [
    "materiais de construção",
    "materiais de construcao",
    "acabamento",
    "acabamentos",
    "casa e construção",
    "casa & construção",
    "casa e construcao",
    "construção",
    "construcao",
    "decoração",
    "decoracao",
    "decor",
]


# These words indicate weak fit or wrong industry.
# If a lead has these signals, we do not want it in sales-ready Gold.
BAD_FIT_KEYWORDS = [
    "instalador",
    "instalação",
    "instalacao",
    "colocador",
    "limpeza",
    "lavagem",
    "reforma",
    "marcenaria",
    "marceneiro",
    "designer de interiores",
    "arquiteto",
    "arquitetura",
    "alimentos",
    "bebidas",
    "carne",
    "banana",
    "farmácia",
    "farmacia",
    "medicamentos",
    "autopeças",
    "auto peças",
    "peças automotivas",
    "baterias",
    "gás",
    "gas",
    "petróleo",
    "petroleo",
    "restaurante",
    "hotel",
    "escola",
    "hospital",
    "ótica",
    "otica",
    "óculos",
    "oculos",
]


def classify_gold_split(row: pd.Series) -> tuple[str, str]:
    """
    Classify one Silver lead into one of three Gold split groups:

    1. strong_b2b_sales_ready
       Best leads for Sales to contact first.

    2. review_queue
       Possible leads, but BI/Sales should review before outreach.

    3. exclude_from_gold
       Weak, unrelated, or service-only leads.
    """

    name = safe_text(row.get("name"))
    category = safe_text(row.get("category"))
    categories = safe_text(row.get("categories"))
    website = safe_text(row.get("website"))
    phone = safe_text(row.get("phone"))
    review_status = safe_text(row.get("review_status"))

    score = int(row.get("b2b_score") or 0)

    # Combine the most useful text fields into one searchable text blob.
    # This lets the keyword rules evaluate the whole lead profile.
    blob = f"{name} {category} {categories}".lower()

    # Product fit: does the lead look flooring-related?
    has_flooring = contains_any(blob, FLOORING_KEYWORDS)

    # Business fit: does the lead look like a distributor, wholesaler, supplier, or importer?
    has_strong_b2b = contains_any(blob, STRONG_B2B_KEYWORDS)

    # Broader construction/decor fit: possibly relevant, but not enough for immediate sales.
    has_broad_relevant = contains_any(blob, BROAD_BUT_RELEVANT_KEYWORDS)

    # Bad-fit signal: installer, repair, unrelated industry, etc.
    has_bad_fit = contains_any(blob, BAD_FIT_KEYWORDS)

    # Contact availability matters because Sales needs a way to reach the company.
    has_contact = bool(website) or bool(phone)

    # Strongest contact profile: both website and phone are available.
    has_both_contact = bool(website) and bool(phone)

    # We collect reasons so Sales/BI can understand why a lead was classified.
    reasons = []

    if has_flooring:
        reasons.append("flooring/product signal")

    if has_strong_b2b:
        reasons.append("strong distributor/wholesale/import signal")

    if has_broad_relevant:
        reasons.append("broad construction/decor/finishing signal")

    if website:
        reasons.append("website available")

    if phone:
        reasons.append("phone available")

    if has_bad_fit:
        reasons.append("bad-fit/service/unrelated signal")

    # Rule 1:
    # This is the best case.
    # The lead is already strong/medium from the first scoring layer,
    # has flooring signal,
    # has strong B2B signal,
    # has both website and phone,
    # has no bad-fit signal,
    # and has a strong score.
    if (
        review_status in ["strong_b2b", "medium_b2b"]
        and has_flooring
        and has_strong_b2b
        and has_both_contact
        and not has_bad_fit
        and score >= 10
    ):
        return "strong_b2b_sales_ready", "; ".join(reasons)

    # Rule 2:
    # This is a useful flooring lead, but maybe it is not clearly wholesale/import/distribution.
    # It goes to review queue instead of being sent directly to Sales.
    if (
        review_status in ["strong_b2b", "medium_b2b"]
        and has_flooring
        and has_contact
        and not has_bad_fit
    ):
        return "review_queue", "; ".join(
            reasons + ["needs quick sales/BI review before outreach"]
        )

    # Rule 3:
    # This is a broad construction, decor, or finishing company.
    # It may still be useful, but it is not a first-priority flooring distributor.
    if (
        review_status in ["strong_b2b", "medium_b2b", "needs_review"]
        and has_broad_relevant
        and has_contact
        and not has_bad_fit
    ):
        return "review_queue", "; ".join(
            reasons + ["broad construction/finishing lead, not pure flooring distributor"]
        )

    # Everything else is removed from the Gold sales files.
    return "exclude_from_gold", "; ".join(reasons)


def main() -> None:
    """
    Main script flow:

    1. Read Silver Brazil leads.
    2. Apply Gold split classification.
    3. Save strong sales-ready leads to CSV.
    4. Save review queue leads to CSV.
    5. Save both tables to SQLite warehouse.
    6. Print summary counts.
    """

    # Stop early if the Silver file does not exist.
    # This prevents silent failures.
    if not SILVER_PATH.exists():
        raise FileNotFoundError(f"Silver file not found: {SILVER_PATH}")

    # Make sure output folders exist before writing files.
    STRONG_GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Read the Silver CSV.
    # utf-8-sig helps Excel open Portuguese accents correctly.
    df = pd.read_csv(SILVER_PATH, encoding="utf-8-sig")

    # Apply classify_gold_split to every row.
    # Each result is a tuple:
    # (gold_split_status, gold_split_reason)
    split_results = df.apply(classify_gold_split, axis=1)

    # Add the split status column.
    df["gold_split_status"] = [item[0] for item in split_results]

    # Add the explanation/reason column.
    df["gold_split_reason"] = [item[1] for item in split_results]

    # Strong Gold file:
    # only high-confidence sales-ready leads.
    strong_df = df[df["gold_split_status"] == "strong_b2b_sales_ready"].copy()

    # Review queue file:
    # leads that may be useful but need human review first.
    review_df = df[df["gold_split_status"] == "review_queue"].copy()

    # Sort strong leads so the best-scored and most-reviewed companies appear first.
    strong_df = strong_df.sort_values(
        by=["b2b_score", "reviews_count"],
        ascending=[False, False],
    )

    # Sort review queue the same way.
    review_df = review_df.sort_values(
        by=["b2b_score", "reviews_count"],
        ascending=[False, False],
    )

    # Save the strong Gold CSV.
    strong_df.to_csv(STRONG_GOLD_PATH, index=False, encoding="utf-8-sig")

    # Save the review queue CSV.
    review_df.to_csv(REVIEW_QUEUE_PATH, index=False, encoding="utf-8-sig")

    # Open a SQLite connection to the warehouse database.
    conn = sqlite3.connect(WAREHOUSE_PATH)

    # Save the strong Gold table to SQLite.
    strong_df.to_sql(
        "gold_brazil_strong_b2b_sales_ready",
        conn,
        if_exists="replace",
        index=False,
    )

    # Save the review queue table to SQLite.
    review_df.to_sql(
        "gold_brazil_review_queue",
        conn,
        if_exists="replace",
        index=False,
    )

    # Close the database connection.
    conn.close()

    # Print a readable summary for the terminal.
    print("Brazil Gold split complete")
    print("=" * 50)
    print(f"Silver input records: {len(df)}")
    print(f"Strong sales-ready B2B leads: {len(strong_df)}")
    print(f"Review queue leads: {len(review_df)}")
    print(f"Excluded from Gold: {(df['gold_split_status'] == 'exclude_from_gold').sum()}")
    print("")

    print("Gold split status counts:")
    print(df["gold_split_status"].value_counts())
    print("")

    print(f"Strong Gold saved to: {STRONG_GOLD_PATH}")
    print(f"Review Queue saved to: {REVIEW_QUEUE_PATH}")
    print(f"Warehouse updated: {WAREHOUSE_PATH}")


if __name__ == "__main__":
    main()