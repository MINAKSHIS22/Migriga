#!/usr/bin/env python3
"""
Convert Amazon All Beauty Parquet metadata into a frontend-friendly products.json
and provide the primary training dataset for the MIGRIGA recommendation engine.

Dependencies:
    py -m pip install pandas pyarrow fastparquet scikit-learn

Run:
    py convert_beauty_dataset.py
    py convert_beauty_dataset.py full-00000-of-00001.parquet products.json
    py convert_beauty_dataset.py --train
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PARQUET = BASE_DIR / "full-00000-of-00001.parquet"
DEFAULT_OUTPUT = BASE_DIR / "products.json"
LIMIT = 15000


def first_text(value: Any) -> str:
    """Turn a string/list/dict-like value into a readable text string."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        bits = [first_text(x) for x in value]
        return " ".join(x for x in bits if x).strip()
    if hasattr(value, "__iter__") and not isinstance(value, (dict, bytes)):
        try:
            bits = [first_text(x) for x in value]
            return " ".join(x for x in bits if x).strip()
        except Exception:
            pass
    if isinstance(value, dict):
        for key in ("text", "value", "name", "title", "description"):
            if value.get(key):
                return first_text(value[key])
        return ""
    return str(value).strip()


def image_url(value: Any) -> str:
    """Extract a usable image URL from Amazon metadata's images field (dict of arrays or list of dicts)."""
    if isinstance(value, dict):
        for key in ("large", "hi_res", "thumb"):
            arr = value.get(key)
            if hasattr(arr, "__iter__") and not isinstance(arr, (str, bytes)):
                for url in arr:
                    if isinstance(url, str) and url.startswith(("http://", "https://")):
                        return url
            elif isinstance(arr, str) and arr.startswith(("http://", "https://")):
                return arr
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, dict):
                for key in ("large", "hi_res", "thumb"):
                    url = item.get(key)
                    if isinstance(url, str) and url.startswith(("http://", "https://")):
                        return url
            elif isinstance(item, str) and item.startswith(("http://", "https://")):
                return item
    return ""


def product_category(row: Dict[str, Any]) -> str:
    text = " ".join([
        first_text(row.get("title")),
        first_text(row.get("main_category")),
        first_text(row.get("categories")),
    ]).lower()

    if any(word in text for word in ("perfume", "fragrance", "eau de parfum", "cologne", "body mist", "scent", "parfum")):
        return "Fragrance"
    if any(word in text for word in ("shampoo", "conditioner", "hair mask", "hair oil", "haircare", "hair care", "styling", "curl cream", "scalp")):
        return "Haircare"
    if any(word in text for word in ("lipstick", "mascara", "eyeliner", "foundation", "concealer", "blush", "eyeshadow", "makeup", "make-up", "nail polish", "powder", "lip gloss", "bronzer")):
        return "Makeup"
    return "Skincare"


def clean_price(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", str(value))
        if not match:
            return None
        return float(match.group(0).replace(",", ""))
    except Exception:
        return None


def load_beauty_dataset(source_path: Optional[Path] = None, limit: int = LIMIT) -> List[Dict[str, Any]]:
    """
    Loads and parses the Amazon All Beauty parquet dataset into clean, structured product dictionaries.
    """
    source = Path(source_path) if source_path else DEFAULT_PARQUET
    if not source.exists():
        raise FileNotFoundError(f"Cannot find input dataset: {source}")

    print(f"[Dataset] Loading Parquet file: {source.name} ...")
    df = pd.read_parquet(source)
    print(f"[Dataset] Read {len(df):,} source beauty metadata records.")

    products: List[Dict[str, Any]] = []
    seen = set()

    # Fast iteration over records
    for row in df.to_dict("records"):
        asin = first_text(row.get("parent_asin")) or first_text(row.get("asin"))
        title = first_text(row.get("title"))
        if not asin or not title or asin in seen:
            continue

        price = clean_price(row.get("price"))
        raw_rating = row.get("average_rating")
        try:
            rating = float(raw_rating) if raw_rating is not None and not pd.isna(raw_rating) else None
            if rating is not None and not (0 <= rating <= 5):
                rating = None
        except (TypeError, ValueError):
            rating = None

        description = first_text(row.get("description")) or first_text(row.get("features"))
        brand = first_text(row.get("store")) or "MIGRIGA Selected"
        image = image_url(row.get("images"))
        raw_rc = row.get("rating_number")
        try:
            rating_count = int(raw_rc) if raw_rc is not None and not pd.isna(raw_rc) else 0
        except (TypeError, ValueError):
            rating_count = 0

        # Keep products useful for storefront & ML recommendations
        if not (price is not None or image or description or rating is not None):
            continue

        category = product_category(row)

        products.append({
            "id": asin,
            "name": title,
            "brand": brand,
            "category": category,
            "category_name": category,
            "price": price,
            "rating": rating,
            "ratingCount": rating_count,
            "description": description,
            "image": image,
            "source": "Amazon All Beauty Dataset"
        })
        seen.add(asin)

        if len(products) >= limit:
            break

    print(f"[Dataset] Extracted {len(products):,} clean unique beauty products.")
    return products


def main():
    should_train = "--train" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--train"]

    source = Path(args[0]) if len(args) > 0 else DEFAULT_PARQUET
    output = Path(args[1]) if len(args) > 1 else DEFAULT_OUTPUT

    products = load_beauty_dataset(source_path=source, limit=LIMIT)
    output.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Export] Saved {len(products):,} unique products to {output.resolve()}")

    # Run recommendation model training directly on this dataset
    print("\n" + "=" * 65)
    print("  TRIGGERING AI MODEL TRAINING ON convert_beauty_dataset.py")
    print("=" * 65)
    try:
        from backend.train_recommendation import train_on_beauty_dataset
        train_on_beauty_dataset(products)
    except Exception as e:
        print(f"[Notice] Model training invocation: {e}")


if __name__ == "__main__":
    main()
