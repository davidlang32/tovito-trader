"""
Tovito Trader - Enhanced Daily Runner
======================================

Runs daily NAV update with retry logic for network failures.

Features:
- Network connectivity check before attempting
- Retry hourly if fails (configurable)
- Max retries configurable
- Logs all attempts
- Works with Windows Task Scheduler

Usage:
    python scripts/daily_runner.py
    
Or for testing:
    python scripts/daily_runner.py --test
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sys
import os
from datetime import datetime, time as dt_time
import time
import socket

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.automation.nav_calculator import NAVCalculator
from src.database.models import Database, SystemLog
from src.utils.safe_logging import get_safe_logger
from dotenv import load_dotenv

# Import backup functionality
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from backup_database import DatabaseBackup

load_dotenv()

logger = get_safe_logger(__name__, log_file='logs/daily_runner.log')


class DailyRunner:
    """Enhanced daily NAV update with retry logic"""
    
    def __init__(self):
        self.calculator = NAVCalculator()
        self.db = Database()
        self.backup_manager = DatabaseBackup()
        self.max_retries = int(os.getenv('MAX_RETRIES', 8))  # 8 hours of retries
        self.retry_interval = int(os.getenv('RETRY_INTERVAL_MINUTES', 60))  # 60 min = 1 hour
    
    def check_internet_connection(self) -> bool:
        """
        Check if we have internet connectivity
        
        Returns:
            bool: True if connected
        """
        try:
            # Try to connect to Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False
    
    def log_to_database(self, log_type: str, message: str, details: str = None):
        """Log event to database"""
        session = self.db.get_session()
        try:
            log = SystemLog(
                log_type=log_type,
                category='DailyRunner',
                message=message,
                details=details
            )
            session.add(log)
            session.commit()
        except:
            pass  # Don't fail if logging fails
        finally:
            session.close()
    
    def run_nav_update(self) -> bool:
        """
        Attempt to run NAV update
        
        Returns:
            bool: True if successful
        """
        try:
            print(f"\n{'='*60}")
            print(f"DAILY NAV UPDATE ATTEMPT")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            # Step 1: Check internet
            print("🌐 Checking internet connection...")
            if not self.check_internet_connection():
                print("❌ No internet connection detected")
                logger.warning("NAV update skipped - no internet")
                self.log_to_database('WARNING', 'NAV update skipped - no internet connection')
                return False
            
            print("✅ Internet connection OK")
            
            # Step 2: Run NAV update
            print("\n📈 Running NAV update...")
            result = self.calculator.fetch_and_update_nav()
            
            if result['status'] == 'success':
                print(f"\n✅ NAV UPDATE SUCCESSFUL!")
                print(f"   Portfolio Value: $***")
                print(f"   NAV per Share: $***")
                print(f"   Daily Change: $***")
                
                logger.info("NAV update successful")
                self.log_to_database('SUCCESS', 'Daily NAV update completed successfully')
                
                return True
            else:
                print(f"\n❌ NAV update failed: {result.get('error')}")
                logger.error("NAV update failed", error=result.get('error'))
                self.log_to_database('ERROR', 'NAV update failed', result.get('error'))
                return False
        
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            logger.error("NAV update crashed", error=str(e))
            self.log_to_database('ERROR', 'NAV update crashed', str(e))
            return False
    
    def run_validation(self) -> bool:
        """Run data validation"""
        try:
            print("\n🔍 Running validation...")
            validation = self.calculator.validate_data()
            
            if validation['valid']:
                print("✅ Validation passed")
                return True
            else:
                print("⚠️  Validation warnings:")
                for error in validation['errors']:
                    print(f"   - {error}")
                logger.warning("Validation warnings", details=str(validation['errors']))
                return False
        except Exception as e:
            print(f"❌ Validation failed: {str(e)}")
            logger.error("Validation failed", error=str(e))
            return False
    
    def create_backup(self) -> bool:
        """Create database backup"""
        try:
            print("\n💾 Creating database backup...")
            result = self.backup_manager.create_backup()
            
            if result['status'] == 'success':
                print(f"✅ Backup created: {result['backup_filename']}")
                return True
            else:
                print(f"⚠️  Backup failed: {result.get('error')}")
                logger.warning("Backup failed", error=result.get('error'))
                return False
        except Exception as e:
            print(f"⚠️  Backup error: {str(e)}")
            logger.warning("Backup error", error=str(e))
            return False
    
    def run_with_retry(self, test_mode: bool = False):
        """
        Main entry point with retry logic
        
        Args:
            test_mode: If True, run immediately regardless of time
        """
        print(f"\n{'='*60}")
        print("TOVITO TRADER - DAILY AUTOMATION")
        print(f"{'='*60}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Max Retries: {self.max_retries}")
        print(f"Retry Interval: {self.retry_interval} minutes")
        
        if test_mode:
            print("⚠️  TEST MODE - Running immediately")
        
        print(f"{'='*60}\n")
        
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            
            if attempt > 1:
                print(f"\n{'='*60}")
                print(f"RETRY ATTEMPT {attempt}/{self.max_retries}")
                print(f"{'='*60}\n")
            
            # Try to run NAV update
            success = self.run_nav_update()
            
            if success:
                # Run validation
                self.run_validation()
                
                # Create backup
                self.create_backup()
                
                print(f"\n{'='*60}")
                print("✅ DAILY UPDATE COMPLETE!")
                print(f"{'='*60}\n")
                
                logger.info("Daily automation completed successfully")
                return True
            
            # Failed - should we retry?
            if attempt <= self.max_retries:
                next_attempt = datetime.now().timestamp() + (self.retry_interval * 60)
                next_attempt_time = datetime.fromtimestamp(next_attempt).strftime('%I:%M %p')
                
                print(f"\n⏰ Will retry in {self.retry_interval} minutes (at {next_attempt_time})")
                logger.info(f"Scheduled retry {attempt+1} at {next_attempt_time}")
                
                if not test_mode:
                    # Sleep until next retry
                    time.sleep(self.retry_interval * 60)
                else:
                    print("   (Test mode - skipping sleep)")
                    break
            else:
                print(f"\n❌ MAX RETRIES REACHED ({self.max_retries})")
                print("   Daily update will be attempted again tomorrow")
                logger.error(f"Daily update failed after {self.max_retries} retries")
                self.log_to_database('ERROR', f'Daily update failed after {self.max_retries} retries')
                return False
        
        return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run daily NAV update with retry logic')
    parser.add_argument('--test', action='store_true', help='Test mode - run immediately')
    
    args = parser.parse_args()
    
    runner = DailyRunner()
    
    try:
        success = runner.run_with_retry(test_mode=args.test)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        logger.warning("Daily runner interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
