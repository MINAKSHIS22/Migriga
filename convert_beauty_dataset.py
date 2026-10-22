#!/usr/bin/env python3
"""
UK Online Retail Dataset Bridge.
Redirects to convert_retail_dataset.py to ensure the entire project exclusively uses
the UK Online Retail dataset.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from convert_retail_dataset import load_retail_dataset, main as retail_main


def load_beauty_dataset(source_path=None, limit=None):
    """Backward-compatibility alias returning clean UK Online Retail products."""
    return load_retail_dataset(limit=limit)


def main():
    retail_main()


if __name__ == "__main__":
    main()
