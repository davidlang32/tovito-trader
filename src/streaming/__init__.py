"""
Tradier Streaming Module
========================

Real-time market data streaming via Tradier WebSocket API.

Classes:
    TradierStreaming: WebSocket client for live quotes and trades
    TradierPortfolioMonitor: Portfolio value monitoring

Functions:
    stream_quotes: Simple function to stream quotes
    get_live_quote: Get a single live quote

Example:
    from src.streaming import TradierStreaming, Quote
    
    client = TradierStreaming()
    client.subscribe(['SGOV', 'TQQQ'])
    
    @client.on_quote
    def handle_quote(quote: Quote):
        print(f"{quote.symbol}: ${quote.last}")
    
    client.start()
"""

from .tradier_streaming import (
    TradierStreaming,
    TradierPortfolioMonitor,
    Quote,
    Trade,
    PortfolioUpdate,
    StreamType,
    stream_quotes,
    get_live_quote
)

__all__ = [
    'TradierStreaming',
    'TradierPortfolioMonitor',
    'Quote',
    'Trade',
    'PortfolioUpdate',
    'StreamType',
    'stream_quotes',
    'get_live_quote'
]
