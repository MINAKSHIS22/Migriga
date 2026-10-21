# MIGRIGA Analytics - EXTRACT stage
# Reads the raw retail CSV exactly as delivered (all columns as text) and validates
# that it is readable and has the required columns. The source file is never modified.
import csv
import hashlib
import os
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = [
    "InvoiceNo", "StockCode", "Description", "Quantity",
    "InvoiceDate", "UnitPrice", "CustomerID", "Country",
]


class SourceValidationError(Exception):
    """Raised when the source file is missing, unreadable or structurally invalid."""


@dataclass
class ExtractResult:
    raw: pd.DataFrame
    meta: dict = field(default_factory=dict)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        sample = f.read(1 << 20)
    try:
        sample.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError:
        # Only fails on a truncated multibyte char at the very end of the sample,
        # or on a genuinely non-UTF-8 file. Fall back to latin-1, which never fails.
        try:
            sample[:-4].decode("utf-8")
            return "utf-8-sig"
        except UnicodeDecodeError:
            return "latin-1"


def _detect_delimiter(path: str, encoding: str) -> str:
    with open(path, "r", encoding=encoding, newline="") as f:
        sample = f.read(64 * 1024)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def extract(path: str) -> ExtractResult:
    if not path or not os.path.isfile(path):
        raise SourceValidationError(f"Source file not found: {os.path.basename(path or '') or '(none)'}")
    if os.path.getsize(path) == 0:
        raise SourceValidationError("Source file is empty.")

    encoding = _detect_encoding(path)
    delimiter = _detect_delimiter(path, encoding)
    try:
        raw = pd.read_csv(
            path, sep=delimiter, dtype=str, keep_default_na=False,
            encoding=encoding, skipinitialspace=False,
        )
    except Exception as exc:  # pandas raises several parser error types
        raise SourceValidationError(f"Source file could not be parsed as CSV: {exc.__class__.__name__}") from exc

    raw.columns = [str(c).replace("﻿", "").strip() for c in raw.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise SourceValidationError(f"Source file is missing required columns: {', '.join(missing)}")

    raw = raw[REQUIRED_COLUMNS].copy()
    # 1-based ordinal of the data record in the file; used for traceability.
    raw.insert(0, "source_row_number", range(1, len(raw) + 1))

    meta = {
        "source_file": os.path.basename(path),
        "source_size_bytes": os.path.getsize(path),
        "source_sha256": file_sha256(path),
        "encoding": encoding,
        "delimiter": delimiter,
        "rows_read": int(len(raw)),
        "columns": REQUIRED_COLUMNS,
    }
    return ExtractResult(raw=raw, meta=meta)
