"""
Chart Generation for Monthly Reports
=====================================
Generates PNG chart images using matplotlib for embedding into
ReportLab PDF investor statements.

Uses the matplotlib 'Agg' backend (headless) so charts can be
generated in environments without a display (Task Scheduler, CI).

Charts:
    1. NAV Time Series — NAV per share over time with trade count overlay
    2. Investor Account Value — Per-investor value with event markers
    3. Portfolio Holdings — Current positions by market value

All chart functions return a Path to a temporary PNG file.
Callers are responsible for cleanup after embedding into PDF.
"""

import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> datetime:
    """Parse date string, handling YYYY-MM-DD and ISO 8601 variants."""
    # Strip any time/timezone suffix (e.g. T00:00:00Z, T16:00:00+00:00)
    clean = date_str.strip()[:10]
    return datetime.strptime(clean, '%Y-%m-%d')


# ============================================================
# CHART STYLE CONSTANTS
# ============================================================

# Color palette — professional, muted tones
COLORS = {
    'primary': '#1e3a5f',       # Dark navy blue — NAV line
    'secondary': '#4a90d9',     # Medium blue — fill/bars
    'positive': '#2d8a4e',      # Green — gains, contributions
    'negative': '#c0392b',      # Red — losses, withdrawals
    'grid': '#e0e0e0',          # Light gray — gridlines
    'text': '#333333',          # Dark gray — labels
    'background': '#fafafa',    # Off-white — chart background
    'bar_alpha': 0.30,          # Transparency for overlay bars
    'fill_alpha': 0.12,         # Transparency for area fill
}

# Instrument type colors for holdings chart
INSTRUMENT_COLORS = {
    'Equity': '#1e3a5f',
    'Equity Option': '#4a90d9',
    'Future': '#e67e22',
    'Future Option': '#f39c12',
    'Cryptocurrency': '#8e44ad',
    'Other': '#95a5a6',
}

CHART_DPI = 150
CHART_WIDTH = 7.5   # inches (fits letter page with margins)
CHART_HEIGHT = 4.0  # inches


def _setup_chart_style():
    """Apply consistent style to all charts."""
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 9,
        'axes.titlesize': 12,
        'axes.titleweight': 'bold',
        'axes.labelsize': 10,
        'axes.facecolor': COLORS['background'],
        'figure.facecolor': 'white',
        'grid.color': COLORS['grid'],
        'grid.linewidth': 0.5,
    })


def _save_chart(fig, prefix='chart') -> Path:
    """Save figure to a temporary PNG file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        suffix='.png', prefix=f'tovito_{prefix}_', delete=False
    )
    fig.savefig(tmp.name, dpi=CHART_DPI, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    logger.info("Chart saved: %s", tmp.name)
    return Path(tmp.name)


# ============================================================
# CHART 1: NAV TIME SERIES
# ============================================================

def generate_nav_chart(
    nav_history: List[Dict],
    trade_counts: Optional[List[Dict]] = None,
) -> Path:
    """
    Generate NAV per share time series chart.

    Primary Y-axis: NAV per share as a line chart with area fill.
    Secondary Y-axis: Daily trade count as a bar chart (optional).

    Args:
        nav_history: List of dicts with keys:
            'date' (str YYYY-MM-DD), 'nav_per_share' (float)
        trade_counts: Optional list of dicts with keys:
            'date' (str YYYY-MM-DD), 'trade_count' (int)

    Returns:
        Path to temporary PNG file.
    """
    _setup_chart_style()

    if not nav_history:
        return _generate_empty_chart("NAV Performance", "No NAV data available")

    # Parse dates (handles YYYY-MM-DD and ISO 8601 variants)
    dates = [_parse_date(r['date']) for r in nav_history]
    navs = [r['nav_per_share'] for r in nav_history]

    fig, ax1 = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT))

    # NAV line (primary axis)
    ax1.plot(dates, navs, color=COLORS['primary'], linewidth=2,
             label='NAV per Share', zorder=3)
    ax1.fill_between(dates, navs, alpha=COLORS['fill_alpha'],
                      color=COLORS['secondary'])

    ax1.set_xlabel('Date', color=COLORS['text'])
    ax1.set_ylabel('NAV per Share ($)', color=COLORS['primary'])
    ax1.tick_params(axis='y', labelcolor=COLORS['primary'])
    ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter('$%.4f'))
    ax1.grid(True, alpha=0.3, zorder=0)

    # Format X axis dates
    _format_date_axis(ax1, dates)

    # Start NAV reference line
    if len(navs) > 1:
        ax1.axhline(y=navs[0], color=COLORS['grid'], linestyle='--',
                     linewidth=0.8, alpha=0.7, zorder=1)

    # Trade count bars (secondary axis)
    if trade_counts:
        ax2 = ax1.twinx()
        trade_dates = [_parse_date(r['date']) for r in trade_counts]
        counts = [r['trade_count'] for r in trade_counts]

        bar_width = max(0.5, min(2.0, 365 / max(len(trade_dates), 1)))
        ax2.bar(trade_dates, counts, width=bar_width,
                color=COLORS['secondary'], alpha=COLORS['bar_alpha'],
                label='Daily Trades', zorder=2)

        ax2.set_ylabel('Trades per Day', color=COLORS['secondary'])
        ax2.tick_params(axis='y', labelcolor=COLORS['secondary'])
        ax2.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2,
                   loc='upper left', framealpha=0.9, fontsize=8)
    else:
        ax1.legend(loc='upper left', framealpha=0.9, fontsize=8)

    # Title with date range
    start = dates[0].strftime('%b %d, %Y')
    end = dates[-1].strftime('%b %d, %Y')
    ax1.set_title(f'NAV Performance  ({start} - {end})',
                  fontsize=12, fontweight='bold', color=COLORS['text'])

    fig.tight_layout()
    return _save_chart(fig, 'nav')


# ============================================================
# CHART 2: INVESTOR ACCOUNT VALUE
# ============================================================

def generate_investor_value_chart(
    nav_history: List[Dict],
    investor_shares: float,
    investor_transactions: Optional[List[Dict]] = None,
) -> Path:
    """
    Generate per-investor account value over time.

    Line chart showing account value (shares x NAV) with markers
    for contributions (green up arrow) and withdrawals (red down arrow).

    Reconstructs the investor's share count over time from transactions
    so the chart accurately reflects the value at each point, not just
    current shares × historical NAV.

    Args:
        nav_history: List of dicts with keys:
            'date' (str YYYY-MM-DD), 'nav_per_share' (float)
        investor_shares: Current share count for this investor (used as
            fallback if no transaction history available).
        investor_transactions: Optional list of dicts with keys:
            'date' (str YYYY-MM-DD), 'transaction_type' (str),
            'amount' (float), 'shares_transacted' (float, optional)

    Returns:
        Path to temporary PNG file.
    """
    _setup_chart_style()

    if not nav_history:
        return _generate_empty_chart("Account Value", "No NAV data available")

    dates = [_parse_date(r['date']) for r in nav_history]

    # Reconstruct share count at each date from transactions.
    # Without shares_transacted data, fall back to constant shares.
    if investor_transactions and any(t.get('shares_transacted') for t in investor_transactions):
        # Build a chronological list of (date, share_delta) events
        share_events = []
        for txn in investor_transactions:
            try:
                txn_date = _parse_date(txn['date'])
            except (ValueError, KeyError):
                continue
            shares = txn.get('shares_transacted', 0) or 0
            txn_type = txn.get('transaction_type', '').lower()
            if txn_type == 'withdrawal':
                shares = -abs(shares)  # Withdrawals reduce share count
            else:
                shares = abs(shares)   # Contributions/initial add shares
            share_events.append((txn_date, shares))

        share_events.sort(key=lambda x: x[0])

        # Walk through NAV dates, accumulating shares
        values = []
        cumulative_shares = 0.0
        event_idx = 0
        for nav_date, nav_record in zip(dates, nav_history):
            # Apply any transactions on or before this date
            while event_idx < len(share_events) and share_events[event_idx][0] <= nav_date:
                cumulative_shares += share_events[event_idx][1]
                event_idx += 1
            values.append(nav_record['nav_per_share'] * cumulative_shares)
    else:
        # Fallback: constant shares (less accurate but works without history)
        values = [r['nav_per_share'] * investor_shares for r in nav_history]

    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT))

    # Value line
    ax.plot(dates, values, color=COLORS['primary'], linewidth=2,
            label='Account Value', zorder=3)
    ax.fill_between(dates, values, alpha=COLORS['fill_alpha'],
                     color=COLORS['secondary'])

    # Transaction event markers
    if investor_transactions:
        for txn in investor_transactions:
            try:
                txn_date = _parse_date(txn['date'])
            except (ValueError, KeyError):
                continue

            txn_type = txn.get('transaction_type', '').lower()
            amount = txn.get('amount', 0)

            # Find closest NAV value for marker placement
            closest_value = _find_closest_value(dates, values, txn_date)
            if closest_value is None:
                continue

            if txn_type in ('initial', 'contribution'):
                ax.annotate(
                    f'+${abs(amount):,.0f}',
                    xy=(txn_date, closest_value),
                    xytext=(0, 20),
                    textcoords='offset points',
                    ha='center', fontsize=7, fontweight='bold',
                    color=COLORS['positive'],
                    arrowprops=dict(
                        arrowstyle='->', color=COLORS['positive'],
                        lw=1.5
                    ),
                    zorder=5,
                )
            elif txn_type == 'withdrawal':
                ax.annotate(
                    f'-${abs(amount):,.0f}',
                    xy=(txn_date, closest_value),
                    xytext=(0, -25),
                    textcoords='offset points',
                    ha='center', fontsize=7, fontweight='bold',
                    color=COLORS['negative'],
                    arrowprops=dict(
                        arrowstyle='->', color=COLORS['negative'],
                        lw=1.5
                    ),
                    zorder=5,
                )

    ax.set_xlabel('Date', color=COLORS['text'])
    ax.set_ylabel('Account Value ($)', color=COLORS['text'])
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax.grid(True, alpha=0.3, zorder=0)

    _format_date_axis(ax, dates)

    ax.set_title('Your Account Value Over Time',
                 fontsize=12, fontweight='bold', color=COLORS['text'])

    ax.legend(loc='upper left', framealpha=0.9, fontsize=8)
    fig.tight_layout()
    return _save_chart(fig, 'investor_value')


# ============================================================
# CHART 3: PORTFOLIO HOLDINGS
# ============================================================

def generate_holdings_chart(
    positions: List[Dict],
    max_positions: int = 10,
) -> Path:
    """
    Generate horizontal bar chart of current portfolio holdings.

    Shows each position's market value, color-coded by instrument type.
    Groups small positions into "Other" when there are more than
    max_positions holdings.

    Args:
        positions: List of dicts with keys:
            'symbol' (str), 'underlying_symbol' (str, optional),
            'market_value' (float), 'instrument_type' (str),
            'unrealized_pl' (float, optional)
        max_positions: Max positions before grouping into "Other".

    Returns:
        Path to temporary PNG file.
    """
    _setup_chart_style()

    if not positions:
        return _generate_empty_chart(
            "Portfolio Holdings", "No positions currently held"
        )

    # Aggregate by underlying symbol for cleaner display
    aggregated = _aggregate_positions(positions)

    # Sort by absolute market value
    aggregated.sort(key=lambda x: abs(x['market_value']), reverse=True)

    # Group small positions into "Other" if needed
    if len(aggregated) > max_positions:
        top = aggregated[:max_positions - 1]
        rest = aggregated[max_positions - 1:]
        other_value = sum(p['market_value'] for p in rest)
        other_pl = sum(p.get('unrealized_pl', 0) or 0 for p in rest)
        top.append({
            'label': f'Other ({len(rest)} positions)',
            'market_value': other_value,
            'unrealized_pl': other_pl,
            'instrument_type': 'Other',
        })
        aggregated = top

    # Build chart data
    labels = [p.get('label', p.get('underlying_symbol', p.get('symbol', '?')))
              for p in aggregated]
    values = [p['market_value'] for p in aggregated]
    pl_values = [p.get('unrealized_pl', 0) or 0 for p in aggregated]
    bar_colors = [
        INSTRUMENT_COLORS.get(p.get('instrument_type', 'Other'), INSTRUMENT_COLORS['Other'])
        for p in aggregated
    ]

    # Determine chart height based on number of positions
    bar_height = max(3.0, min(6.0, len(labels) * 0.5 + 1.0))

    fig, ax = plt.subplots(figsize=(CHART_WIDTH, bar_height))

    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=bar_colors, edgecolor='white',
                   linewidth=0.5, height=0.6, zorder=3)

    # Add value labels on bars
    for i, (bar, val, pl) in enumerate(zip(bars, values, pl_values)):
        # Value label
        x_offset = max(abs(val) * 0.02, 50)
        label_x = val + x_offset if val >= 0 else val - x_offset
        ha = 'left' if val >= 0 else 'right'

        val_text = f'${abs(val):,.0f}'
        if pl != 0:
            pl_color = COLORS['positive'] if pl > 0 else COLORS['negative']
            pl_text = f' ({pl:+,.0f})'
            ax.text(label_x, i, val_text, va='center', ha=ha,
                    fontsize=8, color=COLORS['text'], zorder=4)
            ax.text(label_x + len(val_text) * 80, i, pl_text, va='center',
                    ha=ha, fontsize=7, color=pl_color, zorder=4)
        else:
            ax.text(label_x, i, val_text, va='center', ha=ha,
                    fontsize=8, color=COLORS['text'], zorder=4)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel('Market Value ($)', color=COLORS['text'])
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax.grid(True, axis='x', alpha=0.3, zorder=0)
    ax.invert_yaxis()  # Largest value at top

    # Add legend for instrument types
    unique_types = list(set(
        p.get('instrument_type', 'Other') for p in aggregated
    ))
    if len(unique_types) > 1:
        legend_patches = [
            plt.Rectangle((0, 0), 1, 1,
                           fc=INSTRUMENT_COLORS.get(t, INSTRUMENT_COLORS['Other']),
                           label=t)
            for t in unique_types
        ]
        ax.legend(handles=legend_patches, loc='lower right',
                  framealpha=0.9, fontsize=7)

    ax.set_title('Current Portfolio Holdings',
                 fontsize=12, fontweight='bold', color=COLORS['text'])

    fig.tight_layout()
    return _save_chart(fig, 'holdings')


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _generate_empty_chart(title: str, message: str) -> Path:
    """Generate a placeholder chart when no data is available."""
    _setup_chart_style()
    fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT))

    ax.text(0.5, 0.5, message, transform=ax.transAxes,
            fontsize=14, ha='center', va='center',
            color=COLORS['text'], style='italic')
    ax.set_title(title, fontsize=12, fontweight='bold',
                 color=COLORS['text'])
    ax.axis('off')

    fig.tight_layout()
    return _save_chart(fig, 'empty')


def _format_date_axis(ax, dates):
    """Format X axis with smart date labels."""
    if not dates:
        return

    span_days = (dates[-1] - dates[0]).days

    if span_days <= 31:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    elif span_days <= 90:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    elif span_days <= 365:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')


def _find_closest_value(dates, values, target_date):
    """Find the value at the closest date to target_date."""
    if not dates or not values:
        return None

    closest_idx = 0
    closest_diff = abs((dates[0] - target_date).days)

    for i, d in enumerate(dates):
        diff = abs((d - target_date).days)
        if diff < closest_diff:
            closest_diff = diff
            closest_idx = i

    return values[closest_idx]


def _aggregate_positions(positions: List[Dict]) -> List[Dict]:
    """
    Aggregate positions by underlying symbol.

    Multiple option legs on the same underlying are combined into
    one row showing total market value and unrealized P&L.
    Equity positions are shown individually.
    """
    aggregated = {}

    for pos in positions:
        # Use underlying_symbol for grouping options, symbol for equities
        key = pos.get('underlying_symbol') or pos.get('symbol', 'Unknown')
        instrument = pos.get('instrument_type', 'Other')

        if key not in aggregated:
            aggregated[key] = {
                'label': key,
                'underlying_symbol': key,
                'market_value': 0.0,
                'unrealized_pl': 0.0,
                'instrument_type': instrument,
                'leg_count': 0,
            }

        entry = aggregated[key]
        entry['market_value'] += pos.get('market_value', 0) or 0
        entry['unrealized_pl'] += pos.get('unrealized_pl', 0) or 0
        entry['leg_count'] += 1

        # If any leg is an option, label the aggregate as Equity Option
        if 'option' in instrument.lower():
            entry['instrument_type'] = 'Equity Option'

    result = list(aggregated.values())

    # Update labels for multi-leg positions
    for entry in result:
        if entry['leg_count'] > 1:
            entry['label'] = f"{entry['label']} ({entry['leg_count']} legs)"

    return result
