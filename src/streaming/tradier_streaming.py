#!/usr/bin/env python3
"""
Tradier Live Streaming Client
==============================
Real-time market data streaming via Tradier WebSocket API.

Features:
- Live quotes (bid/ask/last)
- Trade data
- Account balance updates
- Event-driven architecture
- Auto-reconnection
- Heartbeat monitoring

Usage:
    from tradier_streaming import TradierStreaming
    
    client = TradierStreaming()
    client.subscribe_quotes(['SGOV', 'TQQQ', 'SPY'])
    client.on_quote(handle_quote)
    client.start()
"""

import os
import json
import time
import asyncio
import logging
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import websockets
import requests
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamType(Enum):
    """Types of data streams available"""
    QUOTES = "quotes"
    TRADES = "trades"
    SUMMARY = "summary"
    TIMESALE = "timesale"


@dataclass
class Quote:
    """Real-time quote data"""
    symbol: str
    bid: float
    ask: float
    last: float
    bid_size: int
    ask_size: int
    volume: int
    timestamp: datetime
    change: float = 0.0
    change_pct: float = 0.0
    
    def __str__(self):
        return f"{self.symbol}: ${self.last:.2f} (Bid: ${self.bid:.2f} x {self.bid_size} | Ask: ${self.ask:.2f} x {self.ask_size})"


@dataclass
class Trade:
    """Real-time trade data"""
    symbol: str
    price: float
    size: int
    timestamp: datetime
    exchange: str = ""
    
    def __str__(self):
        return f"{self.symbol}: {self.size} @ ${self.price:.2f}"


@dataclass  
class PortfolioUpdate:
    """Portfolio value update"""
    total_value: float
    cash: float
    equity: float
    timestamp: datetime
    positions: Dict[str, Dict] = field(default_factory=dict)
    
    def __str__(self):
        return f"Portfolio: ${self.total_value:,.2f} (Cash: ${self.cash:,.2f} | Equity: ${self.equity:,.2f})"


class TradierStreaming:
    """
    Tradier WebSocket Streaming Client
    
    Connects to Tradier's streaming API for real-time market data.
    
    Example:
        client = TradierStreaming()
        
        @client.on_quote
        def handle_quote(quote: Quote):
            print(f"New quote: {quote}")
        
        client.subscribe(['SGOV', 'TQQQ'])
        client.start()
    """
    
    # Tradier streaming endpoints
    STREAM_ENDPOINT = "wss://ws.tradier.com/v1/markets/events"
    SESSION_URL = "https://api.tradier.com/v1/markets/events/session"
    SANDBOX_SESSION_URL = "https://sandbox.tradier.com/v1/markets/events/session"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        sandbox: bool = False
    ):
        """
        Initialize streaming client.
        
        Args:
            api_key: Tradier API key (or from TRADIER_API_KEY env var)
            account_id: Tradier account ID (or from TRADIER_ACCOUNT_ID env var)
            sandbox: Use sandbox environment
        """
        self.api_key = api_key or os.getenv('TRADIER_API_KEY')
        self.account_id = account_id or os.getenv('TRADIER_ACCOUNT_ID')
        self.sandbox = sandbox
        
        if not self.api_key:
            raise ValueError("TRADIER_API_KEY required")
        
        # Session management
        self._session_id: Optional[str] = None
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        
        # Subscriptions
        self._subscribed_symbols: List[str] = []
        self._stream_types: List[StreamType] = [StreamType.QUOTES]
        
        # Callbacks
        self._quote_callbacks: List[Callable[[Quote], None]] = []
        self._trade_callbacks: List[Callable[[Trade], None]] = []
        self._portfolio_callbacks: List[Callable[[PortfolioUpdate], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []
        self._connect_callbacks: List[Callable[[], None]] = []
        self._disconnect_callbacks: List[Callable[[], None]] = []
        
        # State
        self._last_heartbeat: Optional[datetime] = None
        self._quotes: Dict[str, Quote] = {}
        
        # Threading
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_session_url(self) -> str:
        """Get the appropriate session URL"""
        return self.SANDBOX_SESSION_URL if self.sandbox else self.SESSION_URL
    
    def _create_session(self) -> str:
        """Create a streaming session and get session ID"""
        logger.info("Creating streaming session...")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
        
        response = requests.post(self._get_session_url(), headers=headers)
        
        if response.status_code != 200:
            raise ConnectionError(f"Failed to create session: {response.status_code} - {response.text}")
        
        data = response.json()
        session_id = data.get('stream', {}).get('sessionid')
        
        if not session_id:
            raise ConnectionError(f"No session ID in response: {data}")
        
        logger.info(f"Session created: {session_id[:8]}...")
        return session_id

    # ============================================================
    # Callback Registration
    # ============================================================
    
    def on_quote(self, callback: Callable[[Quote], None]) -> 'TradierStreaming':
        """Register callback for quote updates"""
        self._quote_callbacks.append(callback)
        return self
    
    def on_trade(self, callback: Callable[[Trade], None]) -> 'TradierStreaming':
        """Register callback for trade updates"""
        self._trade_callbacks.append(callback)
        if StreamType.TRADES not in self._stream_types:
            self._stream_types.append(StreamType.TRADES)
        return self
    
    def on_portfolio(self, callback: Callable[[PortfolioUpdate], None]) -> 'TradierStreaming':
        """Register callback for portfolio updates"""
        self._portfolio_callbacks.append(callback)
        return self
    
    def on_error(self, callback: Callable[[Exception], None]) -> 'TradierStreaming':
        """Register callback for errors"""
        self._error_callbacks.append(callback)
        return self
    
    def on_connect(self, callback: Callable[[], None]) -> 'TradierStreaming':
        """Register callback for connection established"""
        self._connect_callbacks.append(callback)
        return self
    
    def on_disconnect(self, callback: Callable[[], None]) -> 'TradierStreaming':
        """Register callback for disconnection"""
        self._disconnect_callbacks.append(callback)
        return self

    # ============================================================
    # Subscription Management
    # ============================================================
    
    def subscribe(self, symbols: List[str]) -> 'TradierStreaming':
        """Subscribe to symbols for streaming data"""
        self._subscribed_symbols = [s.upper() for s in symbols]
        logger.info(f"Subscribed to: {', '.join(self._subscribed_symbols)}")
        return self
    
    def subscribe_quotes(self, symbols: List[str]) -> 'TradierStreaming':
        """Subscribe to quote updates for symbols"""
        return self.subscribe(symbols)
    
    def subscribe_trades(self, symbols: List[str]) -> 'TradierStreaming':
        """Subscribe to trade updates for symbols"""
        if StreamType.TRADES not in self._stream_types:
            self._stream_types.append(StreamType.TRADES)
        return self.subscribe(symbols)
    
    def add_symbol(self, symbol: str) -> 'TradierStreaming':
        """Add a symbol to subscription"""
        symbol = symbol.upper()
        if symbol not in self._subscribed_symbols:
            self._subscribed_symbols.append(symbol)
            # If connected, send subscription update
            if self._websocket and self._running:
                asyncio.run_coroutine_threadsafe(
                    self._send_subscription(),
                    self._loop
                )
        return self
    
    def remove_symbol(self, symbol: str) -> 'TradierStreaming':
        """Remove a symbol from subscription"""
        symbol = symbol.upper()
        if symbol in self._subscribed_symbols:
            self._subscribed_symbols.remove(symbol)
            del self._quotes[symbol]
        return self
    
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get the latest cached quote for a symbol"""
        return self._quotes.get(symbol.upper())
    
    def get_all_quotes(self) -> Dict[str, Quote]:
        """Get all cached quotes"""
        return self._quotes.copy()

    # ============================================================
    # Connection Management
    # ============================================================
    
    async def _send_subscription(self):
        """Send subscription message to WebSocket"""
        if not self._websocket or not self._subscribed_symbols:
            return
        
        # Build subscription payload
        payload = {
            'symbols': self._subscribed_symbols,
            'sessionid': self._session_id,
            'linebreak': True
        }
        
        # Add filter for stream types
        filters = []
        if StreamType.QUOTES in self._stream_types:
            filters.append('quote')
        if StreamType.TRADES in self._stream_types:
            filters.append('trade')
        if StreamType.SUMMARY in self._stream_types:
            filters.append('summary')
        if StreamType.TIMESALE in self._stream_types:
            filters.append('timesale')
        
        if filters:
            payload['filter'] = filters
        
        message = json.dumps(payload)
        logger.debug(f"Sending subscription: {message}")
        await self._websocket.send(message)
    
    async def _handle_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            msg_type = data.get('type', '')
            
            if msg_type == 'quote':
                quote = self._parse_quote(data)
                if quote:
                    self._quotes[quote.symbol] = quote
                    for callback in self._quote_callbacks:
                        try:
                            callback(quote)
                        except Exception as e:
                            logger.error(f"Quote callback error: {e}")
            
            elif msg_type == 'trade':
                trade = self._parse_trade(data)
                if trade:
                    for callback in self._trade_callbacks:
                        try:
                            callback(trade)
                        except Exception as e:
                            logger.error(f"Trade callback error: {e}")
            
            elif msg_type == 'heartbeat':
                self._last_heartbeat = datetime.now()
                logger.debug("Heartbeat received")
            
            elif msg_type == 'error':
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Stream error: {error_msg}")
                for callback in self._error_callbacks:
                    callback(Exception(error_msg))
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {message[:100]}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def _parse_quote(self, data: dict) -> Optional[Quote]:
        """Parse quote data from stream message"""
        try:
            return Quote(
                symbol=data.get('symbol', ''),
                bid=float(data.get('bid', 0)),
                ask=float(data.get('ask', 0)),
                last=float(data.get('last', 0)),
                bid_size=int(data.get('bidsz', 0)),
                ask_size=int(data.get('asksz', 0)),
                volume=int(data.get('volume', 0)),
                timestamp=datetime.now(),
                change=float(data.get('change', 0)),
                change_pct=float(data.get('change_percentage', 0))
            )
        except Exception as e:
            logger.error(f"Quote parse error: {e}")
            return None
    
    def _parse_trade(self, data: dict) -> Optional[Trade]:
        """Parse trade data from stream message"""
        try:
            return Trade(
                symbol=data.get('symbol', ''),
                price=float(data.get('price', 0)),
                size=int(data.get('size', 0)),
                timestamp=datetime.now(),
                exchange=data.get('exch', '')
            )
        except Exception as e:
            logger.error(f"Trade parse error: {e}")
            return None
    
    async def _connect(self):
        """Establish WebSocket connection"""
        while self._running:
            try:
                # Create new session
                self._session_id = self._create_session()
                
                # Connect to WebSocket
                logger.info("Connecting to WebSocket...")
                async with websockets.connect(
                    self.STREAM_ENDPOINT,
                    ping_interval=30,
                    ping_timeout=10
                ) as ws:
                    self._websocket = ws
                    self._reconnect_delay = 1
                    
                    logger.info("✅ Connected to Tradier streaming!")
                    
                    # Notify connect callbacks
                    for callback in self._connect_callbacks:
                        try:
                            callback()
                        except Exception as e:
                            logger.error(f"Connect callback error: {e}")
                    
                    # Send subscription
                    await self._send_subscription()
                    
                    # Process messages
                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_message(message)
                
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}")
            except Exception as e:
                logger.error(f"Connection error: {e}")
                for callback in self._error_callbacks:
                    callback(e)
            
            # Notify disconnect callbacks
            for callback in self._disconnect_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Disconnect callback error: {e}")
            
            # Reconnect logic
            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._max_reconnect_delay
                )
    
    def _run_async(self):
        """Run async event loop in thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())
    
    def start(self, blocking: bool = True):
        """
        Start the streaming connection.
        
        Args:
            blocking: If True, blocks the current thread.
                     If False, runs in background thread.
        """
        if self._running:
            logger.warning("Already running")
            return
        
        if not self._subscribed_symbols:
            logger.warning("No symbols subscribed - call subscribe() first")
        
        self._running = True
        
        if blocking:
            asyncio.run(self._connect())
        else:
            self._thread = threading.Thread(target=self._run_async, daemon=True)
            self._thread.start()
            logger.info("Streaming started in background")
    
    def stop(self):
        """Stop the streaming connection"""
        logger.info("Stopping streaming...")
        self._running = False
        
        if self._websocket:
            asyncio.run_coroutine_threadsafe(
                self._websocket.close(),
                self._loop
            )
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Streaming stopped")


class TradierPortfolioMonitor:
    """
    Monitor portfolio value in real-time.
    
    Polls account balance periodically and calculates NAV based on
    position values from streaming quotes.
    
    Example:
        monitor = TradierPortfolioMonitor()
        
        @monitor.on_nav_update
        def handle_nav(nav: float, portfolio: PortfolioUpdate):
            print(f"NAV: ${nav:.4f}")
        
        monitor.start()
    """
    
    BALANCE_URL = "https://api.tradier.com/v1/accounts/{account_id}/balances"
    POSITIONS_URL = "https://api.tradier.com/v1/accounts/{account_id}/positions"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        poll_interval: int = 60
    ):
        """
        Initialize portfolio monitor.
        
        Args:
            api_key: Tradier API key
            account_id: Tradier account ID
            poll_interval: Seconds between balance polls
        """
        self.api_key = api_key or os.getenv('TRADIER_API_KEY')
        self.account_id = account_id or os.getenv('TRADIER_ACCOUNT_ID')
        self.poll_interval = poll_interval
        
        if not self.api_key or not self.account_id:
            raise ValueError("TRADIER_API_KEY and TRADIER_ACCOUNT_ID required")
        
        # Streaming client for live quotes
        self._streaming: Optional[TradierStreaming] = None
        
        # Callbacks
        self._nav_callbacks: List[Callable[[float, PortfolioUpdate], None]] = []
        
        # State
        self._running = False
        self._last_portfolio: Optional[PortfolioUpdate] = None
        self._positions: Dict[str, Dict] = {}
    
    def on_nav_update(self, callback: Callable[[float, PortfolioUpdate], None]) -> 'TradierPortfolioMonitor':
        """Register callback for NAV updates"""
        self._nav_callbacks.append(callback)
        return self
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
    
    def get_balance(self) -> Dict:
        """Get current account balance"""
        url = self.BALANCE_URL.format(account_id=self.account_id)
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code != 200:
            raise ConnectionError(f"Balance request failed: {response.status_code}")
        
        return response.json().get('balances', {})
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        url = self.POSITIONS_URL.format(account_id=self.account_id)
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code != 200:
            raise ConnectionError(f"Positions request failed: {response.status_code}")
        
        data = response.json().get('positions', {})
        if data == 'null' or data is None:
            return []
        
        positions = data.get('position', [])
        if isinstance(positions, dict):
            positions = [positions]
        
        return positions
    
    def _poll_balance(self):
        """Poll account balance and notify callbacks"""
        try:
            balance = self.get_balance()
            positions = self.get_positions()
            
            # Build position dict
            pos_dict = {}
            for pos in positions:
                symbol = pos.get('symbol', '')
                pos_dict[symbol] = {
                    'quantity': pos.get('quantity', 0),
                    'cost_basis': pos.get('cost_basis', 0),
                    'current_price': pos.get('close_price', 0)
                }
            
            portfolio = PortfolioUpdate(
                total_value=float(balance.get('total_equity', 0)),
                cash=float(balance.get('total_cash', 0)),
                equity=float(balance.get('market_value', 0)),
                timestamp=datetime.now(),
                positions=pos_dict
            )
            
            self._last_portfolio = portfolio
            self._positions = pos_dict
            
            # Calculate NAV (would need total shares from database)
            nav = portfolio.total_value  # Simplified - just total value for now
            
            # Notify callbacks
            for callback in self._nav_callbacks:
                try:
                    callback(nav, portfolio)
                except Exception as e:
                    logger.error(f"NAV callback error: {e}")
            
            return portfolio
            
        except Exception as e:
            logger.error(f"Balance poll error: {e}")
            return None
    
    async def _poll_loop(self):
        """Async polling loop"""
        while self._running:
            self._poll_balance()
            await asyncio.sleep(self.poll_interval)
    
    def start(self, blocking: bool = False):
        """Start monitoring"""
        self._running = True
        
        # Initial poll
        self._poll_balance()
        
        # Start streaming for positions
        if self._positions:
            symbols = list(self._positions.keys())
            self._streaming = TradierStreaming(self.api_key, self.account_id)
            self._streaming.subscribe(symbols)
            self._streaming.start(blocking=False)
        
        # Start polling loop
        if blocking:
            asyncio.run(self._poll_loop())
        else:
            thread = threading.Thread(target=lambda: asyncio.run(self._poll_loop()), daemon=True)
            thread.start()
    
    def stop(self):
        """Stop monitoring"""
        self._running = False
        if self._streaming:
            self._streaming.stop()
    
    def get_portfolio(self) -> Optional[PortfolioUpdate]:
        """Get last portfolio update"""
        return self._last_portfolio


# ============================================================
# Convenience Functions
# ============================================================

def stream_quotes(symbols: List[str], callback: Callable[[Quote], None]):
    """
    Simple function to stream quotes for symbols.
    
    Example:
        def print_quote(quote):
            print(f"{quote.symbol}: ${quote.last}")
        
        stream_quotes(['SGOV', 'TQQQ'], print_quote)
    """
    client = TradierStreaming()
    client.subscribe(symbols)
    client.on_quote(callback)
    client.start(blocking=True)


def get_live_quote(symbol: str, timeout: int = 10) -> Optional[Quote]:
    """
    Get a single live quote for a symbol.
    
    Example:
        quote = get_live_quote('SGOV')
        print(f"SGOV: ${quote.last}")
    """
    result = [None]
    
    def on_quote(quote):
        result[0] = quote
    
    client = TradierStreaming()
    client.subscribe([symbol])
    client.on_quote(on_quote)
    client.start(blocking=False)
    
    # Wait for quote
    start = time.time()
    while result[0] is None and (time.time() - start) < timeout:
        time.sleep(0.1)
    
    client.stop()
    return result[0]


# ============================================================
# CLI for Testing
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tradier Live Streaming")
    parser.add_argument('symbols', nargs='*', default=['SGOV', 'TQQQ'], 
                        help='Symbols to stream')
    parser.add_argument('--portfolio', action='store_true',
                        help='Monitor portfolio instead of quotes')
    args = parser.parse_args()
    
    if args.portfolio:
        print("Starting portfolio monitor...")
        monitor = TradierPortfolioMonitor()
        
        @monitor.on_nav_update
        def handle_nav(nav, portfolio):
            print(f"\n📊 Portfolio Update:")
            print(f"   Total: ${portfolio.total_value:,.2f}")
            print(f"   Cash:  ${portfolio.cash:,.2f}")
            print(f"   Equity: ${portfolio.equity:,.2f}")
            print(f"   Time: {portfolio.timestamp.strftime('%H:%M:%S')}")
        
        monitor.start(blocking=True)
    
    else:
        print(f"Starting quote stream for: {', '.join(args.symbols)}")
        
        client = TradierStreaming()
        client.subscribe(args.symbols)
        
        @client.on_quote
        def handle_quote(quote: Quote):
            print(f"📈 {quote}")
        
        @client.on_connect
        def on_connect():
            print("✅ Connected!")
        
        @client.on_disconnect
        def on_disconnect():
            print("⚠️ Disconnected")
        
        @client.on_error
        def on_error(e):
            print(f"❌ Error: {e}")
        
        try:
            client.start(blocking=True)
        except KeyboardInterrupt:
            print("\nStopping...")
            client.stop()
