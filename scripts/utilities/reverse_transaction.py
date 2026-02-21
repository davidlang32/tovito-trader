"""
Reverse Transaction
===================

Reverse the last transaction using proper accounting method.
Creates an offsetting transaction instead of deleting records.

Maintains complete audit trail - nothing is deleted.

Usage:
    python scripts/reverse_transaction.py
    
Or:
    python run.py reverse
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sys
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.models import Database, Investor, Transaction, DailyNAV, TaxEvent
from src.utils.safe_logging import get_safe_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_safe_logger(__name__)


class TransactionReverser:
    """Handle transaction reversals using proper accounting method"""
    
    def __init__(self):
        self.db = Database()
    
    def get_last_transaction(self, session):
        """Get the most recent transaction (excluding reversals)"""
        return session.query(Transaction)\
            .filter(~Transaction.notes.like('%REVERSAL%'))\
            .order_by(Transaction.date.desc())\
            .first()
    
    def display_transaction(self, trans):
        """Display transaction details with PII masking"""
        trans_type = trans.transaction_type
        amount_display = f"${abs(trans.amount):,.2f}"
        shares_display = f"{abs(trans.shares_transacted):,.4f}"
        
        print(f"\n{'='*60}")
        print(f"LAST TRANSACTION")
        print(f"{'='*60}")
        print(f"Date: {trans.date}")
        print(f"Investor: Investor *** (ID: {trans.investor_id})")
        print(f"Type: {trans_type}")
        print(f"Amount: ${amount_display}")
        print(f"Share Price: $***")
        print(f"Shares: {shares_display}")
        if trans.notes:
            print(f"Notes: {trans.notes}")
        print(f"{'='*60}")
    
    def reverse_contribution(self, session, original_trans):
        """
        Reverse a contribution
        Creates a withdrawal transaction with same amount
        """
        investor = session.query(Investor).filter_by(
            investor_id=original_trans.investor_id
        ).first()
        
        if not investor:
            return False, "Investor not found"
        
        # Check if investor has enough shares
        shares_to_remove = abs(original_trans.shares_transacted)
        if investor.current_shares < shares_to_remove:
            return False, f"Insufficient shares. Investor has {investor.current_shares:.4f}, need {shares_to_remove:.4f}"
        
        # Create reversal transaction (opposite of original)
        reversal = Transaction(
            date=date.today(),
            investor_id=original_trans.investor_id,
            transaction_type='Withdrawal',
            amount=-abs(original_trans.amount),  # Negative
            share_price=original_trans.share_price,
            shares_transacted=-abs(original_trans.shares_transacted),  # Negative
            notes=f'REVERSAL of contribution from {original_trans.date}. Original: ${abs(original_trans.amount):.2f}'
        )
        session.add(reversal)
        
        # Update investor
        investor.current_shares -= shares_to_remove
        investor.net_investment -= abs(original_trans.amount)
        
        # Update Daily NAV
        latest_nav = session.query(DailyNAV).order_by(DailyNAV.date.desc()).first()
        if latest_nav and latest_nav.date == date.today():
            latest_nav.total_portfolio_value -= abs(original_trans.amount)
            latest_nav.total_shares -= shares_to_remove
        
        return True, reversal
    
    def reverse_withdrawal(self, session, original_trans):
        """
        Reverse a withdrawal
        Creates a contribution transaction with same amount
        Also reverses the tax event
        """
        investor = session.query(Investor).filter_by(
            investor_id=original_trans.investor_id
        ).first()
        
        if not investor:
            return False, "Investor not found"
        
        # Find associated tax event
        tax_event = session.query(TaxEvent).filter(
            TaxEvent.investor_id == original_trans.investor_id,
            TaxEvent.date == original_trans.date
        ).first()
        
        # Create reversal transaction (opposite of original)
        reversal = Transaction(
            date=date.today(),
            investor_id=original_trans.investor_id,
            transaction_type='Contribution',
            amount=abs(original_trans.amount),  # Positive
            share_price=original_trans.share_price,
            shares_transacted=abs(original_trans.shares_transacted),  # Positive
            notes=f'REVERSAL of withdrawal from {original_trans.date}. Original: ${abs(original_trans.amount):.2f}'
        )
        session.add(reversal)
        
        # Update investor
        investor.current_shares += abs(original_trans.shares_transacted)
        investor.net_investment += abs(original_trans.amount)
        
        # If there was a tax event, create reversal tax event
        if tax_event:
            reversal_tax = TaxEvent(
                date=date.today(),
                investor_id=original_trans.investor_id,
                withdrawal_amount=-tax_event.withdrawal_amount,  # Negative
                realized_gain=-tax_event.realized_gain,  # Negative
                tax_due=-tax_event.tax_due,  # Negative
                net_proceeds=-tax_event.net_proceeds,  # Negative
                tax_rate=tax_event.tax_rate,
                notes=f'REVERSAL of tax event from {original_trans.date}'
            )
            session.add(reversal_tax)
        
        # Update Daily NAV
        latest_nav = session.query(DailyNAV).order_by(DailyNAV.date.desc()).first()
        if latest_nav and latest_nav.date == date.today():
            latest_nav.total_portfolio_value += abs(original_trans.amount)
            latest_nav.total_shares += abs(original_trans.shares_transacted)
        
        return True, reversal
    
    def reverse_transaction(self):
        """Main reversal flow"""
        session = self.db.get_session()
        
        try:
            print("\n" + "="*60)
            print("REVERSE TRANSACTION")
            print("="*60)
            print("\n⚠️  This creates an offsetting transaction.")
            print("   Original transaction remains in records.")
            print("   This is proper accounting practice.")
            
            # Get last transaction
            print("\n🔍 Finding last transaction...")
            last_trans = self.get_last_transaction(session)
            
            if not last_trans:
                print("\n❌ No transactions found to reverse!")
                return False
            
            # Display it
            self.display_transaction(last_trans)
            
            # Get investor for display
            investor = session.query(Investor).filter_by(
                investor_id=last_trans.investor_id
            ).first()
            
            print(f"\n📊 Current Position (Investor ***):")
            print(f"   Shares: ***")
            print(f"   Net Investment: $***")
            print(f"   Current Value: $***")
            
            # Confirm
            print(f"\n⚠️  REVERSAL IMPACT:")
            if last_trans.transaction_type == 'Contribution':
                print(f"   Will create: Withdrawal transaction")
                print(f"   Amount: ${abs(last_trans.amount):,.2f}")
                print(f"   Shares removed: {abs(last_trans.shares_transacted):,.4f}")
                print(f"   Net Investment: Reduced")
            elif last_trans.transaction_type == 'Withdrawal':
                print(f"   Will create: Contribution transaction")
                print(f"   Amount: ${abs(last_trans.amount):,.2f}")
                print(f"   Shares added: {abs(last_trans.shares_transacted):,.4f}")
                print(f"   Net Investment: Increased")
                print(f"   Note: Tax event will also be reversed")
            else:
                print(f"   Cannot reverse {last_trans.transaction_type} transactions")
                print(f"   Only Contributions and Withdrawals can be reversed")
                return False
            
            confirm = input(f"\n{'='*60}\nCreate reversal transaction? (yes/NO): ").strip().lower()
            
            if confirm != 'yes':
                print("\nCancelled")
                return False
            
            # Process reversal
            print("\n⚙️  Processing reversal...")
            
            if last_trans.transaction_type == 'Contribution':
                success, result = self.reverse_contribution(session, last_trans)
            elif last_trans.transaction_type == 'Withdrawal':
                success, result = self.reverse_withdrawal(session, last_trans)
            else:
                success = False
                result = f"Cannot reverse {last_trans.transaction_type}"
            
            if not success:
                print(f"\n❌ Reversal failed: {result}")
                session.rollback()
                return False
            
            # Commit changes
            session.commit()
            
            print("✅ Reversal transaction created!")
            
            # Show new position
            session.refresh(investor)
            
            print(f"\n📊 Updated Position (Investor ***):")
            print(f"   Shares: ***")
            print(f"   Net Investment: $***")
            print(f"   Current Value: $***")
            
            print(f"\n" + "="*60)
            print("REVERSAL COMPLETE")
            print("="*60)
            print(f"\nReversal transaction created: {date.today()}")
            print(f"Original transaction from {last_trans.date} remains in records.")
            print(f"Complete audit trail maintained. ✅")
            print()
            
            # Log it
            logger.info("Transaction reversed",
                       original_date=str(last_trans.date),
                       original_type=last_trans.transaction_type,
                       investor_id=last_trans.investor_id)
            
            return True
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error: {str(e)}")
            logger.error("Transaction reversal failed", error=str(e))
            return False
        
        finally:
            session.close()


def main():
    """Main entry point"""
    reverser = TransactionReverser()
    
    try:
        success = reverser.reverse_transaction()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
