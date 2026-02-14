"""
Tovito Trader - Main Runner Script
====================================

Properly run any module from the project root.
Handles Python path setup automatically.

Usage:
    python run.py api            # Test Tradier API
    python run.py database       # Initialize database
    python run.py nav            # Run daily NAV update
    python run.py scheduler      # Start automation service
    python run.py validate       # Validate data
    python run.py logs           # View logs
    python run.py positions      # View positions
    python run.py contribution   # Process contribution
    python run.py withdrawal     # Process withdrawal
    python run.py reverse        # Reverse last transaction
    python run.py monthly-report # Generate monthly reports
    python run.py migrate        # Import from Excel
    python run.py backup         # Backup database
    python run.py test           # Run all tests
    python run.py investors      # List investors
    python run.py health         # System health check
"""

import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def main():
    """Main entry point"""
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Remove command from sys.argv so submodules get correct args
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    
    try:
        if command == 'api':
            from src.api.tradier import TradierClient
            
            print("Testing Tradier API Connection...\n")
            try:
                client = TradierClient()
                print("✅ Tradier API client initialized")
                
                balance = client.get_account_balance()
                print(f"\n✅ Account Balance Retrieved:")
                print(f"   Total Equity: $***")  # PII masked
                print(f"   Timestamp: {balance['timestamp']}")
                
                is_open = client.is_market_open()
                print(f"\n✅ Market Status: {'OPEN' if is_open else 'CLOSED'}")
                
                positions = client.get_positions()
                print(f"\n✅ Current Positions: {len(positions)} position(s)")
                
                print("\n🎉 All API tests passed!")
                
            except Exception as e:
                print(f"\n❌ API Test Failed: {str(e)}")
                print("\nPlease check:")
                print("1. .env file exists with correct credentials")
                print("2. TRADIER_API_KEY is valid")
                print("3. TRADIER_ACCOUNT_ID is correct")
                print("4. Internet connection is working")
        
        elif command == 'database':
            from src.database import models
            print("Initializing database...")
            db = models.Database()
            db.create_all_tables()
        
        elif command == 'nav':
            from src.automation.nav_calculator import NAVCalculator
            calculator = NAVCalculator()
            calculator.fetch_and_update_nav()
        
        elif command == 'scheduler':
            from src.automation.scheduler import TaskScheduler
            scheduler = TaskScheduler()
            scheduler.run()
        
        elif command == 'validate':
            # Updated path: scripts/validation/validate_comprehensive.py
            from scripts.validation import validate_comprehensive
            validate_comprehensive.validate_comprehensive()
        
        elif command == 'logs':
            # Updated path: scripts/utilities/view_logs.py
            from scripts.utilities import view_logs
            days = 7
            log_type = None
            if '--today' in sys.argv:
                days = 1
            if '--days' in sys.argv:
                idx = sys.argv.index('--days')
                if idx + 1 < len(sys.argv):
                    days = int(sys.argv[idx + 1])
            if '--type' in sys.argv:
                idx = sys.argv.index('--type')
                if idx + 1 < len(sys.argv):
                    log_type = sys.argv[idx + 1]
            view_logs.view_logs(days=days, log_type=log_type)
        
        elif command == 'positions':
            # Updated path: scripts/utilities/view_positions.py
            from scripts.utilities import view_positions
            view_positions.view_positions()
        
        elif command == 'contribution':
            # Updated path: scripts/investor/process_contribution.py
            from scripts.investor import process_contribution
            process_contribution.main()
        
        elif command == 'withdrawal':
            # Updated path: scripts/investor/process_withdrawal_enhanced.py
            from scripts.investor import process_withdrawal_enhanced
            process_withdrawal_enhanced.process_withdrawal()
        
        elif command == 'reverse':
            # Updated path: scripts/utilities/reverse_transaction.py
            from scripts.utilities import reverse_transaction
            reverse_transaction.main()
        
        elif command == 'monthly-report':
            # Updated path: scripts/reporting/generate_monthly_report.py
            from scripts.reporting import generate_monthly_report
            generate_monthly_report.main()
        
        elif command == 'migrate':
            # Updated path: scripts/setup/migrate_from_excel.py
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "migrate_from_excel",
                os.path.join(PROJECT_ROOT, 'scripts', 'setup', 'migrate_from_excel.py')
            )
            migrate_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migrate_module)
        
        elif command == 'backup':
            # Updated path: scripts/utilities/backup_database.py
            from scripts.utilities import backup_database
            backup_database.main()
        
        elif command == 'investors':
            # Updated path: scripts/investor/list_investors.py
            from scripts.investor import list_investors
            list_investors.main()
        
        elif command == 'health':
            # Updated path: scripts/validation/system_health_check.py
            from scripts.validation import system_health_check
            system_health_check.run_health_check()
        
        elif command == 'test':
            print("Running system tests...\n")
            # Test imports
            from src.api import tradier
            from src.database import models
            from src.automation import nav_calculator
            from src.utils import safe_logging
            print("✅ All modules imported successfully")
            
            # Test database
            print("\nTesting database...")
            db = models.Database()
            session = db.get_session()
            session.close()
            print("✅ Database connection works")
            
            # Test logger
            print("\nTesting safe logging...")
            logger = safe_logging.get_safe_logger(__name__)
            logger.info("Test log message", test_value=123)
            print("✅ Logging system works")
            
            print("\n🎉 All tests passed!")
        
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
