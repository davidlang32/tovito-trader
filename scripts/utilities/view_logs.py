"""
View System Logs
Display recent system logs with PII protection
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sys
import os
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models import Database, SystemLog
from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)


def view_logs(days: int = 7, log_type: str = None):
    """
    View system logs
    
    Args:
        days: Number of days to look back
        log_type: Filter by log type (INFO, WARNING, ERROR, SUCCESS)
    """
    db = Database()
    session = db.get_session()
    
    try:
        # Calculate date range
        start_date = datetime.now() - timedelta(days=days)
        
        # Build query
        query = session.query(SystemLog).filter(
            SystemLog.timestamp >= start_date
        )
        
        if log_type:
            query = query.filter(SystemLog.log_type == log_type.upper())
        
        # Order by most recent first
        logs = query.order_by(SystemLog.timestamp.desc()).all()
        
        if not logs:
            print(f"\n📋 No logs found for last {days} days")
            if log_type:
                print(f"   Filter: {log_type}")
            return
        
        print(f"\n{'='*80}")
        print(f"SYSTEM LOGS - Last {days} Days")
        if log_type:
            print(f"Filter: {log_type}")
        print(f"{'='*80}\n")
        
        for log in logs:
            # Format timestamp
            time_str = log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # Color code by type
            type_emoji = {
                'SUCCESS': '✅',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🔥'
            }.get(log.log_type, '📝')
            
            print(f"{type_emoji} {time_str} | {log.category}")
            print(f"   {log.message}")
            
            if log.details:
                # Truncate long details
                details = log.details if len(log.details) < 100 else log.details[:97] + "..."
                print(f"   Details: {details}")
            
            print()
        
        print(f"{'='*80}")
        print(f"Total logs: {len(logs)}")
        print(f"{'='*80}\n")
        
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='View system logs')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    parser.add_argument('--type', choices=['INFO', 'WARNING', 'ERROR', 'SUCCESS', 'CRITICAL'],
                       help='Filter by log type')
    parser.add_argument('--today', action='store_true', help='Show only today\'s logs')
    
    args = parser.parse_args()
    
    days = 1 if args.today else args.days
    
    view_logs(days=days, log_type=args.type)
