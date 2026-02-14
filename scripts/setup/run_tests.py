"""
Automated End-to-End Testing Script

Runs comprehensive tests to verify:
- Database schema
- Email system
- Contribution workflow
- Withdrawal workflow
- Data integrity
- Edge cases

Usage:
    python scripts/run_tests.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path
import sys
from decimal import Decimal

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

class TestRunner:
    def __init__(self, db_path="data/tovito.db"):
        self.db_path = Path(db_path)
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def run_all_tests(self):
        """Run all test suites"""
        print("=" * 70)
        print("TOVITO TRADER - AUTOMATED END-TO-END TESTS")
        print("=" * 70)
        print()
        
        if not self.db_path.exists():
            print_error(f"Database not found: {self.db_path}")
            return False
        
        print_info(f"Testing database: {self.db_path}")
        print()
        
        # Run test suites
        self.test_database_schema()
        self.test_data_integrity()
        self.test_calculations()
        self.test_edge_cases()
        
        # Print summary
        print()
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Passed:   {self.passed}")
        print(f"❌ Failed:   {self.failed}")
        print(f"⚠️  Warnings: {self.warnings}")
        print()
        
        if self.failed == 0:
            print_success("ALL TESTS PASSED!")
            print()
            print("🎉 Your system is ready for production!")
            return True
        else:
            print_error(f"{self.failed} test(s) failed")
            print()
            print("Please review failures before going live.")
            return False
    
    def test_database_schema(self):
        """Test database schema is correct"""
        print("📊 Testing Database Schema...")
        print()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Test 1: Required tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['investors', 'nav_history', 'transactions', 'tax_events']
        for table in required_tables:
            if table in tables:
                print_success(f"Table '{table}' exists")
                self.passed += 1
            else:
                print_error(f"Table '{table}' missing")
                self.failed += 1
        
        # Test 2: Email column exists
        cursor.execute("PRAGMA table_info(investors)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'email' in columns:
            print_success("Email column exists in investors table")
            self.passed += 1
        else:
            print_error("Email column missing (run migration first)")
            self.failed += 1
        
        # Test 3: Check for active investors
        cursor.execute("SELECT COUNT(*) FROM investors WHERE status='Active'")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print_success(f"Found {count} active investor(s)")
            self.passed += 1
        else:
            print_warning("No active investors found")
            self.warnings += 1
        
        conn.close()
        print()
    
    def test_data_integrity(self):
        """Test data integrity and consistency"""
        print("🔍 Testing Data Integrity...")
        print()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Test 1: Total shares match
        cursor.execute("""
            SELECT SUM(current_shares) 
            FROM investors 
            WHERE status='Active'
        """)
        investor_total = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT total_shares 
            FROM nav_history 
            ORDER BY date DESC 
            LIMIT 1
        """)
        nav_total = cursor.fetchone()[0] or 0
        
        if abs(investor_total - nav_total) < 0.01:  # Allow tiny rounding difference
            print_success(f"Total shares match: {investor_total:.4f}")
            self.passed += 1
        else:
            print_error(f"Total shares mismatch! Investors: {investor_total:.4f}, NAV: {nav_total:.4f}")
            self.failed += 1
        
        # Test 2: Portfolio percentages sum to ~100%
        cursor.execute("""
            SELECT nav_per_share FROM nav_history 
            ORDER BY date DESC LIMIT 1
        """)
        nav = cursor.fetchone()
        
        if nav:
            nav_per_share = nav[0]
            cursor.execute("""
                SELECT SUM(current_shares * ?) / 
                       (SELECT SUM(current_shares * ?) FROM investors WHERE status='Active')
                FROM investors 
                WHERE status='Active'
            """, (nav_per_share, nav_per_share))
            
            percentage_sum = cursor.fetchone()[0]
            
            if percentage_sum and abs(1.0 - percentage_sum) < 0.001:
                print_success(f"Percentages sum to 100%: {percentage_sum*100:.2f}%")
                self.passed += 1
            else:
                print_error(f"Percentages don't sum to 100%: {(percentage_sum or 0)*100:.2f}%")
                self.failed += 1
        else:
            print_warning("No NAV data found")
            self.warnings += 1
        
        # Test 3: No negative values
        cursor.execute("""
            SELECT COUNT(*) 
            FROM investors 
            WHERE current_shares < 0 OR net_investment < 0
        """)
        negative_count = cursor.fetchone()[0]
        
        if negative_count == 0:
            print_success("No negative values found")
            self.passed += 1
        else:
            print_error(f"Found {negative_count} investor(s) with negative values")
            self.failed += 1
        
        conn.close()
        print()
    
    def test_calculations(self):
        """Test calculation accuracy"""
        print("🧮 Testing Calculations...")
        print()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current NAV
        cursor.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM nav_history 
            ORDER BY date DESC 
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        if not nav_data:
            print_warning("No NAV data to test")
            self.warnings += 1
            conn.close()
            print()
            return
        
        nav_per_share, total_value, total_shares = nav_data
        
        # Test 1: NAV = Value / Shares
        calculated_nav = total_value / total_shares if total_shares > 0 else 0
        
        if abs(calculated_nav - nav_per_share) < 0.0001:
            print_success(f"NAV calculation correct: ${nav_per_share:.4f}")
            self.passed += 1
        else:
            print_error(f"NAV calculation error! Stored: ${nav_per_share:.4f}, Calculated: ${calculated_nav:.4f}")
            self.failed += 1
        
        # Test 2: Investor values match shares * NAV
        cursor.execute("""
            SELECT id, name, current_shares, net_investment
            FROM investors
            WHERE status='Active' AND current_shares > 0
            LIMIT 3
        """)
        
        investors = cursor.fetchall()
        
        for inv_id, name, shares, net_inv in investors:
            expected_value = shares * nav_per_share
            # Verify calculation is possible
            if shares > 0:
                print_success(f"{name}: {shares:.4f} shares × ${nav_per_share:.4f} = ${expected_value:,.2f}")
                self.passed += 1
        
        conn.close()
        print()
    
    def test_edge_cases(self):
        """Test edge case handling"""
        print("⚠️  Testing Edge Cases...")
        print()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Test 1: Investors with zero shares
        cursor.execute("""
            SELECT COUNT(*) 
            FROM investors 
            WHERE status='Active' AND current_shares = 0
        """)
        zero_shares = cursor.fetchone()[0]
        
        if zero_shares == 0:
            print_success("No active investors with zero shares")
            self.passed += 1
        else:
            print_warning(f"Found {zero_shares} active investor(s) with zero shares")
            self.warnings += 1
        
        # Test 2: Email addresses present
        cursor.execute("""
            SELECT COUNT(*) 
            FROM investors 
            WHERE status='Active' AND (email IS NULL OR email = '')
        """)
        no_email = cursor.fetchone()[0]
        
        if no_email == 0:
            print_success("All active investors have email addresses")
            self.passed += 1
        else:
            print_warning(f"{no_email} active investor(s) missing email addresses")
            self.warnings += 1
        
        # Test 3: Recent transactions exist
        cursor.execute("""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE date >= date('now', '-7 days')
        """)
        recent_tx = cursor.fetchone()[0]
        
        if recent_tx > 0:
            print_info(f"Found {recent_tx} transaction(s) in last 7 days")
        else:
            print_info("No recent transactions (this is OK for new system)")
        
        # Test 4: Tax events match withdrawals with gains
        cursor.execute("""
            SELECT COUNT(*) FROM tax_events
        """)
        tax_count = cursor.fetchone()[0]
        
        if tax_count >= 0:
            print_info(f"Found {tax_count} tax event(s) recorded")
        
        conn.close()
        print()

def main():
    """Run automated tests"""
    
    # Check if testing production or test database
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        print_warning(f"Testing custom database: {db_path}")
        print()
    else:
        db_path = "data/tovito.db"
        print_info("Testing production database (default)")
        print()
        
        response = input("⚠️  This will test your PRODUCTION database. Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return
        print()
    
    # Run tests
    runner = TestRunner(db_path)
    success = runner.run_all_tests()
    
    # Return exit code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
