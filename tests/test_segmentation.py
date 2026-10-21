# RFM + K-Means tests: feature calculation, eligibility, scaling, k validation, reproducibility
import numpy as np
import pandas as pd
import pytest

from analytics import customer_segmentation as cs
from analytics.warehouse import AnalyticsParamError


def lines(rows):
    return pd.DataFrame(rows, columns=["customer_id", "invoice_no", "invoice_datetime", "line_type", "line_amount"])


def test_rfm_counts_distinct_invoices_not_lines():
    df = lines([
        ("1", "A", "2010-01-01 10:00:00", "SALE", 10.0),
        ("1", "A", "2010-01-01 10:00:00", "SALE", 5.0),     # same invoice, 2nd line
        ("1", "B", "2010-01-10 10:00:00", "SALE", 20.0),
        ("1", "C1", "2010-01-11 10:00:00", "CANCELLATION", -5.0),
        ("2", "D", "2010-01-05 09:00:00", "SALE", 7.5),
    ])
    rfm, ref = cs.compute_rfm(df)
    r = rfm.set_index("customer_id")
    assert ref == "2010-01-11"                          # day after last SALE
    assert r.loc["1", "frequency"] == 2
    assert r.loc["1", "monetary"] == pytest.approx(30.0)  # 35 gross - 5 cancelled
    assert r.loc["1", "recency_days"] == 1
    assert r.loc["2", "recency_days"] == 6


def test_explicit_reference_date():
    df = lines([("1", "A", "2010-01-01 10:00:00", "SALE", 10.0)])
    rfm, ref = cs.compute_rfm(df, "2010-02-01")
    assert ref == "2010-02-01" and rfm.iloc[0]["recency_days"] == 31


def test_eligibility_excludes_cancel_only_and_non_positive():
    df = lines([
        ("1", "A", "2010-01-01 10:00:00", "SALE", 10.0),
        ("2", "C1", "2010-01-02 10:00:00", "CANCELLATION", -4.0),   # never purchased
        ("3", "B", "2010-01-03 10:00:00", "SALE", 5.0),
        ("3", "C2", "2010-01-04 10:00:00", "CANCELLATION", -9.0),   # net negative
    ])
    rfm, _ = cs.compute_rfm(df)
    keep, excluded = cs.eligibility(rfm)
    assert rfm.loc[keep, "customer_id"].tolist() == ["1"]
    assert excluded == {"no_eligible_purchase": 1, "non_positive_net_value": 1, "purchase_after_reference_date": 0}


def test_feature_scaling_is_standardised_log():
    rfm = pd.DataFrame({"recency_days": [1, 10, 100, 1000], "frequency": [1, 2, 4, 8],
                        "monetary": [10.0, 100.0, 1000.0, 10000.0]})
    X, scaler = cs.prepare_features(rfm)
    assert np.allclose(X.mean(axis=0), 0) and np.allclose(X.std(axis=0), 1)
    assert np.allclose(scaler.mean_, np.log1p(rfm.to_numpy(dtype=float)).mean(axis=0))


def test_feature_validation_rejects_bad_values():
    with pytest.raises(AnalyticsParamError):
        cs.prepare_features(pd.DataFrame({"recency_days": [1, np.nan], "frequency": [1, 2], "monetary": [1.0, 2.0]}))
    with pytest.raises(AnalyticsParamError):
        cs.prepare_features(pd.DataFrame({"recency_days": [1, 2], "frequency": [1, 2], "monetary": [1.0, -2.0]}))


@pytest.mark.parametrize("k", [1, 11, "x"])
def test_cluster_count_validation(k):
    with pytest.raises(AnalyticsParamError):
        cs.validate_params({"k": k})


def test_insufficient_customers():
    X = np.zeros((2, 3))
    with pytest.raises(AnalyticsParamError, match="cannot form"):
        cs.fit_kmeans(X, 3, 42)


def test_reproducible_with_fixed_seed():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 0.3, (30, 3)), rng.normal(3, 0.3, (30, 3)), rng.normal(-3, 0.3, (30, 3))])
    _, a = cs.fit_kmeans(X, 3, 42)
    _, b = cs.fit_kmeans(X, 3, 42)
    assert (a == b).all()
    score, note = cs.silhouette(X, a, 42)
    assert score > 0.7 and note is None


def test_silhouette_undefined_cases():
    X = np.zeros((3, 3))
    assert cs.silhouette(X, np.array([0, 0, 0]), 42)[0] is None
    assert cs.silhouette(X, np.array([0, 1, 2]), 42)[0] is None


def test_segment_on_warehouse(wh_conn):
    r = cs.segment(wh_conn, {"k": 2}, save_model=False)
    rfm = {c["customer_id"]: c for c in r["customers"]}
    assert r["reference_date"] == "2010-03-03"
    assert set(rfm) == {"17850", "13047", "12583"}           # anonymous purchases never profiled
    assert rfm["17850"]["frequency"] == 2 and rfm["17850"]["monetary"] == pytest.approx(100.99)
    assert rfm["13047"]["monetary"] == pytest.approx(5.94) and rfm["13047"]["recency_days"] == 91
    assert rfm["12583"]["recency_days"] == 1 and rfm["12583"]["monetary"] == pytest.approx(32.28)
    assert sum(c["size"] for c in r["clusters"]) == 3
    assert sorted(c["cluster"] for c in r["clusters"]) == [1, 2]


def test_segment_rejects_k_larger_than_customers(wh_conn):
    with pytest.raises(AnalyticsParamError, match="eligible customers"):
        cs.segment(wh_conn, {"k": 5}, save_model=False)


def test_model_is_saved(wh_conn, loaded_warehouse):
    import json, os
    cs.segment(wh_conn, {"k": 2})
    path = cs.model_path()
    assert path.startswith(str(loaded_warehouse["tmp"]))
    m = json.load(open(path))
    assert m["params"]["k"] == 2 and len(m["cluster_centers_scaled"]) == 2 and os.path.isfile(path)
