"""
Tovito Trader - ETL Pipeline
=============================
Extracts raw brokerage data, transforms it into a canonical format,
and loads it into the production trades table.

Pipeline: Extract → Transform → Load
  - extract.py:   Pull raw data from brokerage APIs into staging table
  - transform.py: Normalize staging rows into canonical trades format
  - load.py:      Insert into production trades, update ETL status
"""

from src.etl.extract import extract_from_brokerage, ingest_raw_transactions
from src.etl.transform import transform_pending
from src.etl.load import load_to_trades

__all__ = [
    'extract_from_brokerage',
    'ingest_raw_transactions',
    'transform_pending',
    'load_to_trades',
]
