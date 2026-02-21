"""
Tovito Trader - ETL Pipeline Runner
====================================
Runs the brokerage data ETL pipeline:
  1. Extract raw transactions from brokerage APIs into staging
  2. Transform staging rows into canonical format
  3. Load normalized data into production trades table

Usage:
    python scripts/trading/run_etl.py                    # Last 7 days, all providers
    python scripts/trading/run_etl.py --days 30          # Last 30 days
    python scripts/trading/run_etl.py --source tastytrade # Specific provider
    python scripts/trading/run_etl.py --dry-run           # Extract + transform only
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is in path
PROJECT_DIR = Path("C:/tovito-trader")
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Run the brokerage data ETL pipeline'
    )
    parser.add_argument(
        '--days', type=int, default=7,
        help='Number of days to look back (default: 7)'
    )
    parser.add_argument(
        '--source', type=str, default=None,
        help='Specific brokerage provider (default: all configured)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Extract and transform only — do not load into production'
    )
    args = parser.parse_args()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    logger.info("=" * 60)
    logger.info("TOVITO TRADER - ETL Pipeline")
    logger.info("=" * 60)
    logger.info("Date range: %s to %s (%d days)",
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                args.days)

    if args.source:
        logger.info("Source: %s", args.source)
    else:
        logger.info("Source: all configured providers")

    if args.dry_run:
        logger.info("Mode: DRY RUN (no production writes)")

    logger.info("-" * 60)

    try:
        if args.dry_run:
            # Extract + Transform only
            from src.etl.extract import extract_from_brokerage
            from src.etl.transform import transform_pending
            from src.api.brokerage import get_configured_providers

            providers = [args.source] if args.source else get_configured_providers()

            for provider in providers:
                logger.info("Extracting from %s...", provider)
                result = extract_from_brokerage(provider, start_date, end_date)
                logger.info("  Fetched: %d, Ingested: %d, Skipped: %d",
                            result['total'], result['ingested'], result['skipped'])

            logger.info("Transforming pending rows...")
            transform_result = transform_pending()
            logger.info("  Transformed: %d, Errors: %d, Skipped: %d",
                        len(transform_result['transformed']),
                        len(transform_result['errors']),
                        len(transform_result['skipped']))

            logger.info("DRY RUN complete — no data loaded to production trades")

        else:
            # Full pipeline
            from src.etl.load import run_full_pipeline

            stats = run_full_pipeline(
                source=args.source,
                start_date=start_date,
                end_date=end_date,
            )

            # Print summary
            logger.info("-" * 60)
            logger.info("PIPELINE SUMMARY")
            logger.info("-" * 60)

            for provider, extract_stats in stats['extract'].items():
                if 'error' in extract_stats:
                    logger.error("  Extract [%s]: FAILED - %s",
                                 provider, extract_stats['error'])
                else:
                    logger.info("  Extract [%s]: %d fetched, %d ingested, %d skipped",
                                provider,
                                extract_stats.get('total', 0),
                                extract_stats.get('ingested', 0),
                                extract_stats.get('skipped', 0))

            logger.info("  Transform: %d normalized, %d errors, %d skipped",
                        stats['transform']['transformed'],
                        stats['transform']['errors'],
                        stats['transform']['skipped'])

            logger.info("  Load: %d new trades, %d already existed, %d errors",
                        stats['load']['loaded'],
                        stats['load']['duplicates'],
                        stats['load']['load_errors'])

        logger.info("=" * 60)
        logger.info("[OK] ETL PIPELINE COMPLETED")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("ETL pipeline failed: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
