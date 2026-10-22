#!/usr/bin/env python3
"""
Convert UK Online Retail Dataset (online_retail_09_10.csv / migriga_warehouse.db)
into a frontend-friendly products.json and provide the training dataset for the
MIGRIGA recommendation engine.
"""
import json
import os
import re
import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
WAREHOUSE_DB = BASE_DIR / "data" / "warehouse" / "migriga_warehouse.db"
SOURCE_CSV = BASE_DIR / "data" / "raw" / "online_retail_09_10.csv"
DEFAULT_OUTPUT = BASE_DIR / "products.json"


def clean_title(raw_desc: str) -> str:
    """Format ALL-CAPS retail stock description into clean, readable title case."""
    if not raw_desc or raw_desc.strip() == "UNKNOWN DESCRIPTION":
        return "Classic Heritage Retail Item"
    cleaned = re.sub(r"\s+", " ", raw_desc.strip())
    # Keep acronyms and numbers looking right
    words = cleaned.split(" ")
    title_words = []
    for w in words:
        if w.upper() in ("UK", "T-LIGHT", "LED", "PC", "SET/5", "SET/3", "SET/6", "SET/4", "SET/12", "DIY", "3D"):
            title_words.append(w.upper())
        elif len(w) <= 2 and w.isupper():
            title_words.append(w.upper())
        else:
            title_words.append(w.capitalize())
    return " ".join(title_words)


def product_category(desc: str) -> str:
    """Classify retail products into 4 balanced retail store categories."""
    d = (desc or "").lower()
    if any(k in d for k in (
        "cake", "tea", "mug", "cup", "bowl", "dish", "baking", "jug", "plate",
        "cutlery", "spoon", "fork", "knife", "kitchen", "apron", "coasters",
        "lunch", "glass", "pot", "bottle", "cookie", "jar", "tin", "teapot",
        "saucer", "placemat", "pantry", "baking case", "sugar", "creamer", "toast"
    )):
        return "Kitchen & Dining"

    if any(k in d for k in (
        "t-light", "candle", "holder", "lantern", "cushion", "clock", "frame",
        "mat", "door", "mirror", "light", "lamp", "wicker", "sign", "hook",
        "hanger", "drawer", "vase", "heart", "chilli lights", "cabinet",
        "garland", "scented", "wall art", "shelf", "storage box", "memoboard"
    )):
        return "Home & Living"

    if any(k in d for k in (
        "bag", "parasol", "umbrella", "union jack", "vintage", "flag", "shopper",
        "tote", "luggage", "wallet", "purse", "retro", "suki", "travel",
        "handbag", "pouch", "backpack", "cases", "scarf", "tie rack", "suit"
    )):
        return "Vintage & Accessories"

    return "Gifts & Keepsakes"


def category_slug(category: str) -> str:
    mapping = {
        "Kitchen & Dining": "kitchen",
        "Home & Living": "homeware",
        "Vintage & Accessories": "vintage",
        "Gifts & Keepsakes": "gifts"
    }
    return mapping.get(category, "gifts")


def default_product_image(category: str, stock_code: str) -> str:
    """Assign appropriate category or themed asset fallback."""
    cat_slug = category_slug(category)
    return f"assets/images/cat-{cat_slug}.jpg"


def load_retail_dataset(warehouse_path: Optional[Path] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Extracts all merchandise products from the UK Online Retail warehouse database
    with aggregated transaction metrics (unit price, total sales, volume, order counts).
    """
    db_file = Path(warehouse_path) if warehouse_path else WAREHOUSE_DB
    if not db_file.exists():
        raise FileNotFoundError(f"Cannot find warehouse database at {db_file}")

    print(f"[Dataset] Loading UK Retail warehouse data from: {db_file.name} ...")
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    query = """
    SELECT 
        p.stock_code,
        p.description,
        COUNT(DISTINCT f.invoice_no) as num_invoices,
        SUM(f.quantity) as total_units_sold,
        ROUND(AVG(f.unit_price), 2) as avg_unit_price,
        ROUND(MAX(f.unit_price), 2) as max_unit_price,
        ROUND(SUM(f.line_amount), 2) as total_revenue
    FROM dim_product p
    JOIN fact_sales f ON p.product_key = f.product_key
    WHERE f.is_product = 1 
      AND f.line_type = 'SALE' 
      AND f.unit_price > 0 
      AND p.description != 'UNKNOWN DESCRIPTION'
    GROUP BY p.stock_code
    HAVING total_units_sold > 0
    ORDER BY total_revenue DESC
    """
    if limit:
        query += f" LIMIT {int(limit)}"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    print(f"[Dataset] Aggregated {len(rows):,} merchandise products from UK Online Retail transactions.")

    products: List[Dict[str, Any]] = []
    for r in rows:
        code, raw_desc, invoices, units, avg_price, max_price, revenue = r
        clean_name = clean_title(raw_desc)
        cat = product_category(raw_desc)
        slug = category_slug(cat)

        # Realistic retail consumer price in GBP £
        retail_price = round(float(avg_price if avg_price and avg_price > 0.4 else 2.95), 2)
        # Original comparison price (+25% to 35%)
        original_price = round(retail_price * 1.30, 2)

        # Rating: popular items have 4.7 - 5.0, others 4.4 - 4.8
        rating = 4.9 if units > 5000 else (4.8 if units > 1000 else (4.7 if units > 200 else 4.6))
        rating_count = max(int(invoices), 12)

        products.append({
            "id": str(code),
            "stock_code": str(code),
            "name": clean_name,
            "raw_description": raw_desc,
            "brand": "MIGRIGA Heritage Retail UK",
            "category": slug,
            "category_name": cat,
            "price": retail_price,
            "original_price": original_price,
            "rating": rating,
            "ratingCount": rating_count,
            "review_count": rating_count,
            "units_sold": int(units),
            "invoices_count": int(invoices),
            "total_revenue": float(revenue),
            "description": f"Authentic British retail collection: {clean_name}. Sourced from historical UK retail catalogue transactions.",
            "image": default_product_image(cat, code),
            "source": "UK Online Retail Dataset (UCI Machine Learning Repository)"
        })

    return products


def main():
    should_train = "--train" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--train"]

    output = Path(args[0]) if len(args) > 0 else DEFAULT_OUTPUT

    products = load_retail_dataset()
    output.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Export] Saved {len(products):,} unique UK retail products to {output.resolve()}")

    if should_train or "--train" in sys.argv:
        print("\n" + "=" * 65)
        print("  TRIGGERING AI MODEL TRAINING ON UK RETAIL DATASET")
        print("=" * 65)
        try:
            from backend.train_recommendation import train_on_retail_dataset
            train_on_retail_dataset()
        except Exception as e:
            print(f"[Notice] Model training invocation: {e}")


if __name__ == "__main__":
    main()
