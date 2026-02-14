"""
View Current Positions
Display all investor positions with PII protection
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.automation.nav_calculator import NAVCalculator
from src.database.models import Database, Investor
from src.utils.safe_logging import get_safe_logger, PIIProtector

logger = get_safe_logger(__name__)


def view_positions():
    """Display all active investor positions"""
    
    print("\n" + "="*60)
    print("CURRENT INVESTOR POSITIONS")
    print("="*60 + "\n")
    
    calculator = NAVCalculator()
    db = Database()
    session = db.get_session()
    
    try:
        # Get all active investors
        investors = session.query(Investor).filter(
            Investor.status == 'Active'
        ).order_by(Investor.investor_id).all()
        
        if not investors:
            print("No active investors found.\n")
            return
        
        # Get current NAV
        current_nav = calculator.get_current_nav()
        
        if not current_nav:
            print("⚠️  No NAV data available yet.")
            print("   Run daily update first: python -m src.automation.nav_calculator\n")
            return
        
        print(f"Current NAV per Share: {PIIProtector.mask_dollar_amount(current_nav)}\n")
        print("-" * 60)
        
        total_value = 0
        
        for inv in investors:
            value = inv.current_shares * current_nav
            total_value += value
            
            print(f"\n📊 Investor: {PIIProtector.mask_name(inv.name)}")
            print(f"   ID: {inv.investor_id}")
            print(f"   Shares: ***")
            print(f"   Value: {PIIProtector.mask_dollar_amount(value)}")
            print(f"   Status: {inv.status}")
        
        print("\n" + "-" * 60)
        print(f"\nTotal Portfolio Value: {PIIProtector.mask_dollar_amount(total_value)}")
        print(f"Active Investors: {len(investors)}")
        print("\n" + "="*60 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}\n")
        logger.error("Failed to view positions", error=str(e))
    
    finally:
        session.close()


if __name__ == "__main__":
    view_positions()
