"""
TOVITO TRADER - Quick Manual NAV Update
Run this to update NAV right now without the full automation
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tradier_balance():
    """Get account balance from Tradier API"""
    try:
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('TRADIER_API_KEY')
        account_id = os.getenv('TRADIER_ACCOUNT_ID')
        
        if not api_key or not account_id:
            print("❌ Missing TRADIER_API_KEY or TRADIER_ACCOUNT_ID in .env file")
            return None
        
        # Use production URL
        base_url = os.getenv('TRADIER_BASE_URL', 'https://api.tradier.com/v1')
        
        url = f"{base_url}/accounts/{account_id}/balances"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        
        print(f"📡 Fetching balance from Tradier...")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            balances = data.get('balances', {})
            total_equity = balances.get('total_equity', 0)
            print(f"✅ Account balance: ${total_equity:,.2f}")
            return total_equity
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
            
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("   Run: pip install requests python-dotenv")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def update_nav_manually(db_path, portfolio_value):
    """Update NAV in database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get total shares
        cursor.execute("SELECT SUM(current_shares) FROM investors WHERE status = 'Active'")
        total_shares = cursor.fetchone()[0] or 0
        
        if total_shares == 0:
            print("❌ No active investors with shares found!")
            conn.close()
            return False
        
        # Calculate NAV
        nav_per_share = portfolio_value / total_shares
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get yesterday's values for change calculation
        cursor.execute("""
            SELECT total_portfolio_value, nav_per_share 
            FROM daily_nav 
            ORDER BY date DESC 
            LIMIT 1
        """)
        prev = cursor.fetchone()
        
        if prev:
            daily_change_dollars = portfolio_value - prev[0]
            daily_change_percent = ((nav_per_share - prev[1]) / prev[1] * 100) if prev[1] else 0
        else:
            daily_change_dollars = 0
            daily_change_percent = 0
        
        # Check if today's entry exists
        cursor.execute("SELECT date FROM daily_nav WHERE date = ?", (today,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            cursor.execute("""
                UPDATE daily_nav SET
                    nav_per_share = ?,
                    total_portfolio_value = ?,
                    total_shares = ?,
                    daily_change_dollars = ?,
                    daily_change_percent = ?,
                    source = 'Manual'
                WHERE date = ?
            """, (nav_per_share, portfolio_value, total_shares, 
                  daily_change_dollars, daily_change_percent, today))
            print(f"📝 Updated existing entry for {today}")
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value, 
                    total_shares, daily_change_dollars, daily_change_percent, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'Manual', datetime('now'))
            """, (today, nav_per_share, portfolio_value, total_shares,
                  daily_change_dollars, daily_change_percent))
            print(f"📝 Created new entry for {today}")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ NAV UPDATED SUCCESSFULLY!")
        print(f"   Date: {today}")
        print(f"   Portfolio Value: ${portfolio_value:,.2f}")
        print(f"   Total Shares: {total_shares:,.2f}")
        print(f"   NAV per Share: ${nav_per_share:.4f}")
        print(f"   Daily Change: ${daily_change_dollars:,.2f} ({daily_change_percent:+.2f}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def main():
    print("=" * 60)
    print("TOVITO TRADER - Quick Manual NAV Update")
    print("=" * 60)
    print()
    
    # Find database
    db_paths = [
        "data/tovito.db",
        "../data/tovito.db",
        "C:/tovito-trader/data/tovito.db"
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ Could not find database!")
        return
    
    print(f"📂 Database: {db_path}")
    print()
    
    # Try to get balance from Tradier
    balance = get_tradier_balance()
    
    if balance is None:
        print()
        print("📝 Enter portfolio value manually:")
        try:
            balance = float(input("   Total portfolio value: $"))
        except ValueError:
            print("❌ Invalid number")
            return
    
    print()
    
    # Update NAV
    success = update_nav_manually(db_path, balance)
    
    if success:
        print()
        print("🎉 Done! Refresh your dashboard to see updated values.")

if __name__ == "__main__":
    main()
