"""
TOVITO TRADER - Desktop Dashboard
CustomTkinter Application for Fund Management

Features:
- Dashboard Overview with key metrics
- NAV History Chart (interactive)
- Investor Allocation Pie Chart
- Investor Positions Table
- Recent Transactions
- Data Explorer (SQL queries)
- Trading Journal
- Tax Management View
- Alert Monitoring System
"""

import customtkinter as ctk
from CTkTable import CTkTable
import sqlite3
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys

# For charts
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib import style

# For data handling
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# Import alerts tab (optional - won't break if missing)
try:
    from alerts_tab import AlertsTab
    HAS_ALERTS = True
except ImportError as e:
    print(f"Alerts module not available: {e}")
    HAS_ALERTS = False

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Color themes for the dashboard
THEMES = {
    'dark_gray': {
        'name': 'Dark Gray',
        'bg_dark': '#0d0d0d',        # Near black (main background)
        'bg_card': '#1a1a1a',        # Very dark gray (card backgrounds)
        'accent': '#262626',         # Dark gray (accents/borders)
        'highlight': '#e94560',      # Red/pink (highlights/buttons)
        'text': '#f5f5f5',           # Off-white text
        'text_secondary': '#808080', # Medium gray text
        'success': '#22c55e',        # Green
        'warning': '#f59e0b',        # Amber
        'danger': '#ef4444',         # Red
        'chart_bg': '#0d0d0d',       # Chart background
    },
    'dark_blue': {
        'name': 'Dark Blue',
        'bg_dark': '#0a0a1a',
        'bg_card': '#12122a',
        'accent': '#1a1a3a',
        'highlight': '#6366f1',      # Indigo
        'text': '#f5f5f5',
        'text_secondary': '#8888aa',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'danger': '#ef4444',
        'chart_bg': '#0a0a1a',
    },
    'dark_green': {
        'name': 'Dark Green',
        'bg_dark': '#0a1a0a',
        'bg_card': '#122a12',
        'accent': '#1a3a1a',
        'highlight': '#22c55e',      # Green
        'text': '#f5f5f5',
        'text_secondary': '#88aa88',
        'success': '#4ade80',
        'warning': '#f59e0b',
        'danger': '#ef4444',
        'chart_bg': '#0a1a0a',
    },
    'light': {
        'name': 'Light',
        'bg_dark': '#f5f5f5',
        'bg_card': '#ffffff',
        'accent': '#e5e5e5',
        'highlight': '#e94560',
        'text': '#1a1a1a',
        'text_secondary': '#666666',
        'success': '#16a34a',
        'warning': '#d97706',
        'danger': '#dc2626',
        'chart_bg': '#ffffff',
    },
}

# Current theme (default to dark gray)
COLORS = THEMES['dark_gray'].copy()

def set_theme(theme_name):
    """Switch color theme"""
    global COLORS
    if theme_name in THEMES:
        COLORS.update(THEMES[theme_name])
        return True
    return False

# Chart style
plt.style.use('dark_background')


class DatabaseManager:
    """Handles all database operations"""
    
    def __init__(self, db_path=None):
        """Initialize with database path - auto-detects if not provided"""
        if db_path is None:
            # Try common locations
            possible_paths = [
                Path("data/tovito.db"),
                Path("../data/tovito.db"),
                Path("C:/tovito-trader/data/tovito.db"),
                Path.home() / "tovito-trader" / "data" / "tovito.db",
            ]
            for path in possible_paths:
                if path.exists():
                    db_path = str(path)
                    break
        
        self.db_path = db_path
        self.connected = False
        
        if db_path and os.path.exists(db_path):
            self.connected = True
    
    def get_connection(self):
        """Get a database connection"""
        if not self.connected:
            return None
        return sqlite3.connect(self.db_path)
    
    def execute_query(self, query, params=None):
        """Execute a query and return results"""
        if not self.connected:
            return None, None
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = cursor.fetchall()
            conn.close()
            return columns, results
        except Exception as e:
            conn.close()
            return None, str(e)
    
    def get_tables(self):
        """Get list of all tables"""
        cols, results = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        if results and isinstance(results, list):
            return [r[0] for r in results]
        return []
    
    def get_table_data(self, table_name, limit=1000):
        """Get all data from a table"""
        return self.execute_query(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
    
    def get_investors(self):
        """Get all investors with their current positions"""
        # First, check what columns exist in investors table
        try:
            cols_info = self.execute_query("PRAGMA table_info(investors)")
            if cols_info and cols_info[1]:
                col_names = [c[1] for c in cols_info[1]]
            else:
                col_names = []
        except:
            col_names = []
        
        # Determine correct column name for shares
        if 'current_shares' in col_names:
            shares_col = 'current_shares'
        elif 'shares' in col_names:
            shares_col = 'shares'
        else:
            shares_col = 'current_shares'  # default
        
        # Build query based on available columns
        has_status = 'status' in col_names
        
        if has_status:
            where_clause = "WHERE i.status = 'Active' OR i.status IS NULL OR i.status = ''"
        else:
            where_clause = ""
        
        query = f"""
        SELECT 
            i.investor_id,
            i.name,
            COALESCE(i.{shares_col}, 0) as shares,
            COALESCE(i.net_investment, 0) as net_investment,
            {'i.status' if has_status else "'Active'"} as status,
            COALESCE(n.nav_per_share, 1.0) as nav_per_share,
            COALESCE(i.{shares_col}, 0) * COALESCE(n.nav_per_share, 1.0) as current_value,
            (COALESCE(i.{shares_col}, 0) * COALESCE(n.nav_per_share, 1.0)) - COALESCE(i.net_investment, 0) as unrealized_gain
        FROM investors i
        LEFT JOIN (
            SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1
        ) n ON 1=1
        {where_clause}
        ORDER BY i.name
        """
        return self.execute_query(query)
    
    def get_investor_count(self):
        """Get count of active investors"""
        # Check if status column exists
        try:
            cols_info = self.execute_query("PRAGMA table_info(investors)")
            if cols_info and cols_info[1]:
                col_names = [c[1] for c in cols_info[1]]
                has_status = 'status' in col_names
            else:
                has_status = False
        except:
            has_status = False
        
        if has_status:
            query = """
                SELECT COUNT(*) FROM investors 
                WHERE status = 'Active' OR status IS NULL OR status = ''
            """
        else:
            query = "SELECT COUNT(*) FROM investors"
        
        cols, results = self.execute_query(query)
        if results and len(results) > 0:
            return results[0][0]
        return 0
    
    def get_nav_history(self, days=90):
        """Get NAV history for charting"""
        query = """
        SELECT date, nav_per_share, total_portfolio_value, total_shares
        FROM daily_nav
        ORDER BY date DESC
        LIMIT ?
        """
        cols, results = self.execute_query(query, (days,))
        if results and isinstance(results, list):
            # Reverse to chronological order
            return cols, list(reversed(results))
        return cols, results
    
    def get_recent_transactions(self, limit=10):
        """Get recent transactions"""
        # Use actual column names from database:
        # transaction_type (not type), shares_transacted (not shares), share_price (not nav_per_share)
        query = """
        SELECT 
            t.date,
            i.name as investor,
            t.transaction_type as type,
            t.amount,
            t.shares_transacted as shares,
            t.share_price as nav_per_share
        FROM transactions t
        LEFT JOIN investors i ON t.investor_id = i.investor_id
        ORDER BY t.date DESC, t.transaction_id DESC
        LIMIT ?
        """
        return self.execute_query(query, (limit,))
    
    def get_portfolio_summary(self):
        """Get current portfolio summary with change from previous day"""
        # Get latest and previous NAV
        query = """
        SELECT 
            total_portfolio_value,
            total_shares,
            nav_per_share,
            date
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 2
        """
        cols, results = self.execute_query(query)
        if results and len(results) > 0:
            latest = results[0]
            previous = results[1] if len(results) > 1 else None
            
            summary = {
                'total_value': latest[0],
                'total_shares': latest[1],
                'nav_per_share': latest[2],
                'last_update': latest[3],
                'nav_change': 0,
                'nav_change_pct': 0,
                'value_change': 0,
            }
            
            if previous:
                summary['nav_change'] = latest[2] - previous[2]
                summary['nav_change_pct'] = ((latest[2] - previous[2]) / previous[2] * 100) if previous[2] else 0
                summary['value_change'] = latest[0] - previous[0]
                summary['previous_nav'] = previous[2]
                summary['previous_date'] = previous[3]
            
            return summary
        return None
    
    def get_trades_summary(self):
        """Get trading summary if trades table exists"""
        tables = self.get_tables()
        if 'trades' not in tables:
            return None
        
        query = """
        SELECT 
            symbol,
            COUNT(*) as trade_count,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_buys,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_sells,
            SUM(commission) as total_commission
        FROM trades
        WHERE category = 'Trade'
        GROUP BY symbol
        ORDER BY trade_count DESC
        LIMIT 10
        """
        return self.execute_query(query)


class MetricCard(ctk.CTkFrame):
    """A card widget for displaying a single metric"""
    
    def __init__(self, parent, title, value, subtitle="", color=COLORS['accent'], **kwargs):
        super().__init__(parent, fg_color=COLORS['bg_card'], corner_radius=10, **kwargs)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary']
        )
        self.title_label.pack(pady=(15, 5), padx=15, anchor="w")
        
        # Value
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=color
        )
        self.value_label.pack(pady=(0, 5), padx=15, anchor="w")
        
        # Subtitle (always create, even if empty)
        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle if subtitle else " ",  # Space prevents collapse
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_secondary']
        )
        self.subtitle_label.pack(pady=(0, 15), padx=15, anchor="w")
    
    def update_value(self, value, subtitle="", color=None):
        """Update the metric value"""
        self.value_label.configure(text=value)
        if color:
            self.value_label.configure(text_color=color)
        if subtitle:
            self.subtitle_label.configure(text=subtitle)


class ChartFrame(ctk.CTkFrame):
    """A frame for displaying matplotlib charts"""
    
    def __init__(self, parent, title="Chart", **kwargs):
        super().__init__(parent, fg_color=COLORS['bg_card'], corner_radius=10, **kwargs)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['text']
        )
        self.title_label.pack(pady=(10, 5), padx=15, anchor="w")
        
        # Chart container
        self.chart_container = ctk.CTkFrame(self, fg_color="transparent")
        self.chart_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.figure = None
        self.canvas = None
    
    def create_line_chart(self, dates, values, ylabel="NAV", color=COLORS['highlight']):
        """Create a line chart for NAV history"""
        # Clear previous chart
        for widget in self.chart_container.winfo_children():
            widget.destroy()
        
        # Create figure
        self.figure = Figure(figsize=(8, 4), dpi=100, facecolor=COLORS['chart_bg'])
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(COLORS['chart_bg'])
        
        # Plot data
        ax.plot(dates, values, color=color, linewidth=2)
        ax.fill_between(dates, values, alpha=0.2, color=color)
        
        # Styling
        ax.set_ylabel(ylabel, color=COLORS['text'])
        ax.tick_params(colors=COLORS['text_secondary'])
        ax.spines['bottom'].set_color(COLORS['text_secondary'])
        ax.spines['left'].set_color(COLORS['text_secondary'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.figure.autofmt_xdate()
        
        self.figure.tight_layout()
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, self.chart_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def create_pie_chart(self, labels, values, colors=None):
        """Create a pie chart for allocation"""
        # Clear previous chart
        for widget in self.chart_container.winfo_children():
            widget.destroy()
        
        # Create figure
        self.figure = Figure(figsize=(6, 4), dpi=100, facecolor=COLORS['chart_bg'])
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(COLORS['chart_bg'])
        
        # Default colors
        if colors is None:
            colors = ['#e94560', '#0f3460', '#4ecca3', '#ffc107', '#7b2cbf', '#00b4d8']
        
        # Create pie
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors[:len(values)],
            textprops={'color': COLORS['text']}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
        
        self.figure.tight_layout()
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, self.chart_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)


class DataTableFrame(ctk.CTkFrame):
    """A frame for displaying tabular data"""
    
    def __init__(self, parent, title="Data", **kwargs):
        super().__init__(parent, fg_color=COLORS['bg_card'], corner_radius=10, **kwargs)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['text']
        )
        self.title_label.pack(pady=(10, 5), padx=15, anchor="w")
        
        # Scrollable container
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.table = None
    
    def update_data(self, headers, rows):
        """Update the table with new data"""
        # Clear previous table
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        if not rows:
            no_data = ctk.CTkLabel(
                self.scroll_frame,
                text="No data available",
                text_color=COLORS['text_secondary']
            )
            no_data.pack(pady=20)
            return
        
        # Create table data with headers
        table_data = [list(headers)] + [list(row) for row in rows]
        
        try:
            # Create table
            self.table = CTkTable(
                master=self.scroll_frame,
                values=table_data,
                header_color=COLORS['accent'],
                hover_color=COLORS['bg_dark'],
                colors=[COLORS['bg_card'], COLORS['bg_dark']],
                text_color=COLORS['text'],
                corner_radius=5,
                wraplength=120
            )
            self.table.pack(fill="both", expand=True, padx=2, pady=2)
        except Exception as e:
            # Fallback to text display
            text_display = ctk.CTkTextbox(
                self.scroll_frame,
                fg_color=COLORS['bg_dark'],
                text_color=COLORS['text'],
                font=ctk.CTkFont(family="Consolas", size=10),
                height=200
            )
            text_display.pack(fill="both", expand=True, padx=2, pady=2)
            
            # Format as text
            col_widths = [max(len(str(h)), 10) for h in headers]
            for i, row in enumerate(rows[:50]):
                for j, val in enumerate(row):
                    if j < len(col_widths):
                        col_widths[j] = max(col_widths[j], min(len(str(val)), 15))
            
            # Header
            header_line = " | ".join(str(h)[:15].ljust(col_widths[i]) for i, h in enumerate(headers))
            text_display.insert("end", header_line + "\n")
            text_display.insert("end", "-" * len(header_line) + "\n")
            
            # Rows
            for row in rows[:50]:
                row_line = " | ".join(str(v)[:15].ljust(col_widths[i]) if i < len(col_widths) else str(v)[:15] for i, v in enumerate(row))
                text_display.insert("end", row_line + "\n")
            
            text_display.configure(state="disabled")


class DashboardTab(ctk.CTkFrame):
    """Main dashboard overview tab"""
    
    def __init__(self, parent, db_manager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.db = db_manager
        
        self.create_widgets()
        self.refresh_data()
    
    def create_widgets(self):
        """Create dashboard widgets"""
        # Top metrics row
        self.metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics_frame.pack(fill="x", padx=10, pady=10)
        
        # Configure grid for metrics
        for i in range(4):
            self.metrics_frame.columnconfigure(i, weight=1)
        
        # Metric cards
        self.card_portfolio = MetricCard(
            self.metrics_frame, "Portfolio Value", "$0.00",
            color=COLORS['success']
        )
        self.card_portfolio.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.card_nav = MetricCard(
            self.metrics_frame, "NAV per Share", "$0.00",
            color=COLORS['highlight']
        )
        self.card_nav.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        self.card_shares = MetricCard(
            self.metrics_frame, "Total Shares", "0",
            color=COLORS['text']
        )
        self.card_shares.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        
        self.card_investors = MetricCard(
            self.metrics_frame, "Active Investors", "0",
            color=COLORS['warning']
        )
        self.card_investors.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        
        # Charts row
        self.charts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.charts_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.charts_frame.columnconfigure(0, weight=2)
        self.charts_frame.columnconfigure(1, weight=1)
        self.charts_frame.rowconfigure(0, weight=1)
        
        # NAV History Chart
        self.nav_chart = ChartFrame(self.charts_frame, title="📈 NAV History")
        self.nav_chart.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Investor Allocation Pie
        self.allocation_chart = ChartFrame(self.charts_frame, title="🥧 Investor Allocation")
        self.allocation_chart.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        # Bottom row - Tables
        self.tables_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tables_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.tables_frame.columnconfigure(0, weight=1)
        self.tables_frame.columnconfigure(1, weight=1)
        self.tables_frame.rowconfigure(0, weight=1)
        
        # Investor Positions Table
        self.positions_table = DataTableFrame(self.tables_frame, title="👥 Investor Positions")
        self.positions_table.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Recent Transactions Table
        self.transactions_table = DataTableFrame(self.tables_frame, title="📋 Recent Transactions")
        self.transactions_table.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
    
    def refresh_data(self):
        """Refresh all dashboard data"""
        if not self.db.connected:
            return
        
        # Update portfolio summary
        summary = self.db.get_portfolio_summary()
        if summary:
            # Portfolio value
            self.card_portfolio.update_value(
                f"${summary['total_value']:,.2f}",
                f"Last update: {summary['last_update']}"
            )
            
            # NAV per share with change color
            nav_change = summary.get('nav_change', 0)
            nav_change_pct = summary.get('nav_change_pct', 0)
            
            if nav_change > 0:
                nav_color = COLORS['success']  # Green for up
                nav_subtitle = f"▲ ${nav_change:.4f} ({nav_change_pct:+.2f}%)"
            elif nav_change < 0:
                nav_color = COLORS['danger']   # Red for down
                nav_subtitle = f"▼ ${abs(nav_change):.4f} ({nav_change_pct:.2f}%)"
            else:
                nav_color = COLORS['text']     # Neutral
                nav_subtitle = "No change"
            
            self.card_nav.update_value(
                f"${summary['nav_per_share']:.4f}",
                nav_subtitle,
                color=nav_color
            )
            
            # Total shares
            self.card_shares.update_value(f"{summary['total_shares']:,.2f}")
        
        # Update investor count
        investor_count = self.db.get_investor_count()
        self.card_investors.update_value(str(investor_count))
        
        # Update investor positions table and pie chart
        cols, investors = self.db.get_investors()
        if investors and isinstance(investors, list) and len(investors) > 0:
            # Update positions table
            headers = ["ID", "Name", "Shares", "Net Inv", "NAV", "Value", "Gain"]
            rows = []
            for inv in investors:
                try:
                    rows.append([
                        str(inv[0]) if inv[0] else "",  # investor_id
                        str(inv[1]) if inv[1] else "",  # name
                        f"{float(inv[2] or 0):,.2f}",   # shares
                        f"${float(inv[3] or 0):,.2f}",  # net_investment
                        f"${float(inv[5] or 0):.4f}",  # nav_per_share
                        f"${float(inv[6] or 0):,.2f}",  # current_value
                        f"${float(inv[7] or 0):,.2f}"   # unrealized_gain
                    ])
                except (IndexError, TypeError, ValueError) as e:
                    print(f"Error processing investor row: {e}")
                    continue
            
            if rows:
                self.positions_table.update_data(headers, rows)
            
            # Update allocation pie chart
            try:
                names = [str(inv[1]) for inv in investors if inv[1]]
                values = [float(inv[6]) for inv in investors if inv[6] and float(inv[6]) > 0]
                names = names[:len(values)]
                if values:
                    self.allocation_chart.create_pie_chart(names, values)
            except (IndexError, TypeError, ValueError) as e:
                print(f"Error creating allocation chart: {e}")
        else:
            # Show "no data" message
            self.positions_table.update_data(["Message"], [["No investor data found"]])
        
        # Update NAV history chart
        cols, nav_history = self.db.get_nav_history(days=60)
        if nav_history and isinstance(nav_history, list) and len(nav_history) > 0:
            try:
                dates = []
                nav_values = []
                for row in nav_history:
                    try:
                        dates.append(datetime.strptime(str(row[0]), '%Y-%m-%d'))
                        nav_values.append(float(row[1]))
                    except (ValueError, TypeError):
                        continue
                
                if dates and nav_values:
                    self.nav_chart.create_line_chart(dates, nav_values, ylabel="NAV per Share")
            except Exception as e:
                print(f"Error creating NAV chart: {e}")
        
        # Update recent transactions
        cols, transactions = self.db.get_recent_transactions(limit=10)
        if transactions and isinstance(transactions, list) and len(transactions) > 0:
            headers = ["Date", "Investor", "Type", "Amount", "Shares", "NAV"]
            rows = []
            for txn in transactions:
                try:
                    rows.append([
                        str(txn[0]) if txn[0] else "",
                        str(txn[1]) if txn[1] else "Unknown",
                        str(txn[2]) if txn[2] else "",
                        f"${float(txn[3] or 0):,.2f}",
                        f"{float(txn[4] or 0):,.2f}",
                        f"${float(txn[5] or 0):.4f}"
                    ])
                except (IndexError, TypeError, ValueError) as e:
                    print(f"Error processing transaction row: {e}")
                    continue
            
            if rows:
                self.transactions_table.update_data(headers, rows)
        else:
            self.transactions_table.update_data(["Message"], [["No recent transactions"]])


class DataExplorerTab(ctk.CTkFrame):
    """Data explorer tab for SQL queries and table viewing"""
    
    def __init__(self, parent, db_manager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.db = db_manager
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create data explorer widgets"""
        # Top section - Table selector and SQL input
        self.top_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.top_frame.pack(fill="x", padx=10, pady=10)
        
        # Table selector
        self.table_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.table_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            self.table_frame,
            text="Select Table:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 10))
        
        tables = self.db.get_tables() if self.db.connected else ["No database connected"]
        self.table_dropdown = ctk.CTkComboBox(
            self.table_frame,
            values=tables,
            width=200,
            command=self.on_table_select
        )
        self.table_dropdown.pack(side="left", padx=5)
        
        self.view_table_btn = ctk.CTkButton(
            self.table_frame,
            text="View Table",
            width=100,
            command=self.view_selected_table
        )
        self.view_table_btn.pack(side="left", padx=5)
        
        self.export_btn = ctk.CTkButton(
            self.table_frame,
            text="Export CSV",
            width=100,
            fg_color=COLORS['success'],
            command=self.export_to_csv
        )
        self.export_btn.pack(side="left", padx=5)
        
        # SQL Query input
        self.sql_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.sql_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkLabel(
            self.sql_frame,
            text="Custom SQL:",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w")
        
        self.sql_input = ctk.CTkTextbox(
            self.sql_frame,
            height=80,
            fg_color=COLORS['bg_dark'],
            text_color=COLORS['text']
        )
        self.sql_input.pack(fill="x", pady=5)
        self.sql_input.insert("0.0", "SELECT * FROM daily_nav ORDER BY date DESC LIMIT 20")
        
        self.run_sql_btn = ctk.CTkButton(
            self.sql_frame,
            text="▶ Run Query",
            width=120,
            fg_color=COLORS['highlight'],
            command=self.run_custom_sql
        )
        self.run_sql_btn.pack(anchor="w")
        
        # Results section
        self.results_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Status bar
        self.status_label = ctk.CTkLabel(
            self.results_frame,
            text="Ready",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary']
        )
        self.status_label.pack(anchor="w", padx=15, pady=10)
        
        # Results table container
        self.results_scroll = ctk.CTkScrollableFrame(
            self.results_frame,
            fg_color="transparent"
        )
        self.results_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Store current results
        self.current_columns = []
        self.current_data = []
    
    def on_table_select(self, table_name):
        """Handle table selection"""
        pass  # Can add preview functionality
    
    def view_selected_table(self):
        """View the selected table"""
        table_name = self.table_dropdown.get()
        if table_name and table_name != "No database connected":
            cols, results = self.db.get_table_data(table_name)
            self.display_results(cols, results, f"SELECT * FROM {table_name}")
    
    def run_custom_sql(self):
        """Run custom SQL query"""
        query = self.sql_input.get("0.0", "end").strip()
        if query:
            cols, results = self.db.execute_query(query)
            self.display_results(cols, results, query)
    
    def display_results(self, columns, results, query=""):
        """Display query results in table"""
        # Clear previous results
        for widget in self.results_scroll.winfo_children():
            widget.destroy()
        
        if columns is None:
            # Error occurred
            self.status_label.configure(
                text=f"❌ Error: {results}",
                text_color=COLORS['danger']
            )
            return
        
        if not results:
            self.status_label.configure(
                text="No results returned",
                text_color=COLORS['warning']
            )
            return
        
        # Store for export
        self.current_columns = columns
        self.current_data = results
        
        # Update status
        self.status_label.configure(
            text=f"✅ {len(results)} rows returned",
            text_color=COLORS['success']
        )
        
        # Format data for display
        formatted_rows = []
        for row in results:
            formatted_row = []
            for val in row:
                if val is None:
                    formatted_row.append("NULL")
                elif isinstance(val, float):
                    formatted_row.append(f"{val:.4f}")
                else:
                    # Truncate long strings for display
                    s = str(val)
                    formatted_row.append(s[:50] if len(s) > 50 else s)
            formatted_rows.append(formatted_row)
        
        # Create table data with headers
        table_data = [list(columns)] + formatted_rows[:100]
        
        try:
            # Create table with explicit row/column count
            table = CTkTable(
                master=self.results_scroll,
                values=table_data,
                header_color=COLORS['accent'],
                hover_color=COLORS['bg_dark'],
                colors=[COLORS['bg_card'], COLORS['bg_dark']],
                text_color=COLORS['text'],
                corner_radius=5,
                wraplength=150
            )
            table.pack(fill="both", expand=True, padx=5, pady=5)
        except Exception as e:
            # Fallback: display as text if CTkTable fails
            self.status_label.configure(
                text=f"⚠️ Table widget error, showing as text. {len(results)} rows.",
                text_color=COLORS['warning']
            )
            
            # Create text display instead
            text_widget = ctk.CTkTextbox(
                self.results_scroll,
                fg_color=COLORS['bg_dark'],
                text_color=COLORS['text'],
                font=ctk.CTkFont(family="Consolas", size=11)
            )
            text_widget.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Format as text table
            col_widths = []
            for i, col in enumerate(columns):
                max_width = len(str(col))
                for row in formatted_rows[:100]:
                    if i < len(row):
                        max_width = max(max_width, len(str(row[i])))
                col_widths.append(min(max_width + 2, 25))
            
            # Header
            header_line = ""
            for i, col in enumerate(columns):
                header_line += str(col).ljust(col_widths[i])
            text_widget.insert("end", header_line + "\n")
            text_widget.insert("end", "-" * sum(col_widths) + "\n")
            
            # Data rows
            for row in formatted_rows[:100]:
                row_line = ""
                for i, val in enumerate(row):
                    if i < len(col_widths):
                        row_line += str(val).ljust(col_widths[i])
                text_widget.insert("end", row_line + "\n")
            
            text_widget.configure(state="disabled")
        
        if len(results) > 100:
            ctk.CTkLabel(
                self.results_scroll,
                text=f"Showing first 100 of {len(results)} rows",
                text_color=COLORS['warning']
            ).pack(pady=5)
    
    def export_to_csv(self):
        """Export current results to CSV"""
        if not self.current_data:
            self.status_label.configure(
                text="No data to export",
                text_color=COLORS['warning']
            )
            return
        
        # Use file dialog to let user choose save location
        from tkinter import filedialog
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"export_{timestamp}.csv"
        
        filename = filedialog.asksaveasfilename(
            title="Save CSV Export",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=default_filename
        )
        
        if not filename:
            # User cancelled
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                # Write headers
                f.write(",".join(str(col) for col in self.current_columns) + "\n")
                # Write data
                for row in self.current_data:
                    formatted = []
                    for val in row:
                        if val is None:
                            formatted.append("")
                        elif isinstance(val, str) and ("," in val or '"' in val or '\n' in val):
                            # Escape quotes and wrap in quotes
                            formatted.append(f'"{val.replace(chr(34), chr(34)+chr(34))}"')
                        else:
                            formatted.append(str(val))
                    f.write(",".join(formatted) + "\n")
            
            self.status_label.configure(
                text=f"✅ Exported to {filename}",
                text_color=COLORS['success']
            )
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Export failed: {str(e)}",
                text_color=COLORS['danger']
            )


class TradingJournalTab(ctk.CTkFrame):
    """Trading journal tab for viewing trades"""
    
    def __init__(self, parent, db_manager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.db = db_manager
        
        self.create_widgets()
        self.refresh_data()
    
    def create_widgets(self):
        """Create trading journal widgets"""
        # Top section - Summary cards
        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.pack(fill="x", padx=10, pady=10)
        
        for i in range(4):
            self.summary_frame.columnconfigure(i, weight=1)
        
        self.card_trades = MetricCard(
            self.summary_frame, "Total Trades", "0"
        )
        self.card_trades.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.card_commission = MetricCard(
            self.summary_frame, "Total Commissions", "$0.00",
            color=COLORS['danger']
        )
        self.card_commission.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        self.card_symbols = MetricCard(
            self.summary_frame, "Unique Symbols", "0"
        )
        self.card_symbols.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        
        self.card_volume = MetricCard(
            self.summary_frame, "Trading Volume", "$0.00",
            color=COLORS['success']
        )
        self.card_volume.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        
        # Filter section
        self.filter_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.filter_frame.pack(fill="x", padx=10, pady=5)
        
        filter_inner = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        filter_inner.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(filter_inner, text="Symbol:").pack(side="left", padx=(0, 5))
        self.symbol_filter = ctk.CTkEntry(filter_inner, width=100, placeholder_text="e.g., SGOV")
        self.symbol_filter.pack(side="left", padx=5)
        
        ctk.CTkLabel(filter_inner, text="Category:").pack(side="left", padx=(20, 5))
        self.category_filter = ctk.CTkComboBox(
            filter_inner,
            values=["All", "Trade", "ACH", "Dividend", "Fee"],
            width=120
        )
        self.category_filter.set("All")
        self.category_filter.pack(side="left", padx=5)
        
        ctk.CTkLabel(filter_inner, text="Limit:").pack(side="left", padx=(20, 5))
        self.limit_filter = ctk.CTkEntry(filter_inner, width=60, placeholder_text="100")
        self.limit_filter.insert(0, "100")
        self.limit_filter.pack(side="left", padx=5)
        
        self.filter_btn = ctk.CTkButton(
            filter_inner,
            text="Apply Filter",
            width=100,
            command=self.apply_filter
        )
        self.filter_btn.pack(side="left", padx=20)
        
        # Trades table
        self.trades_table = DataTableFrame(self, title="📊 Trading Journal")
        self.trades_table.pack(fill="both", expand=True, padx=10, pady=10)
    
    def refresh_data(self):
        """Refresh trading data"""
        if not self.db.connected:
            return
        
        # Check if trades table exists
        tables = self.db.get_tables()
        if 'trades' not in tables:
            # Show message
            for widget in self.trades_table.scroll_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(
                self.trades_table.scroll_frame,
                text="Trading journal not available.\nRun: python scripts/import_tradier_history.py --import",
                text_color=COLORS['warning'],
                font=ctk.CTkFont(size=14)
            ).pack(pady=50)
            return
        
        # Get summary stats
        cols, results = self.db.execute_query("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(ABS(commission)) as total_commission,
                COUNT(DISTINCT symbol) as unique_symbols,
                SUM(ABS(amount)) as trading_volume
            FROM trades
            WHERE category = 'Trade'
        """)
        
        if results and len(results) > 0:
            self.card_trades.update_value(str(results[0][0] or 0))
            self.card_commission.update_value(f"${(results[0][1] or 0):,.2f}")
            self.card_symbols.update_value(str(results[0][2] or 0))
            self.card_volume.update_value(f"${(results[0][3] or 0):,.2f}")
        
        # Load trades
        self.apply_filter()
    
    def apply_filter(self):
        """Apply filters and load trades"""
        symbol = self.symbol_filter.get().strip().upper()
        category = self.category_filter.get()
        try:
            limit = int(self.limit_filter.get())
        except ValueError:
            limit = 100
        
        # Build query
        conditions = []
        params = []
        
        if symbol:
            conditions.append("symbol LIKE ?")
            params.append(f"%{symbol}%")
        
        if category != "All":
            conditions.append("category = ?")
            params.append(category)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT 
                date,
                symbol,
                category,
                type,
                quantity,
                price,
                amount,
                commission,
                option_type,
                strike,
                expiration_date,
                description
            FROM trades
            {where_clause}
            ORDER BY date DESC
            LIMIT ?
        """
        params.append(limit)
        
        cols, results = self.db.execute_query(query, tuple(params))
        
        if results and isinstance(results, list):
            headers = ["Date", "Symbol", "Cat", "Type", "Qty", "Price", "Amount", "Comm", "Opt", "Strike", "Expiry", "Description"]
            rows = []
            for trade in results:
                rows.append([
                    trade[0] or "",                                          # date
                    trade[1] or "",                                          # symbol
                    trade[2] or "",                                          # category
                    trade[3] or "",                                          # type
                    f"{trade[4]:.0f}" if trade[4] else "",                   # quantity
                    f"${trade[5]:.2f}" if trade[5] else "",                  # price
                    f"${trade[6]:,.2f}" if trade[6] else "",                 # amount
                    f"${trade[7]:.2f}" if trade[7] else "",                  # commission
                    trade[8] or "",                                          # option_type
                    f"${trade[9]:.2f}" if trade[9] else "",                  # strike
                    trade[10] or "",                                         # expiration_date
                    (trade[11] or "")[:30]                                   # description
                ])
            self.trades_table.update_data(headers, rows)
        else:
            self.trades_table.update_data([], [])


class TaxManagementTab(ctk.CTkFrame):
    """Tax management tab"""
    
    def __init__(self, parent, db_manager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.db = db_manager
        
        self.create_widgets()
        self.refresh_data()
    
    def create_widgets(self):
        """Create tax management widgets"""
        # Summary cards
        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.pack(fill="x", padx=10, pady=10)
        
        for i in range(4):
            self.summary_frame.columnconfigure(i, weight=1)
        
        self.card_total_gains = MetricCard(
            self.summary_frame, "Total Unrealized Gains", "$0.00",
            color=COLORS['success']
        )
        self.card_total_gains.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.card_tax_liability = MetricCard(
            self.summary_frame, "Est. Tax Liability (37%)", "$0.00",
            color=COLORS['danger']
        )
        self.card_tax_liability.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        self.card_ytd_realized = MetricCard(
            self.summary_frame, "YTD Realized Gains", "$0.00"
        )
        self.card_ytd_realized.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        
        self.card_ytd_taxes = MetricCard(
            self.summary_frame, "YTD Taxes Withheld", "$0.00"
        )
        self.card_ytd_taxes.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        
        # Two column layout
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_frame.rowconfigure(0, weight=1)
        
        # Investor tax positions
        self.tax_positions = DataTableFrame(self.content_frame, title="💰 Investor Tax Positions")
        self.tax_positions.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Tax events history
        self.tax_events = DataTableFrame(self.content_frame, title="📜 Tax Events History")
        self.tax_events.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
    
    def refresh_data(self):
        """Refresh tax data"""
        if not self.db.connected:
            return
        
        # Get investor tax positions
        cols, investors = self.db.get_investors()
        
        if investors and isinstance(investors, list):
            total_gains = sum(inv[7] for inv in investors if inv[7] and inv[7] > 0)
            tax_rate = 0.37
            tax_liability = total_gains * tax_rate
            
            self.card_total_gains.update_value(f"${total_gains:,.2f}")
            self.card_tax_liability.update_value(f"${tax_liability:,.2f}")
            
            # Update tax positions table
            headers = ["Investor", "Net Inv", "Value", "Gain", "Tax (37%)", "After-Tax"]
            rows = []
            for inv in investors:
                gain = inv[7] if inv[7] else 0
                tax = max(0, gain * tax_rate)
                after_tax = (inv[6] or 0) - tax
                rows.append([
                    inv[1],  # name
                    f"${inv[3]:,.2f}",  # net_investment
                    f"${inv[6]:,.2f}" if inv[6] else "$0.00",  # current_value
                    f"${gain:,.2f}",
                    f"${tax:,.2f}",
                    f"${after_tax:,.2f}"
                ])
            self.tax_positions.update_data(headers, rows)
        
        # Get tax events if table exists
        tables = self.db.get_tables()
        if 'tax_events' in tables:
            cols, events = self.db.execute_query("""
                SELECT date, investor_id, event_type, realized_gain, tax_due, notes
                FROM tax_events
                ORDER BY date DESC
                LIMIT 20
            """)
            
            if events and isinstance(events, list):
                ytd_realized = sum(e[3] for e in events if e[3])
                ytd_taxes = sum(e[4] for e in events if e[4])
                
                self.card_ytd_realized.update_value(f"${ytd_realized:,.2f}")
                self.card_ytd_taxes.update_value(f"${ytd_taxes:,.2f}")
                
                headers = ["Date", "Investor", "Event", "Realized", "Tax Due", "Notes"]
                rows = []
                for event in events:
                    rows.append([
                        event[0],
                        event[1],
                        event[2],
                        f"${event[3]:,.2f}" if event[3] else "$0.00",
                        f"${event[4]:,.2f}" if event[4] else "$0.00",
                        (event[5] or "")[:30]
                    ])
                self.tax_events.update_data(headers, rows)


class SettingsTab(ctk.CTkFrame):
    """Settings tab"""
    
    def __init__(self, parent, db_manager, app, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.db = db_manager
        self.app = app
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create settings widgets"""
        # Database connection
        self.db_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.db_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            self.db_frame,
            text="⚙️ Database Connection",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Connection status
        status_frame = ctk.CTkFrame(self.db_frame, fg_color="transparent")
        status_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(status_frame, text="Status:").pack(side="left", padx=(0, 10))
        
        status_text = "✅ Connected" if self.db.connected else "❌ Not Connected"
        status_color = COLORS['success'] if self.db.connected else COLORS['danger']
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text=status_text,
            text_color=status_color,
            font=ctk.CTkFont(weight="bold")
        )
        self.status_label.pack(side="left")
        
        # Database path
        path_frame = ctk.CTkFrame(self.db_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(path_frame, text="Path:").pack(side="left", padx=(0, 10))
        
        self.path_entry = ctk.CTkEntry(path_frame, width=400)
        self.path_entry.pack(side="left", padx=5)
        if self.db.db_path:
            self.path_entry.insert(0, self.db.db_path)
        
        self.browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            width=80,
            command=self.browse_database
        )
        self.browse_btn.pack(side="left", padx=5)
        
        self.connect_btn = ctk.CTkButton(
            path_frame,
            text="Connect",
            width=80,
            fg_color=COLORS['success'],
            command=self.connect_database
        )
        self.connect_btn.pack(side="left", padx=5)
        
        # Appearance
        self.appearance_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.appearance_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            self.appearance_frame,
            text="🎨 Appearance",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        theme_frame = ctk.CTkFrame(self.appearance_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkLabel(theme_frame, text="Color Theme:").pack(side="left", padx=(0, 10))
        
        # Get theme names from THEMES dict
        theme_names = [THEMES[t]['name'] for t in THEMES.keys()]
        
        self.theme_dropdown = ctk.CTkComboBox(
            theme_frame,
            values=theme_names,
            width=150,
            command=self.change_color_theme
        )
        self.theme_dropdown.set("Dark Gray")
        self.theme_dropdown.pack(side="left", padx=5)
        
        # System appearance mode
        mode_frame = ctk.CTkFrame(self.appearance_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkLabel(mode_frame, text="System Mode:").pack(side="left", padx=(0, 10))
        
        self.mode_dropdown = ctk.CTkComboBox(
            mode_frame,
            values=["Dark", "Light", "System"],
            width=150,
            command=self.change_appearance_mode
        )
        self.mode_dropdown.set("Dark")
        self.mode_dropdown.pack(side="left", padx=5)
        
        # Note about theme changes
        ctk.CTkLabel(
            self.appearance_frame,
            text="Note: Some color changes require restarting the app.",
            text_color=COLORS['text_secondary'],
            font=ctk.CTkFont(size=10)
        ).pack(anchor="w", padx=15, pady=(0, 10))
        
        # About
        self.about_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_card'], corner_radius=10)
        self.about_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            self.about_frame,
            text="ℹ️ About",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            self.about_frame,
            text="Tovito Trader Dashboard v1.0\n\n"
                 "A professional fund management dashboard for tracking:\n"
                 "• Investor positions and NAV\n"
                 "• Trading activity and journal\n"
                 "• Tax management\n"
                 "• Custom SQL queries\n\n"
                 "Built with CustomTkinter",
            text_color=COLORS['text_secondary'],
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 15))
    
    def browse_database(self):
        """Open file dialog to browse for database"""
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            title="Select Database",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if filename:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, filename)
    
    def connect_database(self):
        """Connect to the specified database"""
        db_path = self.path_entry.get()
        if db_path and os.path.exists(db_path):
            self.db.db_path = db_path
            self.db.connected = True
            self.status_label.configure(text="✅ Connected", text_color=COLORS['success'])
            # Refresh dashboard
            self.app.dashboard_tab.refresh_data()
        else:
            self.status_label.configure(text="❌ File not found", text_color=COLORS['danger'])
    
    def change_color_theme(self, theme_name):
        """Change color theme"""
        # Find theme key by name
        theme_key = None
        for key, theme in THEMES.items():
            if theme['name'] == theme_name:
                theme_key = key
                break
        
        if theme_key:
            set_theme(theme_key)
            # Show message about restart
            print(f"Theme changed to {theme_name}. Restart app for full effect.")
    
    def change_appearance_mode(self, mode):
        """Change system appearance mode (Dark/Light/System)"""
        ctk.set_appearance_mode(mode.lower())


class TovitoDashboard(ctk.CTk):
    """Main application window"""
    
    def __init__(self, db_path=None):
        super().__init__()
        
        # Initialize database
        self.db = DatabaseManager(db_path)
        
        # Window configuration
        self.title("Tovito Trader - Dashboard")
        self.geometry("1400x900")
        self.minsize(1200, 700)
        
        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Create main container
        self.main_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_dark'])
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        self.create_header()
        
        # Tab view
        self.create_tabs()
        
        # Status bar
        self.create_statusbar()
    
    def create_header(self):
        """Create header with title and refresh button"""
        self.header = ctk.CTkFrame(self.main_frame, fg_color=COLORS['accent'], height=60)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        
        # Title
        title_label = ctk.CTkLabel(
            self.header,
            text="📊 TOVITO TRADER DASHBOARD",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS['text']
        )
        title_label.pack(side="left", padx=20, pady=15)
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            self.header,
            text="🔄 Refresh",
            width=100,
            fg_color=COLORS['highlight'],
            command=self.refresh_all
        )
        refresh_btn.pack(side="right", padx=20, pady=15)
        
        # Connection indicator
        status_text = "🟢 Connected" if self.db.connected else "🔴 Not Connected"
        self.connection_label = ctk.CTkLabel(
            self.header,
            text=status_text,
            font=ctk.CTkFont(size=12)
        )
        self.connection_label.pack(side="right", padx=20, pady=15)
    
    def create_tabs(self):
        """Create tab navigation"""
        self.tabview = ctk.CTkTabview(
            self.main_frame,
            fg_color=COLORS['bg_dark'],
            segmented_button_fg_color=COLORS['accent'],
            segmented_button_selected_color=COLORS['highlight'],
            segmented_button_unselected_color=COLORS['bg_card']
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Add tabs
        self.tabview.add("📊 Dashboard")
        if HAS_ALERTS:
            self.tabview.add("🚨 Alerts")
        self.tabview.add("🔍 Data Explorer")
        self.tabview.add("📈 Trading Journal")
        self.tabview.add("💰 Tax Management")
        self.tabview.add("⚙️ Settings")
        
        # Create tab content
        self.dashboard_tab = DashboardTab(self.tabview.tab("📊 Dashboard"), self.db)
        self.dashboard_tab.pack(fill="both", expand=True)
        
        # Alerts tab (if available)
        if HAS_ALERTS:
            try:
                self.alerts_tab = AlertsTab(self.tabview.tab("🚨 Alerts"), self.db)
                self.alerts_tab.pack(fill="both", expand=True)
            except Exception as e:
                print(f"Error creating Alerts tab: {e}")
        
        self.explorer_tab = DataExplorerTab(self.tabview.tab("🔍 Data Explorer"), self.db)
        self.explorer_tab.pack(fill="both", expand=True)
        
        self.trading_tab = TradingJournalTab(self.tabview.tab("📈 Trading Journal"), self.db)
        self.trading_tab.pack(fill="both", expand=True)
        
        self.tax_tab = TaxManagementTab(self.tabview.tab("💰 Tax Management"), self.db)
        self.tax_tab.pack(fill="both", expand=True)
        
        self.settings_tab = SettingsTab(self.tabview.tab("⚙️ Settings"), self.db, self)
        self.settings_tab.pack(fill="both", expand=True)
    
    def create_statusbar(self):
        """Create status bar"""
        self.statusbar = ctk.CTkFrame(self.main_frame, fg_color=COLORS['accent'], height=30)
        self.statusbar.grid(row=2, column=0, sticky="ew")
        self.statusbar.grid_propagate(False)
        
        # Database path
        db_text = f"Database: {self.db.db_path}" if self.db.db_path else "No database connected"
        self.db_label = ctk.CTkLabel(
            self.statusbar,
            text=db_text,
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary']
        )
        self.db_label.pack(side="left", padx=10, pady=5)
        
        # Timestamp
        self.time_label = ctk.CTkLabel(
            self.statusbar,
            text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary']
        )
        self.time_label.pack(side="right", padx=10, pady=5)
        
        # Update time periodically
        self.update_time()
    
    def update_time(self):
        """Update the time display"""
        self.time_label.configure(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.after(1000, self.update_time)
    
    def refresh_all(self):
        """Refresh all tabs"""
        self.dashboard_tab.refresh_data()
        self.trading_tab.refresh_data()
        self.tax_tab.refresh_data()
        # Update connection status
        status_text = "🟢 Connected" if self.db.connected else "🔴 Not Connected"
        self.connection_label.configure(text=status_text)


def main():
    """Main entry point"""
    # Check for database path argument
    db_path = None
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    app = TovitoDashboard(db_path)
    app.mainloop()


if __name__ == "__main__":
    main()
