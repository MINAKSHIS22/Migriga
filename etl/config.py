# MIGRIGA Analytics - ETL & Warehouse Configuration
# Paths are resolved at call time so tests and deployments can override them
# through environment variables without touching code.
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_SOURCE_CSV = os.path.join(PROJECT_ROOT, "data", "raw", "online_retail_09_10.csv")
DEFAULT_WAREHOUSE_PATH = os.path.join(PROJECT_ROOT, "data", "warehouse", "migriga_warehouse.db")

DATASET_CITATION = (
    "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. "
    "https://doi.org/10.24432/C5CG6D"
)
DATASET_LICENSE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
DATASET_NOTE = (
    "Historical transactions (Dec 2009 - Dec 2010) of a UK-based online gift retailer. "
    "These are NOT Migriga sales or Migriga customers."
)


def source_csv_path() -> str:
    return os.environ.get("MIGRIGA_SOURCE_CSV", DEFAULT_SOURCE_CSV)


def warehouse_path() -> str:
    return os.environ.get("MIGRIGA_WAREHOUSE_PATH", DEFAULT_WAREHOUSE_PATH)
