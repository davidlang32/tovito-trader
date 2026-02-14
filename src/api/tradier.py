"""
Tradier API Client
Handles all interactions with Tradier brokerage API
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class TradierClient:
    """Client for Tradier API interactions"""
    
    def __init__(self):
        self.api_key = os.getenv('TRADIER_API_KEY')
        self.account_id = os.getenv('TRADIER_ACCOUNT_ID')
        self.base_url = os.getenv('TRADIER_API_URL', 'https://api.tradier.com/v1')
        
        if not self.api_key or not self.account_id:
            raise ValueError("Tradier API credentials not configured in .env file")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
    
    def get_account_balance(self) -> Dict:
        """
        Get current account balance and equity
        
        Returns:
            dict: {
                'total_equity': float,
                'total_cash': float,
                'option_long_value': float,
                'option_short_value': float,
                'stock_long_value': float,
                'timestamp': datetime
            }
        """
        url = f"{self.base_url}/accounts/{self.account_id}/balances"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            balances = data.get('balances', {})
            
            return {
                'total_equity': float(balances.get('total_equity', 0)),
                'total_cash': float(balances.get('total_cash', 0)),
                'option_long_value': float(balances.get('option_long_value', 0)),
                'option_short_value': float(balances.get('option_short_value', 0)),
                'stock_long_value': float(balances.get('stock_long_value', 0)),
                'timestamp': datetime.now()
            }
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch account balance: {str(e)}")
    
    def get_positions(self) -> List[Dict]:
        """
        Get current positions
        
        Returns:
            list: List of position dictionaries
        """
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            positions = data.get('positions', {}).get('position', [])
            
            # Ensure it's always a list
            if isinstance(positions, dict):
                positions = [positions]
            
            return positions
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch positions: {str(e)}")
    
    def get_gainloss(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """
        Get gain/loss history for a date range
        
        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)
            
        Returns:
            list: List of gain/loss records
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        url = f"{self.base_url}/accounts/{self.account_id}/gainloss"
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            gainloss = data.get('gainloss', {}).get('closed_position', [])
            
            if isinstance(gainloss, dict):
                gainloss = [gainloss]
            
            return gainloss
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch gain/loss: {str(e)}")
    
    def get_history(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """
        Get account history (transactions, trades, etc.)
        
        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)
            
        Returns:
            list: List of history events
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        url = f"{self.base_url}/accounts/{self.account_id}/history"
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            history = data.get('history', {}).get('event', [])
            
            if isinstance(history, dict):
                history = [history]
            
            return history
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch history: {str(e)}")
    
    def is_market_open(self) -> bool:
        """
        Check if market is currently open
        
        Returns:
            bool: True if market is open
        """
        url = f"{self.base_url}/markets/clock"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            clock = data.get('clock', {})
            
            return clock.get('state') == 'open'
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch market status: {str(e)}")
    
    def get_market_calendar(self, month: int = None, year: int = None) -> Dict:
        """
        Get market calendar (trading days, holidays)
        
        Args:
            month: Month (1-12)
            year: Year
            
        Returns:
            dict: Calendar information
        """
        url = f"{self.base_url}/markets/calendar"
        
        params = {}
        if month:
            params['month'] = month
        if year:
            params['year'] = year
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch market calendar: {str(e)}")


# Test function
if __name__ == "__main__":
    """Test Tradier API connection"""
    
    try:
        client = TradierClient()
        print("✅ Tradier API client initialized")
        
        # Test balance fetch
        balance = client.get_account_balance()
        print(f"\n✅ Account Balance Retrieved:")
        print(f"   Total Equity: ${balance['total_equity']:,.2f}")
        print(f"   Total Cash: ${balance['total_cash']:,.2f}")
        print(f"   Timestamp: {balance['timestamp']}")
        
        # Test market status
        is_open = client.is_market_open()
        print(f"\n✅ Market Status: {'OPEN' if is_open else 'CLOSED'}")
        
        # Test positions
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
