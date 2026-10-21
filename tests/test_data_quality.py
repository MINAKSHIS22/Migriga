# Data tests: extraction, validation, cleaning, classification and duplicate handling
import hashlib

import pandas as pd
import pytest

from etl.extract import REQUIRED_COLUMNS, SourceValidationError, extract
from etl.transform import (ADJUSTMENT, CANCELLATION, SALE, STOCK_ADJUSTMENT, ZERO_PRICE, classify_lines,
                           clean_description, normalize_customer_id, parse_dates, transform)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_extract_reads_all_rows_as_text(sample_csv):
    ex = extract(sample_csv)
    assert ex.meta["rows_read"] == 22
    assert list(ex.raw.columns) == ["source_row_number"] + REQUIRED_COLUMNS
    assert ex.raw["Quantity"].iloc[15] == "abc"          # kept verbatim, not coerced
    assert ex.raw["source_row_number"].tolist() == list(range(1, 23))


def test_missing_source_file_fails_clearly(tmp_path):
    with pytest.raises(SourceValidationError, match="not found"):
        extract(str(tmp_path / "nope.csv"))


def test_empty_file_fails(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(SourceValidationError, match="empty"):
        extract(str(p))


def test_required_columns_validated(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("InvoiceNo,StockCode,Quantity\n1,A,2\n")
    with pytest.raises(SourceValidationError, match="missing required columns"):
        extract(str(p))


def test_utf8_bom_header_is_handled(tmp_path, sample_csv):
    p = tmp_path / "bom.csv"
    p.write_bytes(b"\xef\xbb\xbf" + open(sample_csv, "rb").read())
    ex = extract(str(p))
    assert ex.raw.columns[1] == "InvoiceNo"


def test_raw_source_is_never_modified(loaded_warehouse):
    before = sha(loaded_warehouse["csv"])
    from etl.run_etl import run_etl
    run_etl(force=True)
    assert sha(loaded_warehouse["csv"]) == before


def test_customer_id_normalisation_never_invents_ids():
    assert normalize_customer_id("13085") == "13085"
    assert normalize_customer_id("13085.0") == "13085"
    assert normalize_customer_id(" 13085 ") == "13085"
    assert normalize_customer_id("") is None
    assert normalize_customer_id("nan") is None
    assert normalize_customer_id("ABC12") is None


def test_description_cleaning():
    assert clean_description("  WHITE  HANGING HEART ") == "WHITE HANGING HEART"
    assert clean_description("   ") is None


def test_date_parsing_handles_source_and_iso_formats():
    s = pd.Series(["12/1/2009 7:45", "2010-01-05 11:30:00", "not a date"])
    d = parse_dates(s)
    assert d.iloc[0] == pd.Timestamp("2009-12-01 07:45")
    assert d.iloc[1] == pd.Timestamp("2010-01-05 11:30")
    assert pd.isna(d.iloc[2])


def test_line_classification():
    inv = pd.Series(["1", "C2", "3", "4", "A5", "C6"])
    qty = pd.Series([2, -1, -5, 3, 1, 4])
    price = pd.Series([1.0, 1.0, 0.0, 0.0, -10.0, 1.0])
    assert classify_lines(inv, qty, price).tolist() == [
        SALE, CANCELLATION, STOCK_ADJUSTMENT, ZERO_PRICE, ADJUSTMENT, ADJUSTMENT]


def test_transform_rejects_invalid_rows_with_reasons(sample_csv):
    tr = transform(extract(sample_csv).raw)
    reasons = dict(zip(tr.rejected["source_row_number"], tr.rejected["reason"]))
    assert reasons == {16: "invalid_quantity", 17: "invalid_invoice_date", 18: "missing_stock_code"}
    assert tr.quality["rows_rejected"] == 3
    assert tr.quality["rows_accepted"] == 19


def test_transform_classifies_and_flags(sample_csv):
    tr = transform(extract(sample_csv).raw)
    f = tr.facts
    assert f["line_type"].value_counts().to_dict() == {
        SALE: 15, CANCELLATION: 1, STOCK_ADJUSTMENT: 1, ZERO_PRICE: 1, ADJUSTMENT: 1}
    # POST is a non-product line; B (bad debt) too
    assert set(f.loc[f["is_product"] == 0, "stock_code"]) == {"POST", "B"}
    # Lower-case stock code is normalised to the same product
    assert "85123a" not in set(f["stock_code"]) and tr.quality["stock_codes_case_normalized"] == 1
    # Missing CustomerID stays missing (anonymous) and '17850.0' maps to '17850'
    assert f["customer_id"].isna().sum() == 4
    assert (f["customer_id"] == "17850").sum() == 7


def test_duplicate_policy_flags_second_occurrence_only(sample_csv):
    tr = transform(extract(sample_csv).raw)
    f = tr.facts
    dup = f[f["is_duplicate"] == 1]
    assert len(dup) == 1 and dup.iloc[0]["source_row_number"] == 4
    assert f["line_fingerprint"].is_unique                    # distinct lines keep distinct identities
    assert tr.quality["exact_duplicate_rows_raw"] == 1


def test_fingerprints_are_deterministic(sample_csv):
    a = transform(extract(sample_csv).raw).facts["line_fingerprint"].tolist()
    b = transform(extract(sample_csv).raw).facts["line_fingerprint"].tolist()
    assert a == b


def test_canonical_description_and_dimensions(sample_csv):
    tr = transform(extract(sample_csv).raw)
    prod = tr.products.set_index("stock_code")
    assert prod.loc["85123A", "description"] == "WHITE HANGING HEART"
    assert prod.loc["21733", "description"] == "UNKNOWN DESCRIPTION"
    assert prod.loc["POST", "item_class"] == "SERVICE_OR_FEE"
    assert set(tr.customers["customer_id"]) == {"17850", "13047", "12583"}
    assert tr.countries == ["France", "United Kingdom"]
    assert tr.dates["date_key"].min() == 20091201 and tr.dates["date_key"].max() == 20100302
