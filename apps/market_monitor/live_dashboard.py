#!/usr/bin/env python3
"""
Tovito Trader - Live Dashboard
==============================

Real-time dashboard showing:
- Live portfolio value from Tradier
- Current NAV and investor positions
- Live quote streaming for positions
- Auto-updates database when market closes

Usage:
    python scripts/live_dashboard.py
    python scripts/live_dashboard.py --symbols SGOV,TQQQ,SPY
    python scripts/live_dashboard.py --auto-update
"""

import os
import sys
import time
import sqlite3
import threading
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import requests
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import colorama for colored output
try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = WHITE = MAGENTA = BLUE = ""
        RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

# Try to import streaming module
try:
    from src.streaming.tradier_streaming import TradierStreaming, Quote
    HAS_STREAMING = True
except ImportError:
    HAS_STREAMING = False


class TradierAPI:
    """Simple Tradier API client"""
    
    BASE_URL = "https://api.tradier.com/v1"
    
    def __init__(self):
        self.api_key = os.getenv('TRADIER_API_KEY')
        self.account_id = os.getenv('TRADIER_ACCOUNT_ID')
        
        if not self.api_key or not self.account_id:
            raise ValueError("TRADIER_API_KEY and TRADIER_ACCOUNT_ID required in .env")
    
    def _headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
    
    def get_balance(self) -> Dict:
        """Get account balance"""
        url = f"{self.BASE_URL}/accounts/{self.account_id}/balances"
        response = requests.get(url, headers=self._headers())
        
        if response.status_code != 200:
            raise Exception(f"Balance request failed: {response.status_code}")
        
        return response.json().get('balances', {})
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        url = f"{self.BASE_URL}/accounts/{self.account_id}/positions"
        response = requests.get(url, headers=self._headers())
        
        if response.status_code != 200:
            raise Exception(f"Positions request failed: {response.status_code}")
        
        data = response.json().get('positions', {})
        if not data or data == 'null':
            return []
        
        positions = data.get('position', [])
        if isinstance(positions, dict):
            positions = [positions]
        
        return positions
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get current quotes for symbols"""
        url = f"{self.BASE_URL}/markets/quotes"
        params = {'symbols': ','.join(symbols)}
        response = requests.get(url, headers=self._headers(), params=params)
        
        if response.status_code != 200:
            raise Exception(f"Quotes request failed: {response.status_code}")
        
        data = response.json().get('quotes', {})
        quotes = data.get('quote', [])
        if isinstance(quotes, dict):
            quotes = [quotes]
        
        return {q['symbol']: q for q in quotes}


class Database:
    """Database access"""
    
    def __init__(self, db_path: str = "data/tovito.db"):
        self.db_path = Path(db_path)
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_latest_nav(self) -> Optional[Dict]:
        """Get latest NAV record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT date, total_portfolio_value, total_shares, nav_per_share
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'date': row[0],
                'total_value': row[1],
                'total_shares': row[2],
                'nav': row[3]
            }
        return None
    
    def get_investors(self) -> List[Dict]:
        """Get all active investors"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT investor_id, name, current_shares, net_investment, status
            FROM investors
            WHERE status = 'Active'
            ORDER BY current_shares DESC
        """)
        
        investors = []
        for row in cursor.fetchall():
            investors.append({
                'id': row[0],
                'name': row[1],
                'shares': row[2],
                'net_investment': row[3],
                'status': row[4]
            })
        
        conn.close()
        return investors
    
    def get_total_shares(self) -> float:
        """Get total shares from investors table"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COALESCE(SUM(current_shares), 0)
            FROM investors
            WHERE status = 'Active'
        """)
        
        total = cursor.fetchone()[0]
        conn.close()
        return total
    
    def update_nav(self, portfolio_value: float, total_shares: float, nav: float):
        """Update or insert today's NAV"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if today's record exists
        cursor.execute("SELECT id FROM daily_nav WHERE date = ?", (today,))
        
        if cursor.fetchone():
            # Update
            cursor.execute("""
                UPDATE daily_nav
                SET total_portfolio_value = ?,
                    total_shares = ?,
                    nav_per_share = ?
                WHERE date = ?
            """, (portfolio_value, total_shares, nav, today))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO daily_nav (date, total_portfolio_value, total_shares, nav_per_share)
                VALUES (?, ?, ?, ?)
            """, (today, portfolio_value, total_shares, nav))
        
        conn.commit()
        conn.close()
        return True


class LiveDashboard:
    """Real-time portfolio dashboard"""
    
    def __init__(self, db_path: str = "data/tovito.db", symbols: List[str] = None):
        self.tradier = TradierAPI()
        self.db = Database(db_path)
        self.symbols = symbols or []
        
        # State
        self.portfolio_value = 0.0
        self.cash = 0.0
        self.equity = 0.0
        self.positions = []
        self.quotes = {}
        self.last_update = None
        self.running = False
        
        # Streaming
        self.streaming_client = None
        if HAS_STREAMING:
            try:
                self.streaming_client = TradierStreaming()
            except Exception as e:
                print(f"⚠️ Streaming not available: {e}")
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def fetch_data(self):
        """Fetch current data from Tradier"""
        try:
            # Get balance
            balance = self.tradier.get_balance()
            self.portfolio_value = float(balance.get('total_equity', 0))
            self.cash = float(balance.get('total_cash', 0))
            self.equity = float(balance.get('market_value', 0))
            
            # Get positions
            self.positions = self.tradier.get_positions()
            
            # Get symbols from positions
            position_symbols = [p.get('symbol', '') for p in self.positions if p.get('symbol')]
            all_symbols = list(set(position_symbols + self.symbols))
            
            # Get quotes
            if all_symbols:
                self.quotes = self.tradier.get_quotes(all_symbols)
            
            self.last_update = datetime.now()
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ Fetch error: {e}{Style.RESET_ALL}")
            return False
    
    def format_currency(self, amount: float) -> str:
        """Format currency with color"""
        if amount >= 0:
            return f"{Fore.GREEN}${amount:,.2f}{Style.RESET_ALL}"
        return f"{Fore.RED}${amount:,.2f}{Style.RESET_ALL}"
    
    def format_percent(self, pct: float) -> str:
        """Format percentage with color"""
        if pct >= 0:
            return f"{Fore.GREEN}+{pct:.2f}%{Style.RESET_ALL}"
        return f"{Fore.RED}{pct:.2f}%{Style.RESET_ALL}"
    
    def render(self):
        """Render the dashboard"""
        self.clear_screen()
        
        # Header
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}  TOVITO TRADER - LIVE DASHBOARD{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}")
        
        if self.last_update:
            print(f"  Last update: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Portfolio Summary
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}📊 PORTFOLIO SUMMARY{Style.RESET_ALL}")
        print(f"{'-'*50}")
        print(f"  Total Value:     {self.format_currency(self.portfolio_value)}")
        print(f"  Cash:            {self.format_currency(self.cash)}")
        print(f"  Equity:          {self.format_currency(self.equity)}")
        
        # NAV Calculation
        latest_nav = self.db.get_latest_nav()
        total_shares = self.db.get_total_shares()
        
        if total_shares > 0:
            current_nav = self.portfolio_value / total_shares
            
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}📈 NAV CALCULATION{Style.RESET_ALL}")
            print(f"{'-'*50}")
            print(f"  Portfolio Value: {self.format_currency(self.portfolio_value)}")
            print(f"  Total Shares:    {total_shares:,.4f}")
            print(f"  Current NAV:     {Fore.CYAN}${current_nav:.4f}{Style.RESET_ALL}")
            
            if latest_nav:
                nav_change = current_nav - latest_nav['nav']
                nav_change_pct = (nav_change / latest_nav['nav']) * 100
                
                print(f"\n  Last Recorded:   ${latest_nav['nav']:.4f} ({latest_nav['date']})")
                print(f"  Change:          {self.format_percent(nav_change_pct)} ({self.format_currency(nav_change)})")
        
        # Positions
        if self.positions:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}📋 POSITIONS{Style.RESET_ALL}")
            print(f"{'-'*70}")
            print(f"  {'Symbol':<10} {'Qty':>10} {'Price':>12} {'Value':>14} {'P/L':>12}")
            print(f"  {'-'*10} {'-'*10} {'-'*12} {'-'*14} {'-'*12}")
            
            for pos in self.positions:
                symbol = pos.get('symbol', 'N/A')
                qty = float(pos.get('quantity', 0))
                cost = float(pos.get('cost_basis', 0))
                
                # Get current price from quotes
                quote = self.quotes.get(symbol, {})
                price = float(quote.get('last', pos.get('close_price', 0)))
                value = qty * price
                pl = value - cost
                pl_pct = (pl / cost * 100) if cost > 0 else 0
                
                pl_str = self.format_currency(pl)
                print(f"  {symbol:<10} {qty:>10.2f} ${price:>10.2f} ${value:>12,.2f} {pl_str} ({pl_pct:+.1f}%)")
        
        # Investors
        investors = self.db.get_investors()
        if investors and total_shares > 0:
            current_nav = self.portfolio_value / total_shares
            
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}👥 INVESTOR POSITIONS{Style.RESET_ALL}")
            print(f"{'-'*70}")
            print(f"  {'Name':<20} {'Shares':>12} {'Value':>14} {'Return':>10} {'%Port':>8}")
            print(f"  {'-'*20} {'-'*12} {'-'*14} {'-'*10} {'-'*8}")
            
            for inv in investors:
                name = inv['name'][:18] + '..' if len(inv['name']) > 20 else inv['name']
                shares = inv['shares']
                net = inv['net_investment']
                value = shares * current_nav
                gain = value - net
                ret_pct = (gain / net * 100) if net > 0 else 0
                port_pct = (shares / total_shares * 100) if total_shares > 0 else 0
                
                ret_str = self.format_percent(ret_pct)
                print(f"  {name:<20} {shares:>12,.4f} ${value:>12,.2f} {ret_str} {port_pct:>7.1f}%")
        
        # Live Quotes
        if self.quotes:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}📡 LIVE QUOTES{Style.RESET_ALL}")
            print(f"{'-'*50}")
            
            for symbol, quote in self.quotes.items():
                last = float(quote.get('last', 0))
                change = float(quote.get('change', 0))
                change_pct = float(quote.get('change_percentage', 0))
                bid = float(quote.get('bid', 0))
                ask = float(quote.get('ask', 0))
                
                change_str = self.format_percent(change_pct)
                print(f"  {symbol:<8} ${last:>10.2f} {change_str}  (Bid: ${bid:.2f} | Ask: ${ask:.2f})")
        
        # Footer
        print(f"\n{Fore.DIM}{'─'*70}")
        print(f"  Press Ctrl+C to exit | Auto-refresh every 30 seconds")
        print(f"{'─'*70}{Style.RESET_ALL}")
    
    def setup_streaming(self):
        """Setup streaming for live quotes"""
        if not self.streaming_client or not HAS_STREAMING:
            return
        
        # Get symbols from positions
        position_symbols = [p.get('symbol', '') for p in self.positions if p.get('symbol')]
        all_symbols = list(set(position_symbols + self.symbols))
        
        if not all_symbols:
            return
        
        def on_quote(quote: Quote):
            self.quotes[quote.symbol] = {
                'last': quote.last,
                'bid': quote.bid,
                'ask': quote.ask,
                'change': quote.change,
                'change_percentage': quote.change_pct
            }
        
        self.streaming_client.subscribe(all_symbols)
        self.streaming_client.on_quote(on_quote)
        self.streaming_client.start(blocking=False)
    
    def run(self, refresh_interval: int = 30, auto_update: bool = False):
        """Run the dashboard"""
        self.running = True
        
        print("Starting dashboard...")
        
        # Initial fetch
        if not self.fetch_data():
            print("Failed to fetch initial data")
            return
        
        # Setup streaming
        self.setup_streaming()
        
        try:
            while self.running:
                self.render()
                
                # Auto-update NAV if enabled and market is closed
                if auto_update:
                    now = datetime.now()
                    # Check if after 4:05 PM and haven't updated today
                    if now.hour >= 16 and now.minute >= 5:
                        latest = self.db.get_latest_nav()
                        if not latest or latest['date'] != now.strftime('%Y-%m-%d'):
                            print(f"\n{Fore.YELLOW}📝 Auto-updating NAV...{Style.RESET_ALL}")
                            total_shares = self.db.get_total_shares()
                            if total_shares > 0:
                                nav = self.portfolio_value / total_shares
                                self.db.update_nav(self.portfolio_value, total_shares, nav)
                                print(f"{Fore.GREEN}✅ NAV updated: ${nav:.4f}{Style.RESET_ALL}")
                
                # Wait for next refresh
                time.sleep(refresh_interval)
                
                # Refresh data
                self.fetch_data()
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Stopping dashboard...{Style.RESET_ALL}")
        finally:
            self.running = False
            if self.streaming_client:
                self.streaming_client.stop()


def main():
    parser = argparse.ArgumentParser(description="Tovito Trader Live Dashboard")
    parser.add_argument('--symbols', '-s', default='', help='Additional symbols to track (comma-separated)')
    parser.add_argument('--db', default='data/tovito.db', help='Database path')
    parser.add_argument('--refresh', '-r', type=int, default=30, help='Refresh interval in seconds')
    parser.add_argument('--auto-update', '-a', action='store_true', help='Auto-update NAV after market close')
    parser.add_argument('--once', action='store_true', help='Run once and exit (no refresh)')
    
    args = parser.parse_args()
    
    symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
    
    dashboard = LiveDashboard(db_path=args.db, symbols=symbols)
    
    if args.once:
        dashboard.fetch_data()
        dashboard.render()
    else:
        dashboard.run(refresh_interval=args.refresh, auto_update=args.auto_update)


if __name__ == "__main__":
    main()
