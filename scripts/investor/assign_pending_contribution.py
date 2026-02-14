"""
Assign Pending Contributions

Interactive tool to assign unallocated deposits to investors.
Run this when you receive an admin alert about new deposits.

Usage:
    python scripts/assign_pending_contribution.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def get_pending_contributions(conn):
    """Get all pending contributions"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, transaction_date, amount, tradier_transaction_id,
               notes, created_at
        FROM pending_contributions
        WHERE status = 'pending'
        ORDER BY transaction_date DESC, created_at DESC
    """)
    
    return cursor.fetchall()


def get_active_investors(conn):
    """Get all active investors"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment
        FROM investors
        WHERE status = 'Active'
        ORDER BY investor_id
    """)
    
    return cursor.fetchall()


def assign_contribution(conn, pending_id, investor_id):
    """Assign a pending contribution to an investor"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE pending_contributions
            SET investor_id = ?,
                status = 'assigned',
                admin_notified_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (investor_id, pending_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cancel_contribution(conn, pending_id, reason):
    """Cancel a pending contribution"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE pending_contributions
            SET status = 'cancelled',
                notes = notes || ' | Cancelled: ' || ?
            WHERE id = ?
        """, (reason, pending_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("=" * 70)
    print("ASSIGN PENDING CONTRIBUTIONS")
    print("=" * 70)
    print()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get pending contributions
        pending = get_pending_contributions(conn)
        
        if not pending:
            print("✅ No pending contributions!")
            print()
            print("All deposits have been assigned to investors.")
            conn.close()
            return
        
        print(f"Found {len(pending)} pending contribution(s):")
        print()
        
        # Display pending contributions
        for idx, (p_id, trans_date, amount, trans_id, notes, created) in enumerate(pending, 1):
            print(f"{idx}. PENDING CONTRIBUTION")
            print("-" * 70)
            print(f"   ID:              {p_id}")
            print(f"   Date:            {trans_date}")
            print(f"   Amount:          ${amount:,.2f}")
            print(f"   Transaction ID:  {trans_id}")
            print(f"   Notes:           {notes}")
            print(f"   Detected:        {created}")
            print()
        
        # Get active investors
        investors = get_active_investors(conn)
        
        print("=" * 70)
        print("ACTIVE INVESTORS")
        print("=" * 70)
        print()
        
        for idx, (inv_id, name, shares, net_inv) in enumerate(investors, 1):
            print(f"{idx}. {name} ({inv_id})")
            print(f"   Shares: {shares:,.4f} | Net Investment: ${net_inv:,.2f}")
        print()
        
        # Process each pending contribution
        for idx, (p_id, trans_date, amount, trans_id, notes, created) in enumerate(pending, 1):
            print("=" * 70)
            print(f"ASSIGN CONTRIBUTION #{idx}")
            print("=" * 70)
            print()
            print(f"Date:   {trans_date}")
            print(f"Amount: ${amount:,.2f}")
            print()
            
            while True:
                action = input(f"Select investor (1-{len(investors)}), 'skip', or 'cancel': ").strip().lower()
                
                if action == 'skip':
                    print("Skipped - will process later")
                    print()
                    break
                
                if action == 'cancel':
                    reason = input("Reason for cancellation: ").strip()
                    if cancel_contribution(conn, p_id, reason):
                        print(f"✅ Contribution cancelled: {reason}")
                    print()
                    break
                
                try:
                    investor_num = int(action)
                    if 1 <= investor_num <= len(investors):
                        # Assign to investor
                        selected_investor = investors[investor_num - 1]
                        inv_id, inv_name = selected_investor[0], selected_investor[1]
                        
                        print()
                        print(f"Assigning ${amount:,.2f} to {inv_name} ({inv_id})")
                        
                        confirm = input("Confirm? (yes/no): ").strip().lower()
                        
                        if confirm in ['yes', 'y']:
                            if assign_contribution(conn, p_id, inv_id):
                                print(f"✅ Assigned to {inv_name}")
                                print()
                                print("NOTE: Shares will be allocated during next NAV update")
                                print()
                            break
                        else:
                            print("Not assigned - try again")
                            continue
                    else:
                        print(f"❌ Please enter 1-{len(investors)}")
                except ValueError:
                    print("❌ Invalid input")
        
        # Summary
        print("=" * 70)
        print("ASSIGNMENT SUMMARY")
        print("=" * 70)
        print()
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM pending_contributions WHERE status = 'assigned'")
        assigned = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pending_contributions WHERE status = 'pending'")
        still_pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pending_contributions WHERE status = 'cancelled'")
        cancelled = cursor.fetchone()[0]
        
        print(f"Assigned:       {assigned}")
        print(f"Still pending:  {still_pending}")
        print(f"Cancelled:      {cancelled}")
        print()
        
        if still_pending > 0:
            print("⚠️  Some contributions still pending assignment")
            print("   Run this script again to assign them")
        else:
            print("✅ All contributions assigned!")
        
        print()
        print("NEXT STEP:")
        print("  Run: python scripts/daily_nav_enhanced.py")
        print("  This will allocate shares based on your assignments")
        print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
