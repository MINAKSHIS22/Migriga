# MIGRIGA Retail - Recommendation Engine Module
# Hybrid Recommendation: Market Basket Co-Occurrence + Content-Based TF-IDF Similarity
import os
import json
import sqlite3
import math
import re
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
CACHE_FILE = os.path.join(BACKEND_DIR, "recommendations_cache.json")
DB_PATH = os.path.join(BASE_DIR, "migriga.db")


class RecommendationEngine:
    def __init__(self):
        self.collaborative_rules: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.content_rules: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.hybrid_recommendations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.trending_products: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "status": "uninitialized",
            "model_type": "Hybrid (Market Basket Co-Occurrence + TF-IDF)",
            "trained_at": None,
            "total_transactions_analyzed": 0,
            "total_products_indexed": 0,
            "coverage_percent": 0.0,
            "dataset_source": "UK Online Retail Dataset"
        }
        self.load_cache()

    def get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def load_cache(self) -> bool:
        """Loads precomputed recommendation matrix from JSON cache if available."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.hybrid_recommendations = data.get("recommendations", {})
                    self.trending_products = data.get("trending", [])
                    self.metadata = data.get("metadata", self.metadata)
                    return True
            except Exception as e:
                print(f"[RecEngine] Warning loading cache: {e}")
        return False

    def save_cache(self):
        """Saves precomputed recommendation matrix and model metrics to JSON cache."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "metadata": self.metadata,
                    "recommendations": self.hybrid_recommendations,
                    "trending": self.trending_products
                }, f, indent=2, ensure_ascii=False)
            print(f"[RecEngine] Cache successfully saved to {CACHE_FILE}")
        except Exception as e:
            print(f"[RecEngine] Error saving cache: {e}")

    def get_product_details_from_db(self, product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetches product cards for list of IDs from SQLite database."""
        if not product_ids:
            return {}
        conn = self.get_db()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in product_ids)
        cursor.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", product_ids)
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for r in rows:
            p = dict(r)
            p["shades"] = json.loads(p["shades_json"]) if p.get("shades_json") else None
            p["sizes"] = json.loads(p["sizes_json"]) if p.get("sizes_json") else None
            p["benefits"] = json.loads(p["benefits_json"]) if p.get("benefits_json") else []
            p["isBestseller"] = bool(p["is_bestseller"])
            p["isNew"] = bool(p["is_new"])
            result[p["id"]] = p
        return result

    def get_all_db_products(self) -> List[Dict[str, Any]]:
        """Retrieves all current products in database for cold-start and fallback recommendations."""
        conn = self.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY is_bestseller DESC, rating DESC")
        rows = cursor.fetchall()
        conn.close()

        products = []
        for r in rows:
            p = dict(r)
            p["shades"] = json.loads(p["shades_json"]) if p.get("shades_json") else None
            p["sizes"] = json.loads(p["sizes_json"]) if p.get("sizes_json") else None
            p["benefits"] = json.loads(p["benefits_json"]) if p.get("benefits_json") else []
            p["isBestseller"] = bool(p["is_bestseller"])
            p["isNew"] = bool(p["is_new"])
            products.append(p)
        return products

    def normalize_id(self, product_id: str) -> str:
        """Resolves both '22423' and 'ret-22423'."""
        if not product_id:
            return ""
        if product_id in self.hybrid_recommendations:
            return product_id
        prefixed = f"ret-{product_id.lower()}"
        if prefixed in self.hybrid_recommendations:
            return prefixed
        unprefixed = product_id.replace("ret-", "")
        if unprefixed in self.hybrid_recommendations:
            return unprefixed
        return product_id

    def get_recommendations_for_product(self, product_id: str, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Returns top-N recommendations for a specific product.
        Uses precomputed hybrid model recommendations if available,
        otherwise falls back to category-based market basket similarity.
        """
        norm_id = self.normalize_id(product_id)
        rec_entries = self.hybrid_recommendations.get(norm_id, [])
        rec_ids = [entry["id"] for entry in rec_entries if entry["id"] != norm_id][:limit]

        # Fetch product metadata from DB
        product_dict = self.get_product_details_from_db(rec_ids)
        results = []

        for entry in rec_entries:
            pid = entry["id"]
            if pid in product_dict and pid != norm_id:
                p = dict(product_dict[pid])
                p["recommendation_score"] = entry.get("score", 0.85)
                p["recommendation_reason"] = entry.get("reason", "Frequently Bought Together in UK Retail")
                p["reason"] = p["recommendation_reason"]
                p["shared_invoices"] = entry.get("shared_invoices", 0)
                results.append(p)
                if len(results) >= limit:
                    break

        # Fallback if recommendations are insufficient (cold-start)
        if len(results) < limit:
            all_products = self.get_all_db_products()
            target_cat = None
            for p in all_products:
                if p["id"] == norm_id:
                    target_cat = p.get("category")
                    break

            existing_ids = {r["id"] for r in results} | {norm_id}
            # Add same-category items first
            if target_cat:
                for p in all_products:
                    if p["id"] not in existing_ids and p.get("category") == target_cat:
                        p_copy = dict(p)
                        p_copy["recommendation_score"] = 0.78
                        p_copy["recommendation_reason"] = f"Matching {p.get('category_name', 'Retail')} Collection"
                        results.append(p_copy)
                        existing_ids.add(p["id"])
                        if len(results) >= limit:
                            break

            # Add popular items if still not enough
            if len(results) < limit:
                for p in all_products:
                    if p["id"] not in existing_ids:
                        p_copy = dict(p)
                        p_copy["recommendation_score"] = 0.70
                        p_copy["recommendation_reason"] = "British Heritage Living Bestseller"
                        results.append(p_copy)
                        existing_ids.add(p["id"])
                        if len(results) >= limit:
                            break

        return results[:limit]

    def get_cart_recommendations(self, cart_ids: List[str], limit: int = 4) -> List[Dict[str, Any]]:
        """
        Returns smart cross-sell recommendations tailored to items currently in the user's shopping bag.
        Aggregates co-occurrence scores across all basket items.
        """
        if not cart_ids:
            return self.get_trending_products(limit)

        norm_cart = [self.normalize_id(cid) for cid in cart_ids]
        cart_set = set(norm_cart)
        candidate_scores = defaultdict(float)
        reasons = {}

        for cid in norm_cart:
            rec_entries = self.hybrid_recommendations.get(cid, [])
            for entry in rec_entries:
                rec_id = entry["id"]
                if rec_id not in cart_set:
                    candidate_scores[rec_id] += entry.get("score", 1.0)
                    if rec_id not in reasons:
                        reasons[rec_id] = entry.get("reason", "Frequently Bought Together in UK Retail")

        ranked_ids = sorted(candidate_scores.keys(), key=lambda x: candidate_scores[x], reverse=True)[:limit]
        product_dict = self.get_product_details_from_db(ranked_ids)

        results = []
        for pid in ranked_ids:
            if pid in product_dict:
                p = dict(product_dict[pid])
                p["recommendation_score"] = round(candidate_scores[pid], 3)
                p["recommendation_reason"] = reasons.get(pid, "Market Basket Co-Occurrence")
                results.append(p)

        # Fallback if cart recs are fewer than limit
        if len(results) < limit:
            trending = self.get_trending_products(limit * 2)
            for p in trending:
                if p["id"] not in cart_set and p["id"] not in [r["id"] for r in results]:
                    results.append(p)
                    if len(results) >= limit:
                        break

        return results[:limit]

    def get_trending_products(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Returns top trending / most popular products based on transaction volume or ratings."""
        if self.trending_products:
            trend_ids = [t["id"] for t in self.trending_products][:limit]
            p_dict = self.get_product_details_from_db(trend_ids)
            results = []
            for t in self.trending_products:
                pid = t["id"]
                if pid in p_dict:
                    p = dict(p_dict[pid])
                    p["recommendation_reason"] = t.get("reason", "UK Retail Community Favorite")
                    results.append(p)
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                return results

        # Fallback to DB bestsellers
        all_prods = self.get_all_db_products()
        for p in all_prods:
            if "recommendation_reason" not in p:
                p["recommendation_reason"] = "Heritage Bestseller"
        return all_prods[:limit]


# Global recommendation engine instance
rec_engine = RecommendationEngine()
engine = rec_engine
