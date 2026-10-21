# MIGRIGA Analytics - Customer segmentation with RFM features and K-Means clustering
#
# R (Recency)   = days between the customer's last eligible purchase and the reference date
# F (Frequency) = number of DISTINCT eligible purchase invoices (not invoice lines)
# M (Monetary)  = gross merchandise purchase value minus that customer's cancelled value (net, £)
# Reference date = day after the last eligible purchase in the warehouse (not "today"), so
# recency is meaningful for this historical dataset.
import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from etl import config
from .warehouse import AnalyticsParamError, IS_CANCEL, IS_SALE, data_version

K_MIN, K_MAX = 2, 10
DEFAULT_K = 4
DEFAULT_SEED = 42
SILHOUETTE_SAMPLE = 5000
DEFAULT_MODEL_PATH = os.path.join(config.PROJECT_ROOT, "data", "processed", "segmentation_model.json")


def model_path() -> str:
    return os.environ.get("MIGRIGA_MODEL_PATH", DEFAULT_MODEL_PATH)


def validate_params(params: dict) -> dict:
    params = params or {}
    try:
        k = int(params.get("k") or DEFAULT_K)
        seed = int(params.get("seed") if params.get("seed") not in (None, "") else DEFAULT_SEED)
    except (TypeError, ValueError):
        raise AnalyticsParamError("k and seed must be integers.")
    if not K_MIN <= k <= K_MAX:
        raise AnalyticsParamError(f"k (number of clusters) must be between {K_MIN} and {K_MAX}.")
    if not 0 <= seed <= 2**31 - 1:
        raise AnalyticsParamError("seed must be a non-negative 32-bit integer.")
    ref = params.get("reference_date") or None
    if ref is not None:
        try:
            datetime.strptime(ref, "%Y-%m-%d")
        except (TypeError, ValueError):
            raise AnalyticsParamError("reference_date must be YYYY-MM-DD.")
    return {"k": k, "seed": seed, "reference_date": ref}


def compute_rfm(lines: pd.DataFrame, reference_date=None):
    """lines: customer_id, invoice_no, invoice_datetime, line_type, line_amount (merchandise, non-duplicate).
    Returns (rfm DataFrame for every identified customer, reference_date string)."""
    sales = lines[lines["line_type"] == "SALE"]
    cancels = lines[lines["line_type"] == "CANCELLATION"]
    if reference_date is None:
        if sales.empty:
            reference_date = datetime.now().strftime("%Y-%m-%d")
        else:
            last = pd.to_datetime(sales["invoice_datetime"]).max().normalize()
            reference_date = (last + timedelta(days=1)).strftime("%Y-%m-%d")
    ref = pd.Timestamp(reference_date)

    g = sales.groupby("customer_id").agg(
        last_purchase=("invoice_datetime", "max"),
        first_purchase=("invoice_datetime", "min"),
        frequency=("invoice_no", "nunique"),
        gross_value=("line_amount", "sum"),
    )
    cancelled = (-cancels.groupby("customer_id")["line_amount"].sum()).rename("cancelled_value")
    all_ids = pd.Index(sorted(set(lines["customer_id"])), name="customer_id")
    rfm = g.reindex(all_ids).join(cancelled, how="left")
    rfm["frequency"] = rfm["frequency"].fillna(0).astype(int)
    rfm["gross_value"] = rfm["gross_value"].fillna(0.0)
    rfm["cancelled_value"] = rfm["cancelled_value"].fillna(0.0)
    rfm["monetary"] = (rfm["gross_value"] - rfm["cancelled_value"]).round(2)
    last = pd.to_datetime(rfm["last_purchase"])
    rfm["recency_days"] = (ref - last.dt.normalize()).dt.days
    return rfm.reset_index(), reference_date


def eligibility(rfm: pd.DataFrame):
    """Customers suitable for clustering: >= 1 purchase invoice and positive net monetary value."""
    no_purchase = rfm["frequency"] < 1
    non_positive = (~no_purchase) & (rfm["monetary"] <= 0)
    future = (~no_purchase) & (rfm["recency_days"] < 0)
    keep = ~(no_purchase | non_positive | future)
    return keep, {
        "no_eligible_purchase": int(no_purchase.sum()),
        "non_positive_net_value": int(non_positive.sum()),
        "purchase_after_reference_date": int(future.sum()),
    }


def prepare_features(rfm: pd.DataFrame):
    """log1p transform (RFM values are heavily right-skewed) then z-score standardisation."""
    raw = rfm[["recency_days", "frequency", "monetary"]].astype(float)
    if raw.isna().any().any() or not np.isfinite(raw.to_numpy()).all():
        raise AnalyticsParamError("RFM features contain missing or non-finite values.")
    if (raw < 0).any().any():
        raise AnalyticsParamError("RFM features must be non-negative before the log transform.")
    logged = np.log1p(raw.to_numpy())
    scaler = StandardScaler()
    X = scaler.fit_transform(logged)
    return X, scaler


def fit_kmeans(X, k, seed):
    if len(X) < k:
        raise AnalyticsParamError(f"Only {len(X)} eligible customers; cannot form {k} clusters.")
    model = KMeans(n_clusters=k, n_init=10, random_state=seed)
    labels = model.fit_predict(X)
    return model, labels


def silhouette(X, labels, seed):
    n_labels = len(set(labels))
    if n_labels < 2:
        return None, "Silhouette needs at least 2 non-empty clusters."
    if n_labels >= len(X):
        return None, "Silhouette is undefined when every customer is its own cluster."
    sample = min(len(X), SILHOUETTE_SAMPLE)
    score = silhouette_score(X, labels, sample_size=sample if sample < len(X) else None, random_state=seed)
    note = None if sample == len(X) else f"Computed on a seeded random sample of {sample} customers."
    return float(score), note


def _descriptor(value, overall, higher_word, lower_word, tol=0.15):
    if overall == 0:
        return "typical"
    ratio = value / overall
    if ratio >= 1 + tol:
        return higher_word
    if ratio <= 1 - tol:
        return lower_word
    return "typical"


def describe_clusters(rfm: pd.DataFrame, labels) -> list:
    """Profiles each cluster by its measured medians relative to the overall medians."""
    df = rfm.assign(cluster=labels)
    overall = df[["recency_days", "frequency", "monetary"]].median()
    out = []
    for cl, grp in df.groupby("cluster"):
        med = grp[["recency_days", "frequency", "monetary"]].median()
        mean = grp[["recency_days", "frequency", "monetary"]].mean()
        rec = _descriptor(med["recency_days"], overall["recency_days"], "less recent", "more recent")
        freq = _descriptor(med["frequency"], overall["frequency"], "more frequent", "less frequent")
        mon = _descriptor(med["monetary"], overall["monetary"], "higher spend", "lower spend")
        out.append({
            "cluster": int(cl),
            "size": int(len(grp)),
            "share": len(grp) / len(df),
            "median": {"recency_days": float(med["recency_days"]), "frequency": float(med["frequency"]),
                       "monetary": round(float(med["monetary"]), 2)},
            "mean": {"recency_days": round(float(mean["recency_days"]), 1),
                     "frequency": round(float(mean["frequency"]), 2),
                     "monetary": round(float(mean["monetary"]), 2)},
            "total_monetary": round(float(grp["monetary"].sum()), 2),
            "descriptors": {"recency": rec, "frequency": freq, "monetary": mon},
            "profile": f"{rec.capitalize()} · {freq} · {mon}",
        })
    # Stable, meaningful ordering: by median monetary value, highest first
    out.sort(key=lambda c: -c["median"]["monetary"])
    return out


def load_lines(conn) -> pd.DataFrame:
    sql = ("SELECT cu.customer_id, cu.primary_country AS country, f.invoice_no, f.invoice_datetime, "
           "f.line_type, f.line_amount FROM fact_sales f JOIN dim_customer cu ON cu.customer_key = f.customer_key "
           f"WHERE f.customer_key <> 0 AND f.is_product = 1 AND f.is_duplicate = 0 AND ({IS_SALE} OR {IS_CANCEL})")
    return pd.read_sql_query(sql, conn)


def segment(conn, params: dict, progress=None, save_model=True) -> dict:
    p = validate_params(params)
    report = progress or (lambda msg, pct: None)
    report("Loading identified-customer lines", 5)
    lines = load_lines(conn)
    country = lines.drop_duplicates("customer_id").set_index("customer_id")["country"]
    report("Computing RFM features", 25)
    rfm, ref_date = compute_rfm(lines.drop(columns=["country"]), p["reference_date"])
    keep, excluded = eligibility(rfm)
    data = rfm[keep].reset_index(drop=True)
    if len(data) < p["k"]:
        raise AnalyticsParamError(f"Only {len(data)} eligible customers; cannot form {p['k']} clusters.")

    report("Scaling features", 40)
    X, scaler = prepare_features(data)
    report(f"Fitting K-Means (k={p['k']})", 55)
    model, labels = fit_kmeans(X, p["k"], p["seed"])
    score, note = silhouette(X, labels, p["seed"])

    report("Evaluating k = 2…10 (elbow / silhouette)", 75)
    elbow = []
    for kk in range(K_MIN, min(K_MAX, len(data) - 1) + 1):
        m = KMeans(n_clusters=kk, n_init=10, random_state=p["seed"]).fit(X)
        s, _ = silhouette(X, m.labels_, p["seed"])
        elbow.append({"k": kk, "inertia": float(m.inertia_), "silhouette": s})

    clusters = describe_clusters(data, labels)
    # Renumber clusters 1..k in profile order so labels are stable for the UI
    order = {c["cluster"]: i + 1 for i, c in enumerate(clusters)}
    for c in clusters:
        c["cluster"] = order[c["cluster"]]
    data["cluster"] = [order[int(l)] for l in labels]
    data["country"] = data["customer_id"].map(country)

    centers_log = scaler.inverse_transform(model.cluster_centers_)
    centers = [{"cluster": order[i], "recency_days": float(np.expm1(c[0])), "frequency": float(np.expm1(c[1])),
                "monetary": float(np.expm1(c[2]))} for i, c in enumerate(centers_log)]
    centers.sort(key=lambda c: c["cluster"])

    customers = data[["customer_id", "country", "recency_days", "frequency", "monetary", "cluster"]]
    result = {
        "params": p,
        "data_version": data_version(conn),
        "reference_date": ref_date,
        "customers_total": int(len(rfm)),
        "customers_included": int(len(data)),
        "customers_excluded": excluded,
        "features": "log1p(R, F, M) → StandardScaler (z-scores)",
        "silhouette": score,
        "silhouette_note": note,
        "inertia": float(model.inertia_),
        "clusters": clusters,
        "centers": centers,
        "elbow": elbow,
        "distributions": {
            m: _histogram(data[m]) for m in ("recency_days", "frequency", "monetary")
        },
        "customers": customers.to_dict(orient="records"),
    }
    if save_model:
        _save_model(p, scaler, model, order, ref_date, result["data_version"], score)
    report("Done", 100)
    return result


def _histogram(series: pd.Series, bins=20) -> dict:
    vals = series.astype(float).to_numpy()
    # Log-spaced bins for skewed measures; clip at the 99th percentile so the chart stays readable
    hi = float(np.percentile(vals, 99))
    lo = float(max(vals.min(), 0))
    edges = np.linspace(lo, hi if hi > lo else lo + 1, bins + 1)
    counts, edges = np.histogram(np.clip(vals, lo, hi), bins=edges)
    return {"edges": [round(float(e), 2) for e in edges], "counts": [int(c) for c in counts],
            "clipped_at_p99": round(hi, 2), "median": float(np.median(vals)), "mean": round(float(vals.mean()), 2)}


def _save_model(p, scaler, model, order, ref_date, version, score):
    path = model_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "data_version": version, "params": p, "reference_date": ref_date,
        "features": ["recency_days", "frequency", "monetary"], "transform": "log1p",
        "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "cluster_centers_scaled": model.cluster_centers_.tolist(),
        "cluster_label_map": {str(k): v for k, v in order.items()},
        "silhouette": score,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)
