# Apriori tests: textbook example, brute-force cross-check, metric formulas, thresholds and
# warehouse basket construction.
import random
from itertools import combinations

import pytest

from analytics import market_basket as mb
from analytics.warehouse import AnalyticsParamError

# Tan, Steinbach & Kumar, "Introduction to Data Mining", market-basket example
TAN = [{"Bread", "Milk"}, {"Bread", "Diapers", "Beer", "Eggs"}, {"Milk", "Diapers", "Beer", "Cola"},
       {"Bread", "Milk", "Diapers", "Beer"}, {"Bread", "Milk", "Diapers", "Cola"}]


def fs(*items):
    return frozenset(items)


def brute_force(transactions, min_support, max_len):
    n = len(transactions)
    items = sorted({i for t in transactions for i in t})
    out = {}
    for k in range(1, max_len + 1):
        for combo in combinations(items, k):
            c = sum(1 for t in transactions if set(combo) <= t)
            if c / n >= min_support - 1e-12:
                out[frozenset(combo)] = c
    return out


def test_textbook_frequent_itemsets():
    freq = mb.apriori(TAN, 0.6, max_len=3)
    assert freq == {fs("Beer"): 3, fs("Bread"): 4, fs("Diapers"): 4, fs("Milk"): 4,
                    fs("Beer", "Diapers"): 3, fs("Bread", "Diapers"): 3, fs("Bread", "Milk"): 3,
                    fs("Diapers", "Milk"): 3}


def test_textbook_rule_metrics():
    freq = mb.apriori(TAN, 0.4, max_len=3)
    rules = mb.association_rules(freq, len(TAN))
    r = next(x for x in rules if x["antecedent"] == ["Diapers", "Milk"] and x["consequent"] == ["Beer"])
    assert r["support"] == pytest.approx(0.4)
    assert r["support_count"] == 2
    assert r["confidence"] == pytest.approx(2 / 3)
    assert r["lift"] == pytest.approx((2 / 3) / 0.6)
    beer_diapers = next(x for x in rules if x["antecedent"] == ["Beer"] and x["consequent"] == ["Diapers"])
    assert beer_diapers["confidence"] == pytest.approx(1.0) and beer_diapers["lift"] == pytest.approx(1.25)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_matches_brute_force_on_random_data(seed):
    rnd = random.Random(seed)
    items = list("ABCDEFGH")
    tx = [set(rnd.sample(items, rnd.randint(1, 5))) for _ in range(40)]
    for sup in (0.1, 0.25):
        assert mb.apriori(tx, sup, max_len=4) == brute_force(tx, sup, 4)


def test_thresholds_filter_rules():
    freq = mb.apriori(TAN, 0.4, max_len=3)
    all_rules = mb.association_rules(freq, len(TAN))
    strict = mb.association_rules(freq, len(TAN), min_confidence=0.75, min_lift=1.1)
    assert strict and len(strict) < len(all_rules)
    assert all(r["confidence"] >= 0.75 and r["lift"] >= 1.1 for r in strict)
    assert mb.association_rules(freq, len(TAN), min_confidence=1.01) == []


def test_max_len_limits_itemset_size():
    assert max(len(s) for s in mb.apriori(TAN, 0.2, max_len=2)) == 2
    assert max(len(s) for s in mb.apriori(TAN, 0.2, max_len=4)) >= 3


def test_pruning_trace_reports_levels():
    # {A,B} and {A,C} are frequent but {B,C} is not, so candidate {A,B,C} must be pruned without counting
    tx = [{"A", "B"}, {"A", "B"}, {"A", "C"}, {"A", "C"}, {"B"}, {"C"}]
    trace = []
    freq = mb.apriori(tx, 2 / 6, max_len=3, trace=trace)
    assert [lv["k"] for lv in trace] == [1, 2, 3]
    assert trace[1]["infrequent"] == [["B", "C"]]
    assert trace[2]["pruned_itemsets"] == [["A", "B", "C"]] and trace[2]["frequent"] == []
    assert frozenset("ABC") not in freq


def test_empty_input():
    assert mb.apriori([], 0.5) == {}


def test_parameter_validation():
    with pytest.raises(AnalyticsParamError):
        mb.validate_params({"min_support": 0.0001})
    with pytest.raises(AnalyticsParamError):
        mb.validate_params({"min_confidence": 2})
    with pytest.raises(AnalyticsParamError):
        mb.validate_params({"max_len": 9})
    with pytest.raises(AnalyticsParamError):
        mb.validate_params({"min_lift": "x"})
    assert mb.validate_params({})["min_support"] == mb.DEFAULTS["min_support"]


def test_basket_construction_from_warehouse(wh_conn):
    baskets, lines = mb.load_baskets(wh_conn)
    assert sorted(map(sorted, baskets)) == sorted([
        ["71053", "84406B", "85123A"], ["71053", "85123A"], ["22423", "85123A"],
        ["22423", "71053"], ["22423", "85123A"], ["71053", "85123A"]])
    assert lines == 13          # duplicate line counts once; POST, cancellations, zero-price excluded
    fr, _ = mb.load_baskets(wh_conn, country="France")
    assert len(fr) == 2


def test_mine_on_warehouse(wh_conn, monkeypatch):
    monkeypatch.setattr(mb, "MIN_SUPPORT_BASKETS", 1)
    r = mb.mine(wh_conn, {"min_support": 0.3, "min_confidence": 0.5, "min_lift": 0})
    assert r["n_baskets"] == 6 and r["min_support_count"] == 2
    sets = {tuple(i["items"]): i["support_count"] for i in r["itemsets"]}
    assert sets == {("85123A",): 5, ("71053",): 4, ("22423",): 3, ("71053", "85123A"): 3, ("22423", "85123A"): 2}
    rule = next(x for x in r["rules"] if x["antecedent"] == ["71053"])
    assert rule["confidence"] == pytest.approx(0.75) and rule["lift"] == pytest.approx(0.75 / (5 / 6))
    assert r["descriptions"]["85123A"] == "WHITE HANGING HEART"


def test_too_few_supporting_baskets_is_rejected(wh_conn):
    with pytest.raises(AnalyticsParamError, match="baskets"):
        mb.mine(wh_conn, {"min_support": 0.3})
