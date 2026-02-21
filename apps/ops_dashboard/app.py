"""
Tovito Trader - Operations Health Dashboard
============================================
Standalone Streamlit page showing system health at a glance.

Launch:
    cd C:\\tovito-trader
    python -m streamlit run apps/ops_dashboard/app.py --server.port 8502

Data layer lives in src/monitoring/health_checks.py so the same
queries can later be reused in the CustomTkinter fund-manager dashboard.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Ensure project root is on the path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from src.monitoring.health_checks import HealthCheckService, get_remediation

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ops Dashboard - Tovito Trader",
    page_icon="🔧",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS for compact monitor cards
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Compact monitor cards */
.monitor-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 6px;
    border-left: 4px solid #ccc;
}
.monitor-card.green { border-left-color: #28a745; }
.monitor-card.yellow { border-left-color: #ffc107; }
.monitor-card.red { border-left-color: #dc3545; }

.monitor-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #555;
    margin-bottom: 2px;
    line-height: 1.2;
}
.monitor-value {
    font-size: 0.92rem;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.3;
}
.monitor-delta {
    font-size: 0.72rem;
    color: #777;
}
/* Tighten expander padding inside cards */
.monitor-card + div[data-testid="stExpander"] {
    margin-top: -4px;
}
/* Reduce metric size globally */
div[data-testid="stMetric"] label {
    font-size: 0.82rem !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 1.1rem !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
    font-size: 0.72rem !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper: render a compact monitor card with inline guidance
# ---------------------------------------------------------------------------
def _status_color(status: str) -> str:
    """Map status to CSS color class."""
    if status in ('ok',):
        return 'green'
    if status in ('stale', 'warning', 'no_data'):
        return 'yellow'
    return 'red'


def monitor_card(col, label: str, value: str, delta: str = None,
                 status: str = 'ok', source: str = None,
                 context: dict = None):
    """Render a compact monitor card with integrated guidance.

    Displays the card HTML, then if non-green, adds a small expander
    with the remediation summary + command right inside the column.
    """
    color = _status_color(status)
    icon_map = {'green': '🟢', 'yellow': '🟡', 'red': '🔴'}
    icon = icon_map.get(color, '⚪')

    delta_html = ''
    if delta:
        delta_html = f'<div class="monitor-delta">{delta}</div>'

    col.markdown(f"""
    <div class="monitor-card {color}">
        <div class="monitor-label">{label}</div>
        <div class="monitor-value">{icon} {value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

    # Inline guidance for non-green items
    if status != 'ok' and source:
        guidance = get_remediation(source, status, context)
        if guidance:
            with col.expander(f"Details & fix"):
                st.caption(guidance['summary'])
                st.write(guidance['action'])
                if guidance.get('command'):
                    st.code(guidance['command'], language='powershell')
                if guidance.get('wait_for_next_cycle'):
                    st.info("Resolves automatically on next cycle.")
                if guidance.get('log_file'):
                    st.caption(f"Log: `{guidance['log_file']}`")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Settings")

    auto_refresh = st.checkbox("Auto-refresh (60 s)", value=False)
    days_range = st.slider("History range (days)", 7, 90, 30)

    st.divider()
    st.caption(f"Last loaded: {datetime.now().strftime('%H:%M:%S')}")

    # Quick DB health
    st.subheader("Database")
    svc = HealthCheckService()
    db_health = svc.get_database_health()
    st.metric("File size", f"{db_health['file_size_mb']} MB")
    integrity_icon = "OK" if db_health['integrity_ok'] else "FAIL"
    st.metric("Integrity", integrity_icon)
    if db_health['table_counts']:
        with st.expander("Table row counts"):
            for tbl, cnt in sorted(db_health['table_counts'].items()):
                st.text(f"{tbl}: {cnt:,}")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Operations Health Dashboard")

health = svc.get_overall_health_score()
score = health['score']
grade = health['grade']

if score >= 85:
    score_emoji = "🟢"
elif score >= 50:
    score_emoji = "🟡"
else:
    score_emoji = "🔴"

col_score, col_grade, col_ts = st.columns([2, 1, 2])
with col_score:
    st.metric("Health Score", f"{score_emoji} {score} / 100")
with col_grade:
    st.metric("Grade", grade)
with col_ts:
    st.metric("As of", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

# ---------------------------------------------------------------------------
# Section 1: Health Score Breakdown
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Health Score Breakdown")

_COMP_SOURCE_MAP = {
    'NAV Freshness': 'daily_nav',
    'Reconciliation': 'reconciliation',
    'System Logs': 'system_logs',
    'Email Delivery': 'email_delivery',
    'Database Integrity': 'database_integrity',
}

cols = st.columns(len(health['components']))
now = datetime.now()
for col, comp in zip(cols, health['components']):
    source_key = _COMP_SOURCE_MAP.get(comp['name'],
                                      comp['name'].lower().replace(' ', '_'))
    monitor_card(
        col,
        label=comp['name'],
        value=f"{comp['score']}/{comp['max']}",
        status=comp['status'],
        source=source_key,
        context={'now': now},
    )

# ---------------------------------------------------------------------------
# Section 2: Data Freshness
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Data Freshness")

freshness = svc.get_data_freshness()
if freshness:
    fresh_cols = st.columns(min(len(freshness), 6))
    for i, (source, info) in enumerate(freshness.items()):
        col = fresh_cols[i % len(fresh_cols)]
        status = info.get('status', 'missing')
        age = info.get('age_hours')
        age_str = f"{age:.0f}h ago" if age is not None else "N/A"
        last_date = info.get('last_date', 'Never') or 'Never'

        monitor_card(
            col,
            label=source.replace('_', ' ').title(),
            value=last_date,
            delta=age_str,
            status=status,
            source=source,
            context={
                'age_hours': age,
                'last_date': info.get('last_date'),
                'now': now,
            },
        )
else:
    st.info("No freshness data available.")

# ---------------------------------------------------------------------------
# Section 3: Automation Status
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Automation Status")

_AUTO_SOURCE_MAP = {
    'Daily NAV Update': 'daily_nav',
    'Watchdog Monitor': 'watchdog',
    'Weekly Validation': 'weekly_validation',
    'Monthly Reports': 'monthly_reports',
}

auto_tasks = svc.get_automation_status()
auto_cols = st.columns(len(auto_tasks))
for col, task in zip(auto_cols, auto_tasks):
    source_key = _AUTO_SOURCE_MAP.get(task['name'],
                                      task['name'].lower().replace(' ', '_'))
    monitor_card(
        col,
        label=task['name'],
        value=task['last_run'] or 'Never',
        delta=task.get('details', ''),
        status=task['status'],
        source=source_key,
        context={'now': now},
    )

# ---------------------------------------------------------------------------
# Section 4: Reconciliation
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Reconciliation")

recon_status = svc.get_current_reconciliation_status()
if recon_status:
    status_val = recon_status.get('status', 'unknown')
    if status_val == 'matched':
        st.success(
            f"Latest reconciliation ({recon_status['date']}): **MATCHED**")
    else:
        st.error(
            f"Latest reconciliation ({recon_status['date']}): "
            f"**{status_val.upper()}**")
        if recon_status.get('notes'):
            st.warning(f"Details: {recon_status['notes']}")
        guidance = get_remediation('reconciliation', 'mismatch')
        if guidance:
            with st.expander("Details & fix"):
                st.write(guidance['action'])
                if guidance.get('command'):
                    st.code(guidance['command'], language='powershell')
else:
    st.info("No reconciliation records found.")
    guidance = get_remediation('reconciliation', 'missing')
    if guidance:
        with st.expander("Details & fix"):
            st.write(guidance['action'])
            if guidance.get('wait_for_next_cycle'):
                st.info("Resolves automatically on next cycle.")

# History chart
recon_history = svc.get_reconciliation_history(days=days_range)
if recon_history:
    import pandas as pd
    df = pd.DataFrame(recon_history)
    df['matched'] = df['status'].apply(
        lambda s: 1 if s == 'matched' else 0)
    df['mismatch'] = df['status'].apply(
        lambda s: 1 if s != 'matched' else 0)
    df = df.sort_values('date')
    st.bar_chart(df.set_index('date')[['matched', 'mismatch']],
                 color=['#28a745', '#dc3545'])

    mismatches = [r for r in recon_history if r.get('status') != 'matched']
    if mismatches:
        with st.expander(f"Mismatches ({len(mismatches)})"):
            st.dataframe(pd.DataFrame(mismatches))

# ---------------------------------------------------------------------------
# Section 5: NAV Continuity
# ---------------------------------------------------------------------------
st.divider()
st.subheader("NAV Continuity")

gap_check = svc.get_nav_gap_check()
if gap_check['has_gaps']:
    st.error(
        f"Found {len(gap_check['gaps'])} gap(s) in NAV history! "
        f"Longest gap: {gap_check['longest_gap']} business day(s)")
    import pandas as pd
    st.dataframe(pd.DataFrame(gap_check['gaps']))
else:
    latest = gap_check.get('latest_nav_date', 'N/A')
    st.success(f"No gaps in NAV history. Latest NAV date: {latest}")

# ---------------------------------------------------------------------------
# Section 6: System Logs
# ---------------------------------------------------------------------------
st.divider()
st.subheader("System Logs")

log_summary = svc.get_log_summary(days=days_range)
if log_summary['total'] > 0:
    summary_cols = st.columns(4)
    type_icons = {'ERROR': '🔴', 'WARNING': '🟡',
                  'SUCCESS': '🟢', 'INFO': '🔵'}
    for i, (lt, cnt) in enumerate(sorted(
            log_summary['by_type'].items(),
            key=lambda x: x[1], reverse=True)):
        col = summary_cols[i % 4]
        icon = type_icons.get(lt, '⚪')
        col.metric(f"{icon} {lt}", cnt)

    with st.expander("Recent log entries"):
        filter_cols = st.columns(2)
        type_filter = filter_cols[0].selectbox(
            "Filter by type",
            ['All'] + list(log_summary['by_type'].keys()),
        )
        cat_filter = filter_cols[1].selectbox(
            "Filter by category",
            ['All'] + list(log_summary['by_category'].keys()),
        )
        logs = svc.get_system_logs(
            limit=50,
            log_type=type_filter if type_filter != 'All' else None,
            category=cat_filter if cat_filter != 'All' else None,
        )
        if logs:
            import pandas as pd
            st.dataframe(pd.DataFrame(logs), use_container_width=True)
        else:
            st.info("No log entries match the current filters.")
else:
    st.info("No system log entries found for the selected period.")

# ---------------------------------------------------------------------------
# Section 7: Email Delivery
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Email Delivery")

email_stats = svc.get_email_delivery_stats(days=days_range)
e_cols = st.columns(3)
total_emails = email_stats['total_sent'] + email_stats['total_failed']
success_rate = (
    f"{email_stats['total_sent'] / total_emails * 100:.0f}%"
    if total_emails > 0 else "N/A"
)
e_cols[0].metric("Sent", email_stats['total_sent'])
e_cols[1].metric("Failed", email_stats['total_failed'])
e_cols[2].metric("Success Rate", success_rate)

if email_stats['by_type']:
    with st.expander("By email type"):
        for etype, cnt in sorted(email_stats['by_type'].items(),
                                 key=lambda x: x[1], reverse=True):
            st.text(f"{etype}: {cnt}")

if email_stats['recent']:
    with st.expander("Recent emails (recipients masked)"):
        import pandas as pd
        st.dataframe(pd.DataFrame(email_stats['recent']),
                     use_container_width=True)

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
if auto_refresh:
    time.sleep(60)
    st.rerun()
