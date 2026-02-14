"""
TOVITO TRADER - Alert System
Core monitoring engine for portfolio alerts

Features:
- Real-time position monitoring via Tradier API
- Volatility-adjusted thresholds (options vs stocks)
- ATR-based exit alerts (Plan M)
- Portfolio event tracking
- Unusual volume detection
- Trend analysis
"""

import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum
import threading
import time
from pathlib import Path

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AlertPriority(Enum):
    CRITICAL = "critical"  # Immediate action required (Plan M exit)
    HIGH = "high"          # Important, needs attention soon
    MEDIUM = "medium"      # Notable event
    LOW = "low"            # Informational


class AlertType(Enum):
    PLAN_M_EXIT = "plan_m_exit"           # 3 ATR move - EXIT NOW
    POSITION_PERCENT = "position_percent"  # Position % change
    PORTFOLIO_THRESHOLD = "portfolio_threshold"  # Portfolio value threshold
    PORTFOLIO_ATH = "portfolio_ath"        # New all-time high
    UNUSUAL_VOLUME = "unusual_volume"      # Volume spike
    TREND_CHANGE = "trend_change"          # Momentum shift
    OUTLIER_EVENT = "outlier_event"        # Statistical outlier


@dataclass
class Alert:
    """Represents a triggered alert"""
    id: str
    alert_type: AlertType
    priority: AlertPriority
    symbol: Optional[str]
    message: str
    details: Dict
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.alert_type.value,
            'priority': self.priority.value,
            'symbol': self.symbol,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged
        }


@dataclass
class Position:
    """Current position data"""
    symbol: str
    quantity: float
    cost_basis: float
    current_price: float
    market_value: float
    day_change: float
    day_change_percent: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    is_option: bool = False
    option_type: Optional[str] = None  # 'call' or 'put'
    strike: Optional[float] = None
    expiration: Optional[str] = None
    underlying: Optional[str] = None


class TradierAPI:
    """Handles all Tradier API interactions"""
    
    BASE_URL = "https://api.tradier.com/v1"
    
    def __init__(self, api_key: str = None, account_id: str = None):
        self.api_key = api_key or os.getenv('TRADIER_API_KEY')
        self.account_id = account_id or os.getenv('TRADIER_ACCOUNT_ID')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
    
    def get_positions(self) -> List[Position]:
        """Fetch current positions from Tradier"""
        if not self.api_key or not self.account_id:
            return []
        
        url = f"{self.BASE_URL}/accounts/{self.account_id}/positions"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            positions = []
            pos_data = data.get('positions', {})
            
            if pos_data == 'null' or not pos_data:
                return []
            
            pos_list = pos_data.get('position', [])
            if isinstance(pos_list, dict):
                pos_list = [pos_list]
            
            for pos in pos_list:
                symbol = pos.get('symbol', '')
                is_option = len(symbol) > 10  # Options have longer symbols
                
                position = Position(
                    symbol=symbol,
                    quantity=float(pos.get('quantity', 0)),
                    cost_basis=float(pos.get('cost_basis', 0)),
                    current_price=float(pos.get('close', 0)),
                    market_value=float(pos.get('quantity', 0)) * float(pos.get('close', 0)),
                    day_change=float(pos.get('change', 0)) if pos.get('change') else 0,
                    day_change_percent=float(pos.get('change_percentage', 0)) if pos.get('change_percentage') else 0,
                    unrealized_pnl=float(pos.get('unrealized_pnl', 0)) if pos.get('unrealized_pnl') else 0,
                    unrealized_pnl_percent=float(pos.get('unrealized_pnl_percentage', 0)) if pos.get('unrealized_pnl_percentage') else 0,
                    is_option=is_option
                )
                
                # Parse option symbol if applicable
                if is_option:
                    parsed = self._parse_option_symbol(symbol)
                    position.underlying = parsed.get('underlying')
                    position.option_type = parsed.get('option_type')
                    position.strike = parsed.get('strike')
                    position.expiration = parsed.get('expiration')
                
                positions.append(position)
            
            return positions
            
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch current quotes for symbols"""
        if not symbols:
            return {}
        
        url = f"{self.BASE_URL}/markets/quotes"
        params = {'symbols': ','.join(symbols)}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            quotes = {}
            quote_data = data.get('quotes', {}).get('quote', [])
            
            if isinstance(quote_data, dict):
                quote_data = [quote_data]
            
            for q in quote_data:
                symbol = q.get('symbol')
                quotes[symbol] = {
                    'last': float(q.get('last', 0)),
                    'change': float(q.get('change', 0)) if q.get('change') else 0,
                    'change_percent': float(q.get('change_percentage', 0)) if q.get('change_percentage') else 0,
                    'volume': int(q.get('volume', 0)),
                    'average_volume': int(q.get('average_volume', 0)) if q.get('average_volume') else 0,
                    'high': float(q.get('high', 0)) if q.get('high') else 0,
                    'low': float(q.get('low', 0)) if q.get('low') else 0,
                    'open': float(q.get('open', 0)) if q.get('open') else 0,
                    'close': float(q.get('close', 0)) if q.get('close') else 0,
                    'bid': float(q.get('bid', 0)) if q.get('bid') else 0,
                    'ask': float(q.get('ask', 0)) if q.get('ask') else 0,
                }
            
            return quotes
            
        except Exception as e:
            print(f"Error fetching quotes: {e}")
            return {}
    
    def get_history(self, symbol: str, days: int = 30) -> List[Dict]:
        """Fetch historical daily bars for ATR calculation"""
        url = f"{self.BASE_URL}/markets/history"
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)  # Extra days for weekends
        
        params = {
            'symbol': symbol,
            'interval': 'daily',
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            history = data.get('history', {})
            if not history or history == 'null':
                return []
            
            days_data = history.get('day', [])
            if isinstance(days_data, dict):
                days_data = [days_data]
            
            return days_data[-days:]  # Return last N days
            
        except Exception as e:
            print(f"Error fetching history for {symbol}: {e}")
            return []
    
    def get_account_balance(self) -> Dict:
        """Fetch account balance"""
        url = f"{self.BASE_URL}/accounts/{self.account_id}/balances"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            balances = data.get('balances', {})
            return {
                'total_equity': float(balances.get('total_equity', 0)),
                'total_cash': float(balances.get('total_cash', 0)),
                'market_value': float(balances.get('market_value', 0)),
                'open_pl': float(balances.get('open_pl', 0)) if balances.get('open_pl') else 0,
                'close_pl': float(balances.get('close_pl', 0)) if balances.get('close_pl') else 0,
            }
            
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return {}
    
    def _parse_option_symbol(self, symbol: str) -> Dict:
        """Parse OCC option symbol format: AAPL260115C00150000"""
        try:
            # Find where the date starts (6 digits)
            for i in range(len(symbol) - 15):
                if symbol[i:i+6].isdigit():
                    underlying = symbol[:i]
                    date_str = symbol[i:i+6]
                    opt_type = symbol[i+6]
                    strike_str = symbol[i+7:]
                    
                    return {
                        'underlying': underlying,
                        'expiration': f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}",
                        'option_type': 'call' if opt_type == 'C' else 'put',
                        'strike': float(strike_str) / 1000
                    }
        except:
            pass
        
        return {'underlying': symbol, 'option_type': None, 'strike': None, 'expiration': None}


class ATRCalculator:
    """Calculates Average True Range for volatility measurement"""
    
    @staticmethod
    def calculate_atr(history: List[Dict], period: int = 14) -> float:
        """Calculate ATR from daily bars"""
        if len(history) < period + 1:
            return 0.0
        
        true_ranges = []
        
        for i in range(1, len(history)):
            high = float(history[i].get('high', 0))
            low = float(history[i].get('low', 0))
            prev_close = float(history[i-1].get('close', 0))
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
        
        # Simple moving average of TR
        return sum(true_ranges[-period:]) / period
    
    @staticmethod
    def calculate_atr_multiple(current_price: float, reference_price: float, atr: float) -> float:
        """Calculate how many ATRs the price has moved"""
        if atr == 0:
            return 0.0
        return abs(current_price - reference_price) / atr


class AlertEngine:
    """Main alert monitoring engine"""
    
    def __init__(self, db_path: str = None, config_path: str = None):
        self.api = TradierAPI()
        self.db_path = db_path or "data/tovito.db"
        self.config_path = config_path or "config/alert_rules.json"
        
        self.config = self._load_config()
        self.positions: List[Position] = []
        self.quotes: Dict[str, Dict] = {}
        self.atr_cache: Dict[str, float] = {}
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        
        # Snooze state
        self.snooze_until: Optional[datetime] = None
        self.snoozed_types: Dict[AlertType, datetime] = {}
        self.snoozed_symbols: Dict[str, datetime] = {}
        
        # Tracking state
        self.portfolio_ath = 0.0
        self.day_open_values: Dict[str, float] = {}  # symbol -> open price
        self.last_check: Optional[datetime] = None
        
        # Monitoring state
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.check_interval = 300  # 5 minutes default
        
        # Callbacks for notifications
        self.on_alert: Optional[Callable[[Alert], None]] = None
        
        # Initialize database table
        self._init_db()
    
    def _load_config(self) -> Dict:
        """Load alert configuration"""
        default_config = {
            'enabled': True,
            'check_interval_seconds': 300,
            'thresholds': {
                'stock_percent_change': 3.0,      # Alert if stock moves 3%
                'option_percent_change': 15.0,    # Options can move more
                'sgov_percent_change': 0.5,       # SGOV should barely move
                'portfolio_percent_change': 2.0,  # Portfolio-wide alert
                'volume_multiplier': 2.0,         # 2x average volume
                'atr_exit_multiple': 3.0,         # Plan M: 3 ATR move
            },
            'plan_m': {
                'enabled': True,
                'atr_period': 14,
                'exit_atr_multiple': 3.0,
            },
            'portfolio_goals': [
                {'name': 'Goal 1', 'value': 25000, 'enabled': True},
                {'name': 'Goal 2', 'value': 50000, 'enabled': True},
            ],
            'watch_symbols': [
                'SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'META', 'GOOGL', 'AMZN'
            ],
            'notifications': {
                'sound': True,
                'visual': True,
                'email': True,
                'discord': False,
                'discord_webhook': ''
            }
        }
        
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in loaded:
                            loaded[key] = value
                    return loaded
        except Exception as e:
            print(f"Error loading config: {e}")
        
        # Save default config
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        if config:
            self.config = config
        
        try:
            config_dir = Path(self.config_path).parent
            config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _init_db(self):
        """Initialize alert events table in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    symbol TEXT,
                    message TEXT NOT NULL,
                    details TEXT,
                    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged_at TIMESTAMP,
                    notes TEXT
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error initializing alert_events table: {e}")
    
    def _log_alert(self, alert: Alert):
        """Log alert to database for historical analysis"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO alert_events (alert_id, alert_type, priority, symbol, message, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.id,
                alert.alert_type.value,
                alert.priority.value,
                alert.symbol,
                alert.message,
                json.dumps(alert.details)
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging alert: {e}")
    
    def _is_snoozed(self, alert_type: AlertType = None, symbol: str = None) -> bool:
        """Check if alerts are snoozed"""
        now = datetime.now()
        
        # Global snooze
        if self.snooze_until and now < self.snooze_until:
            return True
        
        # Type-specific snooze
        if alert_type and alert_type in self.snoozed_types:
            if now < self.snoozed_types[alert_type]:
                return True
            else:
                del self.snoozed_types[alert_type]
        
        # Symbol-specific snooze
        if symbol and symbol in self.snoozed_symbols:
            if now < self.snoozed_symbols[symbol]:
                return True
            else:
                del self.snoozed_symbols[symbol]
        
        return False
    
    def snooze_all(self, minutes: int = 30):
        """Snooze all alerts for specified minutes"""
        self.snooze_until = datetime.now() + timedelta(minutes=minutes)
    
    def snooze_type(self, alert_type: AlertType, minutes: int = 30):
        """Snooze specific alert type"""
        self.snoozed_types[alert_type] = datetime.now() + timedelta(minutes=minutes)
    
    def snooze_symbol(self, symbol: str, minutes: int = 30):
        """Snooze alerts for specific symbol"""
        self.snoozed_symbols[symbol] = datetime.now() + timedelta(minutes=minutes)
    
    def clear_snooze(self):
        """Clear all snoozes"""
        self.snooze_until = None
        self.snoozed_types.clear()
        self.snoozed_symbols.clear()
    
    def _create_alert(self, alert_type: AlertType, priority: AlertPriority,
                      symbol: str, message: str, details: Dict) -> Alert:
        """Create and register a new alert"""
        alert_id = f"{alert_type.value}_{symbol or 'portfolio'}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        alert = Alert(
            id=alert_id,
            alert_type=alert_type,
            priority=priority,
            symbol=symbol,
            message=message,
            details=details
        )
        
        # Check if snoozed
        if self._is_snoozed(alert_type, symbol):
            return None
        
        self.alerts.append(alert)
        self.alert_history.append(alert)
        self._log_alert(alert)
        
        # Trigger callback
        if self.on_alert:
            self.on_alert(alert)
        
        return alert
    
    def get_volatility_threshold(self, position: Position) -> float:
        """Get appropriate % threshold based on position type"""
        thresholds = self.config.get('thresholds', {})
        
        # SGOV is basically cash
        if position.symbol.upper() == 'SGOV':
            return thresholds.get('sgov_percent_change', 0.5)
        
        # Options have higher volatility
        if position.is_option:
            return thresholds.get('option_percent_change', 15.0)
        
        # Default stock threshold
        return thresholds.get('stock_percent_change', 3.0)
    
    def check_positions(self) -> List[Alert]:
        """Check all positions for alerts"""
        new_alerts = []
        
        self.positions = self.api.get_positions()
        
        if not self.positions:
            return new_alerts
        
        # Get quotes for all symbols
        symbols = [p.symbol for p in self.positions]
        # Add underlying symbols for options
        for p in self.positions:
            if p.underlying and p.underlying not in symbols:
                symbols.append(p.underlying)
        
        self.quotes = self.api.get_quotes(symbols)
        
        for position in self.positions:
            # Check % change threshold
            threshold = self.get_volatility_threshold(position)
            
            if abs(position.day_change_percent) >= threshold:
                direction = "up" if position.day_change_percent > 0 else "down"
                alert = self._create_alert(
                    AlertType.POSITION_PERCENT,
                    AlertPriority.HIGH,
                    position.symbol,
                    f"{position.symbol} is {direction} {abs(position.day_change_percent):.1f}% today",
                    {
                        'change_percent': position.day_change_percent,
                        'threshold': threshold,
                        'current_price': position.current_price,
                        'quantity': position.quantity,
                        'market_value': position.market_value
                    }
                )
                if alert:
                    new_alerts.append(alert)
            
            # Check ATR for Plan M (options and volatile positions)
            if self.config.get('plan_m', {}).get('enabled', True):
                alert = self._check_plan_m_exit(position)
                if alert:
                    new_alerts.append(alert)
        
        return new_alerts
    
    def _check_plan_m_exit(self, position: Position) -> Optional[Alert]:
        """Check if position has moved 3 ATR (Plan M exit rule)"""
        symbol = position.underlying if position.underlying else position.symbol
        
        # Get or calculate ATR
        if symbol not in self.atr_cache:
            history = self.api.get_history(symbol, days=20)
            self.atr_cache[symbol] = ATRCalculator.calculate_atr(history)
        
        atr = self.atr_cache.get(symbol, 0)
        if atr == 0:
            return None
        
        # Get today's open price
        quote = self.quotes.get(symbol, {})
        open_price = quote.get('open', 0)
        current_price = quote.get('last', position.current_price)
        
        if open_price == 0:
            return None
        
        # Calculate ATR multiple
        atr_multiple = ATRCalculator.calculate_atr_multiple(current_price, open_price, atr)
        exit_threshold = self.config.get('plan_m', {}).get('exit_atr_multiple', 3.0)
        
        if atr_multiple >= exit_threshold:
            direction = "UP" if current_price > open_price else "DOWN"
            
            return self._create_alert(
                AlertType.PLAN_M_EXIT,
                AlertPriority.CRITICAL,
                position.symbol,
                f"🚨 PLAN M EXIT: {position.symbol} moved {atr_multiple:.1f} ATR {direction}! EXIT NOW!",
                {
                    'atr': atr,
                    'atr_multiple': atr_multiple,
                    'open_price': open_price,
                    'current_price': current_price,
                    'move': current_price - open_price,
                    'threshold': exit_threshold
                }
            )
        
        return None
    
    def check_portfolio(self) -> List[Alert]:
        """Check portfolio-level alerts"""
        new_alerts = []
        
        balance = self.api.get_account_balance()
        if not balance:
            return new_alerts
        
        total_equity = balance.get('total_equity', 0)
        
        # Check portfolio goals
        for goal in self.config.get('portfolio_goals', []):
            if goal.get('enabled', True):
                goal_value = goal.get('value', 0)
                goal_name = goal.get('name', 'Goal')
                
                if total_equity >= goal_value and goal_value > 0:
                    # Check if we already alerted for this goal
                    goal_key = f"goal_{goal_value}"
                    if goal_key not in [a.details.get('goal_key') for a in self.alert_history]:
                        alert = self._create_alert(
                            AlertType.PORTFOLIO_THRESHOLD,
                            AlertPriority.HIGH,
                            None,
                            f"🎯 {goal_name} reached! Portfolio: ${total_equity:,.2f}",
                            {
                                'goal_name': goal_name,
                                'goal_value': goal_value,
                                'total_equity': total_equity,
                                'goal_key': goal_key
                            }
                        )
                        if alert:
                            new_alerts.append(alert)
        
        # Check for new ATH
        if total_equity > self.portfolio_ath:
            # Only alert if significant new high (0.5%+ above previous)
            if self.portfolio_ath > 0 and (total_equity - self.portfolio_ath) / self.portfolio_ath >= 0.005:
                # Check if we have options positions (more noteworthy)
                has_options = any(p.is_option for p in self.positions)
                
                alert = self._create_alert(
                    AlertType.PORTFOLIO_ATH,
                    AlertPriority.MEDIUM,
                    None,
                    f"📈 New All-Time High: ${total_equity:,.2f}" + (" (with options)" if has_options else ""),
                    {
                        'previous_ath': self.portfolio_ath,
                        'new_ath': total_equity,
                        'has_options': has_options
                    }
                )
                if alert:
                    new_alerts.append(alert)
            
            self.portfolio_ath = total_equity
        
        return new_alerts
    
    def check_unusual_volume(self) -> List[Alert]:
        """Check for unusual volume in portfolio holdings and watchlist"""
        new_alerts = []
        
        # Combine portfolio symbols with watchlist
        symbols = set(self.config.get('watch_symbols', []))
        for p in self.positions:
            symbols.add(p.underlying if p.underlying else p.symbol)
        
        quotes = self.api.get_quotes(list(symbols))
        volume_multiplier = self.config.get('thresholds', {}).get('volume_multiplier', 2.0)
        
        for symbol, quote in quotes.items():
            volume = quote.get('volume', 0)
            avg_volume = quote.get('average_volume', 0)
            
            if avg_volume > 0 and volume > avg_volume * volume_multiplier:
                ratio = volume / avg_volume
                
                # Check if it's in our portfolio
                in_portfolio = any(
                    (p.symbol == symbol or p.underlying == symbol) 
                    for p in self.positions
                )
                
                priority = AlertPriority.HIGH if in_portfolio else AlertPriority.MEDIUM
                
                alert = self._create_alert(
                    AlertType.UNUSUAL_VOLUME,
                    priority,
                    symbol,
                    f"📊 Unusual Volume: {symbol} at {ratio:.1f}x average" + (" (IN PORTFOLIO)" if in_portfolio else ""),
                    {
                        'volume': volume,
                        'average_volume': avg_volume,
                        'ratio': ratio,
                        'in_portfolio': in_portfolio,
                        'price_change': quote.get('change_percent', 0)
                    }
                )
                if alert:
                    new_alerts.append(alert)
        
        return new_alerts
    
    def run_check(self) -> List[Alert]:
        """Run all alert checks"""
        all_alerts = []
        
        if not self.config.get('enabled', True):
            return all_alerts
        
        all_alerts.extend(self.check_positions())
        all_alerts.extend(self.check_portfolio())
        all_alerts.extend(self.check_unusual_volume())
        
        self.last_check = datetime.now()
        
        return all_alerts
    
    def start_monitoring(self, interval_seconds: int = None):
        """Start background monitoring thread"""
        if self.is_running:
            return
        
        self.check_interval = interval_seconds or self.config.get('check_interval_seconds', 300)
        self.is_running = True
        
        def monitor_loop():
            while self.is_running:
                try:
                    self.run_check()
                except Exception as e:
                    print(f"Monitor error: {e}")
                
                time.sleep(self.check_interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def get_status(self) -> Dict:
        """Get current monitoring status"""
        return {
            'is_running': self.is_running,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'check_interval': self.check_interval,
            'positions_count': len(self.positions),
            'active_alerts': len([a for a in self.alerts if not a.acknowledged]),
            'snooze_until': self.snooze_until.isoformat() if self.snooze_until else None,
            'portfolio_ath': self.portfolio_ath
        }
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                
                # Update database
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE alert_events SET acknowledged_at = ? WHERE alert_id = ?",
                        (datetime.now().isoformat(), alert_id)
                    )
                    conn.commit()
                    conn.close()
                except:
                    pass
                
                break
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get alert history from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT alert_id, alert_type, priority, symbol, message, details, triggered_at, acknowledged_at
                FROM alert_events
                ORDER BY triggered_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'alert_id': r[0],
                    'alert_type': r[1],
                    'priority': r[2],
                    'symbol': r[3],
                    'message': r[4],
                    'details': json.loads(r[5]) if r[5] else {},
                    'triggered_at': r[6],
                    'acknowledged_at': r[7]
                }
                for r in rows
            ]
        except Exception as e:
            print(f"Error getting alert history: {e}")
            return []


# Quick test
if __name__ == "__main__":
    engine = AlertEngine()
    print("Alert Engine Status:", engine.get_status())
    
    print("\nFetching positions...")
    positions = engine.api.get_positions()
    for p in positions:
        print(f"  {p.symbol}: {p.quantity} @ ${p.current_price:.2f}")
    
    print("\nRunning check...")
    alerts = engine.run_check()
    print(f"Alerts triggered: {len(alerts)}")
    for a in alerts:
        print(f"  [{a.priority.value}] {a.message}")
