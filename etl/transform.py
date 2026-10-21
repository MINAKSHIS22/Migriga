# MIGRIGA Analytics - TRANSFORM stage
# Cleans, validates and classifies raw invoice lines, and derives the dimension
# members needed by the star schema. See docs/data_dictionary.md for every rule.
import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DATE_FORMAT = "%m/%d/%Y %H:%M"

# Stock codes that represent postage, fees, manual corrections, discounts, vouchers
# or test items rather than merchandise. They are kept in the warehouse but excluded
# from product sales measures and from market basket mining.
NON_PRODUCT_CODE_RE = re.compile(
    r"^(POST|DOT|M|C2|D|S|B|CRUK|ADJUST\d*|BANK CHARGES|AMAZONFEE|TEST\d+|GIFT|GIFT_\d+_\d+)$"
)

# Line classifications (fact_sales.line_type)
SALE = "SALE"                          # positive merchandise purchase with a positive price
CANCELLATION = "CANCELLATION"          # line on an invoice prefixed 'C' (negative quantity)
STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT"  # negative quantity on a normal invoice (damages, write-offs)
ZERO_PRICE = "ZERO_PRICE"              # positive quantity at price 0 (samples, free items)
ADJUSTMENT = "ADJUSTMENT"              # 'A' invoices (bad-debt), negative prices, inconsistent cancellations
LINE_TYPES = [SALE, CANCELLATION, STOCK_ADJUSTMENT, ZERO_PRICE, ADJUSTMENT]

ANONYMOUS_CUSTOMER_ID = "__ANONYMOUS__"
UNKNOWN_COUNTRY = "Unknown"


@dataclass
class TransformResult:
    facts: pd.DataFrame
    rejected: pd.DataFrame
    products: pd.DataFrame
    customers: pd.DataFrame
    countries: list
    dates: pd.DataFrame
    quality: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def normalize_customer_id(value):
    """'13085', '13085.0', ' 13085 ' -> '13085'. Empty or non-numeric -> None (never invented)."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    if re.fullmatch(r"\d+(\.0+)?", s):
        return s.split(".")[0]
    return None


def clean_description(value):
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value)).strip()
    return s or None


def parse_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series.str.strip(), format=DATE_FORMAT, errors="coerce")
    retry = parsed.isna() & series.str.strip().ne("")
    if retry.any():
        parsed.loc[retry] = pd.to_datetime(series[retry].str.strip(), format="ISO8601", errors="coerce")
    return parsed


def classify_lines(invoice_no: pd.Series, quantity: pd.Series, unit_price: pd.Series) -> pd.Series:
    is_c = invoice_no.str.upper().str.startswith("C")
    is_a = invoice_no.str.upper().str.startswith("A")
    conditions = [
        is_a | (unit_price < 0),
        is_c & (quantity > 0),          # cancellation invoice with positive quantity: inconsistent
        is_c,
        quantity < 0,
        unit_price == 0,
    ]
    choices = [ADJUSTMENT, ADJUSTMENT, CANCELLATION, STOCK_ADJUSTMENT, ZERO_PRICE]
    return pd.Series(np.select(conditions, choices, default=SALE), index=invoice_no.index)


def line_fingerprint(parts: list) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _profile_raw(raw: pd.DataFrame) -> dict:
    cols = [c for c in raw.columns if c != "source_row_number"]
    blank = {c: int(raw[c].str.strip().eq("").sum()) for c in cols}
    return {
        "missing_values": blank,
        "exact_duplicate_rows_raw": int(raw.duplicated(subset=cols).sum()),
        "distinct_invoices_raw": int(raw["InvoiceNo"].str.strip().nunique()),
        "distinct_stock_codes_raw": int(raw["StockCode"].str.strip().nunique()),
        "distinct_customers_raw": int(raw.loc[raw["CustomerID"].str.strip() != "", "CustomerID"].str.strip().nunique()),
        "distinct_countries_raw": int(raw["Country"].str.strip().nunique()),
    }


def transform(raw: pd.DataFrame) -> TransformResult:
    quality = {"rows_read": int(len(raw))}
    quality.update(_profile_raw(raw))
    warnings = []

    df = pd.DataFrame({"source_row_number": raw["source_row_number"].astype(int)})
    df["invoice_no"] = raw["InvoiceNo"].str.strip().str.upper()
    df["stock_code_source"] = raw["StockCode"].str.strip()
    df["stock_code"] = df["stock_code_source"].str.upper()
    df["description"] = raw["Description"].map(clean_description)
    df["quantity_num"] = pd.to_numeric(raw["Quantity"].str.strip(), errors="coerce")
    df["unit_price"] = pd.to_numeric(raw["UnitPrice"].str.strip(), errors="coerce")
    df["invoice_dt"] = parse_dates(raw["InvoiceDate"])
    df["customer_id"] = raw["CustomerID"].map(normalize_customer_id)
    country = raw["Country"].str.strip()
    df["country"] = country.where(country != "", UNKNOWN_COUNTRY)

    invalid_customer = raw["CustomerID"].str.strip().ne("") & df["customer_id"].isna()
    quality["invalid_customer_ids_set_anonymous"] = int(invalid_customer.sum())

    # --- Rejection rules (row cannot be placed in the fact table) ---
    reasons = pd.Series("", index=df.index, dtype=object)

    def reject(mask, reason):
        target = mask & reasons.eq("")
        reasons.loc[target] = reason

    reject(df["invoice_no"].eq(""), "missing_invoice_no")
    reject(df["stock_code"].eq(""), "missing_stock_code")
    reject(df["invoice_dt"].isna(), "invalid_invoice_date")
    reject(df["quantity_num"].isna(), "invalid_quantity")
    reject(df["quantity_num"].notna() & (df["quantity_num"] % 1 != 0), "non_integer_quantity")
    reject(df["quantity_num"].eq(0), "zero_quantity")
    reject(df["unit_price"].isna(), "invalid_unit_price")

    rejected_mask = reasons.ne("")
    rejected = raw.loc[rejected_mask].copy()
    rejected["reason"] = reasons[rejected_mask]
    quality["rows_rejected"] = int(rejected_mask.sum())
    quality["rejected_by_reason"] = {k: int(v) for k, v in reasons[rejected_mask].value_counts().items()}

    f = df.loc[~rejected_mask].copy()
    f["quantity"] = f["quantity_num"].astype("int64")
    f["unit_price"] = f["unit_price"].astype(float).round(4)
    f["line_amount"] = (f["quantity"] * f["unit_price"]).round(4)
    f["line_type"] = classify_lines(f["invoice_no"], f["quantity"], f["unit_price"])
    f["is_product"] = (~f["stock_code"].str.match(NON_PRODUCT_CODE_RE)).astype(int)
    f["is_cancellation"] = f["invoice_no"].str.startswith("C").astype(int)
    f["date_key"] = f["invoice_dt"].dt.strftime("%Y%m%d").astype(int)
    f["invoice_datetime"] = f["invoice_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    f["invoice_hour"] = f["invoice_dt"].dt.hour.astype(int)

    # --- Duplicate policy ---
    # The source has no line number, so two physically identical lines are indistinguishable.
    # Every line is loaded (nothing is silently merged); the 2nd+ occurrence of an identical
    # line is flagged is_duplicate=1 and excluded from analytical measures by default.
    dup_cols = ["invoice_no", "stock_code", "description", "quantity", "invoice_datetime",
                "unit_price", "customer_id", "country"]
    key_frame = f[dup_cols].astype(object).where(f[dup_cols].notna(), "").astype(str)
    f["occurrence"] = key_frame.groupby(dup_cols, sort=False, dropna=False).cumcount() + 1
    f["is_duplicate"] = (f["occurrence"] > 1).astype(int)
    quality["duplicate_lines_flagged"] = int(f["is_duplicate"].sum())

    joined = key_frame.agg("|".join, axis=1) + "|" + f["occurrence"].astype(str)
    f["line_fingerprint"] = [hashlib.sha1(s.encode("utf-8")).hexdigest() for s in joined]

    # --- Quality metrics on accepted rows ---
    quality["rows_accepted"] = int(len(f))
    quality["negative_quantity_lines"] = int((f["quantity"] < 0).sum())
    quality["zero_price_lines"] = int((f["unit_price"] == 0).sum())
    quality["negative_price_lines"] = int((f["unit_price"] < 0).sum())
    quality["cancellation_lines"] = int(f["is_cancellation"].sum())
    quality["cancellation_invoices"] = int(f.loc[f["is_cancellation"] == 1, "invoice_no"].nunique())
    quality["adjustment_invoices_A"] = int(f.loc[f["invoice_no"].str.startswith("A"), "invoice_no"].nunique())
    quality["non_product_lines"] = int((f["is_product"] == 0).sum())
    quality["missing_customer_lines"] = int(f["customer_id"].isna().sum())
    quality["missing_description_lines"] = int(f["description"].isna().sum())
    quality["lines_by_type"] = {k: int(v) for k, v in f["line_type"].value_counts().items()}
    quality["stock_codes_case_normalized"] = int(
        (f["stock_code"] != f["stock_code_source"]).sum())
    quality["date_min"] = f["invoice_dt"].min().strftime("%Y-%m-%d %H:%M") if len(f) else None
    quality["date_max"] = f["invoice_dt"].max().strftime("%Y-%m-%d %H:%M") if len(f) else None
    quality["distinct_invoices"] = int(f["invoice_no"].nunique())
    quality["distinct_products"] = int(f["stock_code"].nunique())
    quality["distinct_customers"] = int(f["customer_id"].dropna().nunique())
    quality["distinct_countries"] = int(f["country"].nunique())
    inconsistent = int(((f["is_cancellation"] == 1) & (f["quantity"] > 0)).sum())
    if inconsistent:
        warnings.append(f"{inconsistent} cancellation-invoice line(s) had a positive quantity; classified ADJUSTMENT.")
    if quality["rows_rejected"]:
        warnings.append(f"{quality['rows_rejected']} row(s) rejected; see etl_rejected_rows.")
    if quality["invalid_customer_ids_set_anonymous"]:
        warnings.append(f"{quality['invalid_customer_ids_set_anonymous']} non-numeric CustomerID value(s) treated as anonymous.")

    products = _build_products(f)
    customers = _build_customers(f)
    countries = sorted(f["country"].unique().tolist())
    dates = _build_dates(f["invoice_dt"])

    facts = f[[
        "source_row_number", "line_fingerprint", "invoice_no", "stock_code", "customer_id", "country",
        "date_key", "invoice_datetime", "invoice_hour", "quantity", "unit_price", "line_amount",
        "line_type", "is_product", "is_cancellation", "is_duplicate",
    ]].reset_index(drop=True)

    return TransformResult(
        facts=facts, rejected=rejected.reset_index(drop=True), products=products,
        customers=customers, countries=countries, dates=dates, quality=quality, warnings=warnings,
    )


def _build_products(f: pd.DataFrame) -> pd.DataFrame:
    # Canonical description = most frequent non-empty description, preferring SALE lines.
    described = f[f["description"].notna()].copy()
    described["pref"] = (described["line_type"] == SALE).astype(int)
    counts = (described.groupby(["stock_code", "description"])
              .agg(n=("pref", "size"), sale_n=("pref", "sum")).reset_index()
              .sort_values(["stock_code", "sale_n", "n", "description"], ascending=[True, False, False, True]))
    canonical = counts.drop_duplicates("stock_code").set_index("stock_code")["description"]
    variants = counts.groupby("stock_code").size()

    g = f.groupby("stock_code").agg(
        is_product=("is_product", "max"),
        first_seen=("invoice_datetime", "min"),
        last_seen=("invoice_datetime", "max"),
    )
    g["description"] = canonical.reindex(g.index).fillna("UNKNOWN DESCRIPTION")
    g["description_variants"] = variants.reindex(g.index).fillna(0).astype(int)
    g["item_class"] = np.where(g["is_product"] == 1, "MERCHANDISE", "SERVICE_OR_FEE")
    g["first_seen"] = g["first_seen"].str[:10]
    g["last_seen"] = g["last_seen"].str[:10]
    return g.reset_index()


def _build_customers(f: pd.DataFrame) -> pd.DataFrame:
    known = f[f["customer_id"].notna()]
    if known.empty:
        return pd.DataFrame(columns=["customer_id", "primary_country", "first_invoice_date", "last_invoice_date"])
    # Primary country = country on most of the customer's lines (ties -> alphabetical).
    cc = (known.groupby(["customer_id", "country"]).size().reset_index(name="n")
          .sort_values(["customer_id", "n", "country"], ascending=[True, False, True])
          .drop_duplicates("customer_id").set_index("customer_id")["country"])
    g = known.groupby("customer_id").agg(
        first_invoice_date=("invoice_datetime", "min"), last_invoice_date=("invoice_datetime", "max"))
    g["primary_country"] = cc.reindex(g.index)
    g["first_invoice_date"] = g["first_invoice_date"].str[:10]
    g["last_invoice_date"] = g["last_invoice_date"].str[:10]
    return g.reset_index()


def _build_dates(dts: pd.Series) -> pd.DataFrame:
    if dts.empty:
        return pd.DataFrame(columns=["date_key"])
    days = pd.date_range(dts.min().normalize(), dts.max().normalize(), freq="D")
    d = pd.DataFrame({"full_date": days})
    d["date_key"] = d["full_date"].dt.strftime("%Y%m%d").astype(int)
    d["day"] = d["full_date"].dt.day
    d["month"] = d["full_date"].dt.month
    d["month_name"] = d["full_date"].dt.strftime("%B")
    d["quarter"] = d["full_date"].dt.quarter
    d["year"] = d["full_date"].dt.year
    d["year_month"] = d["full_date"].dt.strftime("%Y-%m")
    d["year_quarter"] = d["year"].astype(str) + "-Q" + d["quarter"].astype(str)
    d["iso_week"] = d["full_date"].dt.isocalendar().week.astype(int)
    d["weekday_num"] = d["full_date"].dt.weekday + 1   # 1 = Monday
    d["weekday_name"] = d["full_date"].dt.strftime("%A")
    d["is_weekend"] = (d["weekday_num"] >= 6).astype(int)
    d["full_date"] = d["full_date"].dt.strftime("%Y-%m-%d")
    return d
