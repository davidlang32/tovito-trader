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
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import numpy as np

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
from matplotlib.colors import to_rgba

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


def _save_chart(fig, prefix='chart', dpi: int = None) -> Path:
    """Save figure to a temporary PNG file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        suffix='.png', prefix=f'tovito_{prefix}_', delete=False
    )
    fig.savefig(tmp.name, dpi=dpi or CHART_DPI, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    logger.info("Chart saved: %s", tmp.name)
    return Path(tmp.name)


def _gradient_fill(ax, x, y, color, alpha_top=0.35, alpha_bottom=0.0, zorder=1):
    """
    Fill the area under a line with a vertical gradient (solid → transparent).

    Creates a gradient image clipped to the polygon formed by the data
    line and the x-axis.  This produces the "mountain" visual effect.

    Args:
        ax: Matplotlib axes to draw on.
        x: X values (list of datetime or numeric).
        y: Y values (list of float).
        color: Base color for the gradient (hex string or named color).
        alpha_top: Opacity at the top edge of the fill (0.0–1.0).
        alpha_bottom: Opacity at the bottom edge of the fill (0.0–1.0).
        zorder: Drawing order for the gradient layer.
    """
    if len(x) < 2 or len(y) < 2:
        return

    # Convert dates to matplotlib numeric format for imshow extent
    x_num = mdates.date2num(x)

    # We must set axis limits before clipping so the gradient spans correctly
    y_min = ax.get_ylim()[0]

    # Build polygon vertices: follow the line, then close along the bottom
    verts = list(zip(x_num, y))
    verts.append((x_num[-1], y_min))
    verts.append((x_num[0], y_min))
    verts.append(verts[0])  # Close the path

    codes = ([MplPath.MOVETO]
             + [MplPath.LINETO] * (len(verts) - 2)
             + [MplPath.CLOSEPOLY])
    clip_path = MplPath(verts, codes)
    patch = PathPatch(clip_path, facecolor='none', edgecolor='none')
    ax.add_patch(patch)

    # Build RGBA gradient: top row = (color, alpha_top) → bottom row = (color, alpha_bottom)
    rgba_top = np.array(to_rgba(color, alpha=alpha_top))
    rgba_bottom = np.array(to_rgba(color, alpha=alpha_bottom))
    gradient = np.linspace(rgba_top, rgba_bottom, 256).reshape(256, 1, 4)
    gradient = np.repeat(gradient, 2, axis=1)  # Need at least 2 columns

    # Render the gradient image spanning the full data extent
    y_lo, y_hi = ax.get_ylim()
    im = ax.imshow(
        gradient,
        aspect='auto',
        extent=[x_num[0], x_num[-1], y_lo, y_hi],
        origin='upper',
        zorder=zorder,
    )
    im.set_clip_path(patch)


# ============================================================
# CHART 1: NAV TIME SERIES
# ============================================================

def generate_nav_chart(
    nav_history: List[Dict],
    trade_counts: Optional[List[Dict]] = None,
    width: float = None,
    height: float = None,
    dpi: int = None,
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
        width: Chart width in inches (default: CHART_WIDTH).
        height: Chart height in inches (default: CHART_HEIGHT).
        dpi: Override DPI for saved image (default: CHART_DPI).

    Returns:
        Path to temporary PNG file.
    """
    _setup_chart_style()

    chart_w = width or CHART_WIDTH
    chart_h = height or CHART_HEIGHT

    if not nav_history:
        return _generate_empty_chart("NAV Performance", "No NAV data available")

    # Parse dates (handles YYYY-MM-DD and ISO 8601 variants)
    dates = [_parse_date(r['date']) for r in nav_history]
    navs = [r['nav_per_share'] for r in nav_history]

    fig, ax1 = plt.subplots(figsize=(chart_w, chart_h))

    # NAV line (primary axis)
    ax1.plot(dates, navs, color=COLORS['primary'], linewidth=2,
             label='NAV per Share', zorder=3)

    ax1.set_xlabel('Date', color=COLORS['text'])
    ax1.set_ylabel('NAV per Share ($)', color=COLORS['primary'])
    ax1.tick_params(axis='y', labelcolor=COLORS['primary'])
    ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter('$%.4f'))
    ax1.grid(True, alpha=0.3, zorder=0)

    # Format X axis dates
    _format_date_axis(ax1, dates)

    # Gradient mountain fill (must come after axis setup so limits are correct)
    _gradient_fill(ax1, dates, navs, COLORS['secondary'],
                   alpha_top=0.35, alpha_bottom=0.0, zorder=1)

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
    return _save_chart(fig, 'nav', dpi=dpi)


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

    # Gradient mountain fill (must come after axis setup so limits are correct)
    _gradient_fill(ax, dates, values, COLORS['secondary'],
                   alpha_top=0.35, alpha_bottom=0.0, zorder=1)

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


# ============================================================
# CHART 4: NAV vs BENCHMARKS COMPARISON
# ============================================================

# Benchmark line styles and colors
BENCHMARK_STYLES = {
    'SPY':     {'color': '#2d8a4e', 'linestyle': '--',  'label': 'S&P 500 (SPY)'},
    'QQQ':     {'color': '#8e44ad', 'linestyle': '-.', 'label': 'Nasdaq 100 (QQQ)'},
    'BTC-USD': {'color': '#e67e22', 'linestyle': ':',  'label': 'Bitcoin (BTC)'},
}


def generate_benchmark_chart(
    nav_history: List[Dict],
    benchmark_data: Dict[str, List[Dict]],
    width: float = None,
    height: float = None,
    dpi: int = None,
    show_mountain: bool = True,
) -> Path:
    """
    Generate NAV vs Benchmarks comparison chart.

    Background (left Y-axis): NAV per share as filled area ("mountain").
    Foreground (right Y-axis): Normalized percentage change lines for
    the fund and each benchmark, all starting from 0% at the chart start.

    Args:
        nav_history: List of dicts with keys:
            'date' (str YYYY-MM-DD), 'nav_per_share' (float)
        benchmark_data: Dict mapping ticker -> list of dicts with keys:
            'date' (str), 'close_price' (float).
            Expected tickers: 'SPY', 'QQQ', 'BTC-USD'.
        width: Chart width in inches (default: CHART_WIDTH).
        height: Chart height in inches (default: CHART_HEIGHT).
        dpi: Override DPI for saved image (default: CHART_DPI).
        show_mountain: If True, draw NAV mountain fill on left axis.

    Returns:
        Path to temporary PNG file.
    """
    _setup_chart_style()

    chart_w = width or CHART_WIDTH
    chart_h = height or CHART_HEIGHT

    if not nav_history:
        return _generate_empty_chart(
            "Fund vs. Benchmarks", "No NAV data available"
        )

    # Parse NAV dates and values
    nav_dates = [_parse_date(r['date']) for r in nav_history]
    nav_values = [r['nav_per_share'] for r in nav_history]

    if len(nav_dates) < 2:
        return _generate_empty_chart(
            "Fund vs. Benchmarks", "Insufficient NAV data (need 2+ days)"
        )

    # Build date -> NAV lookup for alignment
    nav_by_date = {}
    for d, v in zip(nav_dates, nav_values):
        nav_by_date[d.strftime('%Y-%m-%d')] = v

    # Normalize fund to percentage change from start
    base_nav = nav_values[0]
    fund_pct = [(v / base_nav - 1) * 100 for v in nav_values]

    # Build normalized benchmark series aligned to NAV dates
    benchmark_series = {}
    for bm_ticker, series in (benchmark_data or {}).items():
        if not series:
            continue

        # Build date -> price lookup
        price_by_date = {
            s['date']: s['close_price'] for s in series
        }

        # Align to NAV dates: for each NAV date, find matching or
        # most recent prior benchmark price
        aligned_pct = []
        last_price = None
        base_price = None

        for nav_date in nav_dates:
            date_str = nav_date.strftime('%Y-%m-%d')

            # Exact match
            if date_str in price_by_date:
                last_price = price_by_date[date_str]
            else:
                # Find nearest prior date (within 5 days for weekends/holidays)
                for offset in range(1, 6):
                    check = (nav_date - timedelta(days=offset)).strftime('%Y-%m-%d')
                    if check in price_by_date:
                        last_price = price_by_date[check]
                        break

            if last_price is not None:
                if base_price is None:
                    base_price = last_price
                aligned_pct.append((last_price / base_price - 1) * 100)
            else:
                aligned_pct.append(None)

        benchmark_series[bm_ticker] = aligned_pct

    # Create figure
    fig, ax1 = plt.subplots(figsize=(chart_w, chart_h))

    # LEFT Y-AXIS: NAV mountain (absolute values)
    if show_mountain:
        ax1.plot(
            nav_dates, nav_values,
            color=COLORS['secondary'],
            linewidth=0.8,
            alpha=0.3,
            zorder=1,
        )
        ax1.set_ylabel('NAV per Share ($)', color=COLORS['secondary'], alpha=0.6)
        ax1.tick_params(axis='y', labelcolor=COLORS['secondary'], colors=COLORS['secondary'])
        ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter('$%.4f'))
        # Fade the left axis to keep it subtle behind the percentage lines
        for label in ax1.get_yticklabels():
            label.set_alpha(0.5)
    else:
        ax1.set_yticks([])
        ax1.set_ylabel('')

    ax1.grid(True, alpha=0.3, zorder=0)
    _format_date_axis(ax1, nav_dates)

    # Gradient mountain fill (must come after axis setup so limits are correct)
    if show_mountain:
        _gradient_fill(ax1, nav_dates, nav_values, COLORS['secondary'],
                       alpha_top=0.35, alpha_bottom=0.0, zorder=1)

    # RIGHT Y-AXIS: Normalized percentage change lines
    ax2 = ax1.twinx()

    # Fund line (bold, solid)
    ax2.plot(
        nav_dates, fund_pct,
        color=COLORS['primary'],
        linewidth=2.5,
        label=f'Tovito ({fund_pct[-1]:+.1f}%)',
        zorder=5,
    )

    # Benchmark lines
    for t_ticker, pct_values in benchmark_series.items():
        style = BENCHMARK_STYLES.get(t_ticker, {
            'color': '#95a5a6', 'linestyle': '--', 'label': t_ticker
        })

        # Filter out None values for plotting
        plot_dates = []
        plot_vals = []
        for d, v in zip(nav_dates, pct_values):
            if v is not None:
                plot_dates.append(d)
                plot_vals.append(v)

        if not plot_vals:
            continue

        last_val = plot_vals[-1]
        ax2.plot(
            plot_dates, plot_vals,
            color=style['color'],
            linestyle=style['linestyle'],
            linewidth=1.5,
            label=f"{style['label']} ({last_val:+.1f}%)",
            zorder=4,
        )

        # End-of-line annotation
        ax2.annotate(
            f'{last_val:+.1f}%',
            xy=(plot_dates[-1], last_val),
            xytext=(8, 0),
            textcoords='offset points',
            fontsize=7,
            fontweight='bold',
            color=style['color'],
            va='center',
            zorder=6,
        )

    # Fund end-of-line annotation
    ax2.annotate(
        f'{fund_pct[-1]:+.1f}%',
        xy=(nav_dates[-1], fund_pct[-1]),
        xytext=(8, 0),
        textcoords='offset points',
        fontsize=7,
        fontweight='bold',
        color=COLORS['primary'],
        va='center',
        zorder=6,
    )

    # Current NAV callout — prominent label so no one has to eyeball it
    current_nav = nav_values[-1]
    ax1.annotate(
        f'NAV: ${current_nav:,.4f}',
        xy=(nav_dates[-1], current_nav),
        xytext=(-14, 18),
        textcoords='offset points',
        fontsize=9,
        fontweight='bold',
        color=COLORS['primary'],
        ha='right',
        va='bottom',
        zorder=10,
        bbox=dict(
            boxstyle='round,pad=0.4',
            facecolor='white',
            edgecolor=COLORS['primary'],
            alpha=0.95,
            linewidth=1.5,
        ),
        arrowprops=dict(
            arrowstyle='->',
            color=COLORS['primary'],
            linewidth=1.5,
            connectionstyle='arc3,rad=-0.2',
        ),
    )

    ax2.set_ylabel('Performance (%)', color=COLORS['text'])
    ax2.tick_params(axis='y', labelcolor=COLORS['text'])
    ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f%%'))

    # Zero line
    ax2.axhline(y=0, color=COLORS['grid'], linestyle='-', linewidth=0.8, alpha=0.5, zorder=2)

    # Legend
    ax2.legend(
        loc='upper left',
        framealpha=0.9,
        fontsize=8,
        edgecolor=COLORS['grid'],
    )

    # Title with date range
    start_str = nav_dates[0].strftime('%b %d, %Y')
    end_str = nav_dates[-1].strftime('%b %d, %Y')
    ax1.set_title(
        f'Fund Performance vs. Benchmarks  ({start_str} \u2013 {end_str})',
        fontsize=12,
        fontweight='bold',
        color=COLORS['text'],
    )

    fig.tight_layout()
    return _save_chart(fig, 'benchmark', dpi=dpi)
