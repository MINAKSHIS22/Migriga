# MIGRIGA Analytics - Market Basket Analysis with the Apriori algorithm
#
# Apriori (Agrawal & Srikant, 1994) mines frequent itemsets level by level:
#   L1 = frequent single items; C(k) = join L(k-1) with itself on a shared (k-2)-prefix,
#   then PRUNE every candidate having an infrequent (k-1)-subset (downward closure);
#   L(k) = candidates whose support >= min_support.
# Support counting uses a vertical bitmap per item (bit i set = basket i contains the item),
# so support(itemset) = popcount(AND of the item bitmaps). This changes only how the counting
# is done, not which itemsets Apriori generates or keeps.
from itertools import combinations

import numpy as np

from .warehouse import AnalyticsParamError, IS_SALE, data_version

MAX_CANDIDATES = 3_000_000
MIN_SUPPORT_BASKETS = 5   # an itemset seen in fewer baskets is too thin to report as a pattern
MAX_RESULTS = 2000

BOUNDS = {
    "min_support": (0.003, 1.0),
    "min_confidence": (0.01, 1.0),
    "min_lift": (0.0, 1000.0),
    "max_len": (2, 4),
}
DEFAULTS = {"min_support": 0.01, "min_confidence": 0.3, "min_lift": 1.0, "max_len": 3, "country": None}


def validate_params(params: dict, bounds: dict = BOUNDS) -> dict:
    p = {**DEFAULTS, **{k: v for k, v in (params or {}).items() if v is not None and v != ""}}
    out = {}
    for name in ("min_support", "min_confidence", "min_lift"):
        try:
            out[name] = float(p[name])
        except (TypeError, ValueError):
            raise AnalyticsParamError(f"{name} must be a number.")
        lo, hi = bounds[name]
        if not lo <= out[name] <= hi:
            raise AnalyticsParamError(f"{name} must be between {lo} and {hi}.")
    try:
        out["max_len"] = int(p["max_len"])
    except (TypeError, ValueError):
        raise AnalyticsParamError("max_len must be an integer.")
    lo, hi = bounds["max_len"]
    if not lo <= out["max_len"] <= hi:
        raise AnalyticsParamError(f"max_len must be between {lo} and {hi}.")
    country = p.get("country")
    if country is not None and (not isinstance(country, str) or len(country) > 100):
        raise AnalyticsParamError("country must be a country name.")
    out["country"] = country or None
    return out


# --- Basket construction -------------------------------------------------------------
def load_baskets(conn, country=None):
    """Eligible baskets: one per invoice with >= 1 merchandise SALE line (no cancellations,
    returns, adjustments, zero-price lines, fees/postage or flagged duplicates). Each item
    counts once per basket however many lines it appears on."""
    sql = ("SELECT f.invoice_no, p.stock_code FROM fact_sales f "
           "JOIN dim_product p ON p.product_key = f.product_key "
           "JOIN dim_country c ON c.country_key = f.country_key "
           f"WHERE {IS_SALE} AND f.is_product = 1 AND f.is_duplicate = 0")
    args = []
    if country:
        sql += " AND c.country_name = ?"
        args.append(country)
    sql += " GROUP BY f.invoice_no, p.stock_code"
    baskets = {}
    lines = 0
    for inv, code in conn.execute(sql, args):
        baskets.setdefault(inv, set()).add(code)
        lines += 1
    return list(baskets.values()), lines


# --- Apriori core (pure, dataset-agnostic) -------------------------------------------
def _bitmaps(transactions):
    """item -> python int bitmap over transaction indices."""
    index = {}
    for t_idx, items in enumerate(transactions):
        for it in items:
            index.setdefault(it, []).append(t_idx)
    n = len(transactions)
    maps = {}
    for it, idxs in index.items():
        arr = np.zeros(n, dtype=bool)
        arr[idxs] = True
        maps[it] = int.from_bytes(np.packbits(arr, bitorder="little").tobytes(), "little")
    return maps


def apriori(transactions, min_support, max_len=3, progress=None, trace=None):
    """Returns {frozenset(itemset): support_count} for all itemsets with support >= min_support.
    If `trace` is a list, one entry per level is appended (candidates, pruned, frequent) - used by
    the DWM Lab to show the algorithm step by step on small inputs."""
    n = len(transactions)
    if n == 0:
        return {}
    min_count = max(1, int(np.ceil(min_support * n - 1e-9)))
    report = progress or (lambda msg, pct: None)

    maps = _bitmaps(transactions)
    level = {}
    for it, bm in maps.items():
        c = bm.bit_count()
        if c >= min_count:
            level[(it,)] = bm
    frequent = {frozenset(k): v.bit_count() for k, v in level.items()}
    report(f"L1: {len(level)} frequent items", 20)
    if trace is not None:
        trace.append({"k": 1, "candidates": len(maps), "pruned": 0,
                      "infrequent": sorted([it] for it, bm in maps.items() if bm.bit_count() < min_count),
                      "frequent": sorted([list(key), level[key].bit_count()] for key in level)})

    k = 2
    while level and k <= max_len:
        prev_keys = sorted(level)
        prev_set = set(prev_keys)
        # Join step: itemsets sharing the first k-2 items
        groups = {}
        for key in prev_keys:
            groups.setdefault(key[:-1], []).append(key)
        n_candidates = sum(len(g) * (len(g) - 1) // 2 for g in groups.values())
        if n_candidates > MAX_CANDIDATES:
            raise AnalyticsParamError(
                f"Minimum support is too low: level {k} would generate {n_candidates:,} candidates "
                f"(limit {MAX_CANDIDATES:,}). Increase min_support or reduce max_len.")
        new_level, pruned, infrequent = {}, [], []
        for members in groups.values():
            for i in range(len(members)):
                a = members[i]
                bm_a = level[a]
                for j in range(i + 1, len(members)):
                    cand = a + (members[j][-1],)
                    # Prune step: every (k-1)-subset must be frequent
                    if k > 2 and any(sub not in prev_set for sub in combinations(cand, k - 1)):
                        if trace is not None:
                            pruned.append(list(cand))
                        continue
                    bm = bm_a & level[members[j]]
                    if bm.bit_count() >= min_count:
                        new_level[cand] = bm
                    elif trace is not None:
                        infrequent.append(list(cand))
        for key, bm in new_level.items():
            frequent[frozenset(key)] = bm.bit_count()
        report(f"L{k}: {len(new_level)} frequent itemsets from {n_candidates:,} candidates", 20 + 25 * (k - 1))
        if trace is not None:
            trace.append({"k": k, "candidates": n_candidates, "pruned": len(pruned), "pruned_itemsets": pruned,
                          "infrequent": infrequent,
                          "frequent": sorted([list(key), bm.bit_count()] for key, bm in new_level.items())})
        level = new_level
        k += 1
    return frequent


def association_rules(frequent, n_transactions, min_confidence=0.0, min_lift=0.0):
    """All rules A -> C with A ∪ C frequent, A ∩ C = ∅, meeting the confidence and lift thresholds."""
    rules = []
    for itemset, count in frequent.items():
        if len(itemset) < 2:
            continue
        items = sorted(itemset)
        for r in range(1, len(items)):
            for ante in combinations(items, r):
                a = frozenset(ante)
                c = itemset - a
                conf = count / frequent[a]
                if conf < min_confidence:
                    continue
                sup_c = frequent[c] / n_transactions
                lift = conf / sup_c
                if lift < min_lift:
                    continue
                rules.append({
                    "antecedent": sorted(a), "consequent": sorted(c),
                    "support": count / n_transactions, "support_count": count,
                    "confidence": conf, "lift": lift,
                    "antecedent_support": frequent[a] / n_transactions,
                    "consequent_support": sup_c,
                })
    rules.sort(key=lambda r: (-r["lift"], -r["confidence"], -r["support"], r["antecedent"], r["consequent"]))
    return rules


# --- Warehouse-backed mining job -------------------------------------------------------
def mine(conn, params: dict, progress=None) -> dict:
    p = validate_params(params)
    report = progress or (lambda msg, pct: None)
    report("Building baskets from fact_sales", 5)
    baskets, lines = load_baskets(conn, p["country"])
    n = len(baskets)
    if n == 0:
        return {"params": p, "n_baskets": 0, "n_items": 0, "itemsets": [], "rules": [],
                "message": "No eligible baskets for the selected filters."}

    min_count = max(1, int(np.ceil(p["min_support"] * n - 1e-9)))
    if min_count < MIN_SUPPORT_BASKETS:
        raise AnalyticsParamError(
            f"Only {n:,} eligible baskets: min_support {p['min_support']} means just {min_count} basket(s) per itemset. "
            f"Raise min_support to at least {MIN_SUPPORT_BASKETS / n:.3f} so every pattern is seen in "
            f">= {MIN_SUPPORT_BASKETS} baskets.")
    frequent = apriori(baskets, p["min_support"], p["max_len"], progress=report)
    report("Generating association rules", 85)
    rules = association_rules(frequent, n, p["min_confidence"], p["min_lift"])

    descriptions = dict(conn.execute("SELECT stock_code, description FROM dim_product").fetchall())
    itemsets = sorted(({"items": sorted(s), "size": len(s), "support_count": c, "support": c / n}
                       for s, c in frequent.items()), key=lambda x: (-x["support"], x["items"]))
    size_counts = {}
    for s in frequent:
        size_counts[len(s)] = size_counts.get(len(s), 0) + 1
    sizes = [len(b) for b in baskets]
    used = {it for s in frequent for it in s}
    return {
        "params": p,
        "data_version": data_version(conn),
        "n_baskets": n,
        "n_basket_lines": lines,
        "n_items": len({it for b in baskets for it in b}),
        "avg_basket_size": round(float(np.mean(sizes)), 2),
        "median_basket_size": float(np.median(sizes)),
        "min_support_count": min_count,
        "n_frequent_itemsets": len(frequent),
        "itemsets_by_size": {str(k): v for k, v in sorted(size_counts.items())},
        "n_rules": len(rules),
        "itemsets": itemsets[:MAX_RESULTS],
        "rules": rules[:MAX_RESULTS],
        "results_truncated": len(rules) > MAX_RESULTS or len(itemsets) > MAX_RESULTS,
        "descriptions": {code: descriptions.get(code, code) for code in used},
    }
