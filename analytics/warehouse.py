# MIGRIGA Analytics - Warehouse access, shared sales policy and filter construction
# Every dashboard, OLAP, basket and segmentation query uses the definitions below so
# that "sales", "cancellations" and "eligible records" mean the same thing everywhere.
import os
import re
import sqlite3
import threading
from collections import OrderedDict
from datetime import date

from etl import config


class WarehouseUnavailable(Exception):
    """The warehouse file does not exist or has never been loaded."""


class AnalyticsParamError(ValueError):
    """A request parameter failed validation."""


# --- Shared policy ---------------------------------------------------------------
# Eligible for product sales measures: merchandise lines, not flagged duplicates,
# and either a positive sale or a cancellation (negative) line.
ELIGIBLE_SALES = "f.is_duplicate = 0 AND f.is_product = 1 AND f.line_type IN ('SALE', 'CANCELLATION')"
IS_SALE = "f.line_type = 'SALE'"
IS_CANCEL = "f.line_type = 'CANCELLATION'"

STAR_JOINS = (
    "FROM fact_sales f "
    "JOIN dim_date d ON d.date_key = f.date_key "
    "JOIN dim_product p ON p.product_key = f.product_key "
    "JOIN dim_customer cu ON cu.customer_key = f.customer_key "
    "JOIN dim_country c ON c.country_key = f.country_key "
)


def connect(path: str = None) -> sqlite3.Connection:
    path = path or config.warehouse_path()
    if not os.path.isfile(path):
        raise WarehouseUnavailable("The analytics warehouse has not been created yet. Run the ETL pipeline first.")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        n = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    except sqlite3.OperationalError:
        conn.close()
        raise WarehouseUnavailable("The analytics warehouse schema is missing. Run the ETL pipeline first.")
    if n == 0:
        conn.close()
        raise WarehouseUnavailable("The analytics warehouse is empty. Run the ETL pipeline first.")
    return conn


def data_version(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM warehouse_meta WHERE key = 'data_version'").fetchone()
    return row[0] if row else "0"


def cache_token(conn: sqlite3.Connection) -> tuple:
    """Identifies one loaded state of one warehouse file; part of every cache key."""
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    return (path, data_version(conn))


# --- Filter parsing ----------------------------------------------------------------
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(value, name):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise AnalyticsParamError(f"{name} must be a date in YYYY-MM-DD format.")
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise AnalyticsParamError(f"{name} is not a valid calendar date.")
    return int(d.strftime("%Y%m%d"))


def parse_list(value, name, max_items=50, max_len=100):
    if value in (None, "", []):
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    items = [str(i).strip() for i in items if str(i).strip()]
    if len(items) > max_items:
        raise AnalyticsParamError(f"{name} accepts at most {max_items} values.")
    if any(len(i) > max_len for i in items):
        raise AnalyticsParamError(f"{name} contains a value that is too long.")
    return items


def build_filters(filters: dict):
    """Returns (list_of_sql_conditions, params, normalized_filters) for the common dice filters."""
    filters = filters or {}
    conds, params = [], []
    dfrom = parse_date(filters.get("date_from"), "date_from")
    dto = parse_date(filters.get("date_to"), "date_to")
    if dfrom and dto and dfrom > dto:
        raise AnalyticsParamError("date_from must be on or before date_to.")
    countries = parse_list(filters.get("countries"), "countries")
    products = [p.upper() for p in parse_list(filters.get("products"), "products")]
    customers = parse_list(filters.get("customers"), "customers")
    if dfrom:
        conds.append("f.date_key >= ?")
        params.append(dfrom)
    if dto:
        conds.append("f.date_key <= ?")
        params.append(dto)
    if countries:
        conds.append(f"c.country_name IN ({','.join('?' * len(countries))})")
        params += countries
    if products:
        conds.append(f"p.stock_code IN ({','.join('?' * len(products))})")
        params += products
    if customers:
        conds.append(f"cu.customer_id IN ({','.join('?' * len(customers))})")
        params += customers
    normalized = {"date_from": filters.get("date_from") or None, "date_to": filters.get("date_to") or None,
                  "countries": countries, "products": products, "customers": customers}
    return conds, params, normalized


# --- Small result cache keyed by warehouse data version ----------------------------
class ResultCache:
    def __init__(self, max_items=128):
        self.max_items = max_items
        self._data = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        return None

    def put(self, key, value):
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def clear(self):
        with self._lock:
            self._data.clear()


cache = ResultCache()


def freeze(obj):
    """Hashable, order-stable representation of request params for cache keys."""
    if isinstance(obj, dict):
        return tuple(sorted((k, freeze(v)) for k, v in obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(freeze(v) for v in obj)
    return obj
