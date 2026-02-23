"""
Tovito Trader Platform Mind Map Generator
==========================================

Generates three visual mind maps of the Tovito Trader platform:

    1. **Platform Architecture** — Comprehensive overview of all applications,
       database tables, automation pipelines, external integrations, operational
       workflows, and core libraries with data flow arrows.

    2. **Database Impact** — Which processes WRITE to and READ from which
       database tables. Three-column layout: writers | tables | readers.

    3. **Business Processes** — End-to-end manual workflows showing how
       human-initiated processes (contributions, withdrawals, onboarding,
       tax settlement, reporting, account closure) flow through the system.

Each view is generated in three formats:
    - Interactive HTML (zoom, pan, collapsible nodes, search, tooltips)
    - Mermaid Markdown (renderable in GitHub, VS Code, docs)
    - High-res PNG + SVG (for printing and embedding)

Usage:
    python scripts/generate_mindmap.py                  # All views, all formats
    python scripts/generate_mindmap.py --format html    # HTML only
    python scripts/generate_mindmap.py --format mermaid # Mermaid only
    python scripts/generate_mindmap.py --format png     # PNG + SVG only
    python scripts/generate_mindmap.py --open           # Open HTML in browser

No new dependencies — uses matplotlib, Pillow, and Tailwind CDN (all existing).
"""

import argparse
import json
import math
import os
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Use non-interactive backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'mindmap'

# ============================================================
# COLOR PALETTE (matches src/reporting/charts.py)
# ============================================================

CATEGORY_COLORS = {
    'root':        '#c0392b',   # Red accent — central node
    'application': '#1e3a5f',   # Dark navy — applications
    'database':    '#4a90d9',   # Medium blue — database
    'automation':  '#2d8a4e',   # Green — automation
    'external':    '#e67e22',   # Orange — external integrations
    'workflow':    '#8e44ad',   # Purple — operational workflows
    'library':     '#95a5a6',   # Gray — core libraries
}

CATEGORY_LABELS = {
    'root':        'Platform Core',
    'application': 'Applications',
    'database':    'Database',
    'automation':  'Automation',
    'external':    'External Services',
    'workflow':    'Workflows',
    'library':     'Core Libraries',
}


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class MindMapNode:
    """A single node in the mind map."""
    id: str
    label: str
    category: str
    parent_id: Optional[str] = None
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.category not in CATEGORY_COLORS:
            raise ValueError(f"Invalid category '{self.category}' for node '{self.id}'")


@dataclass
class MindMapEdge:
    """A connection between two nodes (hierarchy or data flow)."""
    source_id: str
    target_id: str
    label: str = ''
    edge_type: str = 'hierarchy'  # 'hierarchy' or 'dataflow'


class MindMapData:
    """
    Single source of truth for all mind map content.

    Defines ~100 nodes organized in a 3-level hierarchy and ~25 data flow
    edges showing cross-branch connections.
    """

    def __init__(self):
        self.nodes: dict[str, MindMapNode] = {}
        self.edges: list[MindMapEdge] = []

    def _add(self, id, label, category, parent_id=None, **details):
        """Helper to add a node."""
        self.nodes[id] = MindMapNode(id, label, category, parent_id, details)

    def _flow(self, source, target, label=''):
        """Helper to add a data flow edge."""
        self.edges.append(MindMapEdge(source, target, label, 'dataflow'))

    def get_children(self, parent_id):
        """Get child nodes of a given parent."""
        return [n for n in self.nodes.values() if n.parent_id == parent_id]

    def get_depth(self, node_id):
        """Get depth of a node (root = 0)."""
        depth = 0
        n = self.nodes[node_id]
        while n.parent_id is not None:
            depth += 1
            n = self.nodes[n.parent_id]
        return depth

    def get_subtree_size(self, node_id):
        """Count leaf nodes in subtree."""
        children = self.get_children(node_id)
        if not children:
            return 1
        return sum(self.get_subtree_size(c.id) for c in children)

    def build(self):
        """Populate all nodes and edges."""
        self._build_root()
        self._build_applications()
        self._build_database()
        self._build_automation()
        self._build_external()
        self._build_workflows()
        self._build_libraries()
        self._build_data_flows()

    def _build_root(self):
        self._add('root', 'Tovito Trader\nPlatform', 'root')
        # Branch nodes
        self._add('apps', 'Applications', 'application', 'root')
        self._add('db', 'Database\n(tovito.db)', 'database', 'root')
        self._add('auto', 'Automation', 'automation', 'root')
        self._add('ext', 'External\nIntegrations', 'external', 'root')
        self._add('wf', 'Operational\nWorkflows', 'workflow', 'root')
        self._add('lib', 'Core Libraries\n(src/)', 'library', 'root')

    def _build_applications(self):
        self._add('app_fm', 'Fund Manager\nDashboard', 'application', 'apps',
                   tech='CustomTkinter', port='Desktop')
        self._add('app_fm_feat', 'NAV Chart, Allocation Pie,\nInvestor Table, SQL Explorer', 'application', 'app_fm')

        self._add('app_api', 'Investor Portal\nAPI', 'application', 'apps',
                   tech='FastAPI', port='8000')
        self._add('app_api_routes', '/auth  /investor  /nav\n/fund-flow  /profile  /referral', 'application', 'app_api')

        self._add('app_fe', 'Investor Portal\nFrontend', 'application', 'apps',
                   tech='React + Vite', port='5173')
        self._add('app_fe_pages', 'Dashboard, Fund Flows,\nProfile, Tutorials/Help', 'application', 'app_fe')

        self._add('app_mm', 'Market Monitor', 'application', 'apps',
                   tech='Streamlit', port='8501')
        self._add('app_mm_feat', 'Live Data, Alert Rules,\nDiscord Notifications', 'application', 'app_mm')

        self._add('app_ops', 'Ops Dashboard', 'application', 'apps',
                   tech='Streamlit', port='8502')
        self._add('app_ops_feat', 'Health Score, Freshness,\nReconciliation, Remediation', 'application', 'app_ops')

    def _build_database(self):
        self._add('db_financial', 'Core Financial', 'database', 'db')
        self._add('db_investors', 'investors', 'database', 'db_financial')
        self._add('db_daily_nav', 'daily_nav', 'database', 'db_financial')
        self._add('db_transactions', 'transactions', 'database', 'db_financial')
        self._add('db_trades', 'trades', 'database', 'db_financial')
        self._add('db_tax_events', 'tax_events', 'database', 'db_financial')

        self._add('db_positions', 'Position Tracking', 'database', 'db')
        self._add('db_holdings', 'holdings_snapshots', 'database', 'db_positions')
        self._add('db_pos_snap', 'position_snapshots', 'database', 'db_positions')

        self._add('db_etl', 'ETL & Staging', 'database', 'db')
        self._add('db_raw', 'brokerage_\ntransactions_raw', 'database', 'db_etl')

        self._add('db_flow', 'Fund Flow', 'database', 'db')
        self._add('db_ffr', 'fund_flow_requests', 'database', 'db_flow')

        self._add('db_profiles', 'Profiles & Referrals', 'database', 'db')
        self._add('db_inv_prof', 'investor_profiles', 'database', 'db_profiles')
        self._add('db_referrals', 'referrals', 'database', 'db_profiles')

        self._add('db_monitor', 'Monitoring & Audit', 'database', 'db')
        self._add('db_sys_logs', 'system_logs', 'database', 'db_monitor')
        self._add('db_email_logs', 'email_logs', 'database', 'db_monitor')
        self._add('db_recon', 'daily_reconciliation', 'database', 'db_monitor')
        self._add('db_audit', 'audit_log', 'database', 'db_monitor')

    def _build_automation(self):
        self._add('auto_nav', 'Daily NAV Pipeline\n(7 steps)', 'automation', 'auto')
        self._add('auto_nav_s1', '1. Fetch Balance', 'automation', 'auto_nav')
        self._add('auto_nav_s2', '2. Calculate NAV', 'automation', 'auto_nav')
        self._add('auto_nav_s3', '3. Heartbeat +\nhealthchecks.io', 'automation', 'auto_nav')
        self._add('auto_nav_s4', '4. Snapshot Holdings', 'automation', 'auto_nav')
        self._add('auto_nav_s5', '5. Reconciliation', 'automation', 'auto_nav')
        self._add('auto_nav_s6', '6. ETL Trade Sync', 'automation', 'auto_nav')
        self._add('auto_nav_s7', '7. Discord NAV\nMessage', 'automation', 'auto_nav')

        self._add('auto_wd', 'Watchdog Monitor', 'automation', 'auto')
        self._add('auto_wd_checks', 'NAV Freshness,\nHeartbeat, Logs', 'automation', 'auto_wd')

        self._add('auto_tn', 'Trade Notifier', 'automation', 'auto')
        self._add('auto_tn_poll', 'Polls Every 5 Min\n(Market Hours)', 'automation', 'auto_tn')

        self._add('auto_wv', 'Weekly Validation', 'automation', 'auto')

    def _build_external(self):
        self._add('ext_tt', 'TastyTrade API\n(Primary)', 'external', 'ext')
        self._add('ext_tt_feat', 'Balance, Positions,\nTransactions', 'external', 'ext_tt')

        self._add('ext_tr', 'Tradier API\n(Legacy)', 'external', 'ext')

        self._add('ext_discord', 'Discord', 'external', 'ext')
        self._add('ext_disc_bot', 'Bot API\n(Pinned NAV)', 'external', 'ext_discord')
        self._add('ext_disc_wh', 'Webhooks\n#trades #alerts', 'external', 'ext_discord')

        self._add('ext_email', 'Gmail SMTP', 'external', 'ext')
        self._add('ext_email_feat', 'Reports, Alerts,\nInvestor Comms', 'external', 'ext_email')

        self._add('ext_hc', 'healthchecks.io', 'external', 'ext')
        self._add('ext_hc_feat', '2 Monitors:\nNAV + Watchdog', 'external', 'ext_hc')

    def _build_workflows(self):
        self._add('wf_ff', 'Fund Flow\nLifecycle', 'workflow', 'wf')
        self._add('wf_ff_steps', 'Submit > Approve >\nMatch ACH > Process', 'workflow', 'wf_ff')

        self._add('wf_etl', 'ETL Pipeline', 'workflow', 'wf')
        self._add('wf_etl_steps', 'Extract Raw >\nTransform > Load', 'workflow', 'wf_etl')

        self._add('wf_report', 'Monthly\nReporting', 'workflow', 'wf')
        self._add('wf_rpt_steps', 'PDF + Charts >\nEmail > Discord', 'workflow', 'wf_report')

        self._add('wf_tax', 'Tax\nManagement', 'workflow', 'wf')
        self._add('wf_tax_steps', 'Track Gains >\nQuarterly 37%', 'workflow', 'wf_tax')

        self._add('wf_onboard', 'Investor\nOnboarding', 'workflow', 'wf')
        self._add('wf_onb_steps', 'Profiles, KYC,\nReferral Codes', 'workflow', 'wf_onboard')

        self._add('wf_tutorial', 'Tutorial\nSystem', 'workflow', 'wf')
        self._add('wf_tut_steps', 'Record > Annotate >\nGenerate > Deploy', 'workflow', 'wf_tutorial')

    def _build_libraries(self):
        self._add('lib_api', 'src/api/\nBrokerage Protocol', 'library', 'lib')
        self._add('lib_auto', 'src/automation/\nNAV, EmailService', 'library', 'lib')
        self._add('lib_db', 'src/database/\nORM, Schema', 'library', 'lib')
        self._add('lib_etl', 'src/etl/\nExtract, Transform, Load', 'library', 'lib')
        self._add('lib_mon', 'src/monitoring/\nHealthCheckService', 'library', 'lib')
        self._add('lib_rpt', 'src/reporting/\ncharts.py', 'library', 'lib')
        self._add('lib_util', 'src/utils/\nDiscord, Encryption, Logging', 'library', 'lib')

    def _build_data_flows(self):
        """Cross-branch data flow connections."""
        # Brokerage → Pipeline
        self._flow('ext_tt', 'auto_nav_s1', 'balance, positions')
        self._flow('ext_tt', 'auto_nav_s6', 'raw transactions')
        self._flow('ext_tt', 'auto_tn', 'new trades')

        # Pipeline → Database
        self._flow('auto_nav_s2', 'db_daily_nav', 'NAV record')
        self._flow('auto_nav_s4', 'db_holdings', 'snapshot')
        self._flow('auto_nav_s5', 'db_recon', 'verification')
        self._flow('auto_nav_s6', 'db_raw', 'staging')
        self._flow('auto_nav_s6', 'db_trades', 'canonical trades')

        # Pipeline → External
        self._flow('auto_nav_s3', 'ext_hc', 'success/fail ping')
        self._flow('auto_nav_s7', 'ext_disc_bot', 'NAV embed + chart')

        # Watchdog → External
        self._flow('auto_wd', 'ext_email', 'failure alerts')
        self._flow('auto_wd', 'ext_hc', 'watchdog ping')

        # Trade Notifier → Discord
        self._flow('auto_tn', 'ext_disc_wh', 'trade embeds')

        # Market Monitor → Discord
        self._flow('app_mm', 'ext_disc_wh', 'price alerts')

        # Fund Flow → Database
        self._flow('wf_ff', 'db_ffr', 'lifecycle records')
        self._flow('wf_ff', 'db_transactions', 'share accounting')
        self._flow('wf_ff', 'db_investors', 'balance update')

        # Reporting → External
        self._flow('wf_report', 'ext_email', 'monthly reports')
        self._flow('wf_report', 'ext_discord', 'summary post')

        # Apps → Database
        self._flow('app_fm', 'db', 'direct SQLite (read)')
        self._flow('app_api', 'db', 'SQLAlchemy ORM')

        # Frontend → API
        self._flow('app_fe', 'app_api', 'HTTP / JWT')

        # Ops → Health Checks
        self._flow('app_ops', 'lib_mon', 'health queries')

        # Email → Logs
        self._flow('ext_email', 'db_email_logs', 'delivery audit')

        # Tutorial → Frontend
        self._flow('wf_tutorial', 'app_fe', 'HTML guides + videos')


# ============================================================
# DATABASE IMPACT VIEW
# ============================================================

class DatabaseImpactData(MindMapData):
    """
    Focused view: which processes READ from and WRITE to which database tables.

    Layout: Database tables in center column, processes on left (writes) and
    right (reads), with arrows showing direction.
    """

    # Custom colors for this view
    WRITE_COLOR = '#c0392b'    # Red — writes/mutations
    READ_COLOR = '#2d8a4e'     # Green — reads
    TABLE_COLOR = '#4a90d9'    # Blue — tables
    PROCESS_COLOR = '#1e3a5f'  # Navy — processes

    def build(self):
        """Build the database impact model."""
        self._build_tables()
        self._build_writers()
        self._build_readers()
        self._build_flows()

    def _build_tables(self):
        """Central column: all database tables."""
        self._add('db_center', 'tovito.db\n(SQLite)', 'database')

        # Core Financial
        self._add('tbl_investors', 'investors', 'database', 'db_center')
        self._add('tbl_daily_nav', 'daily_nav', 'database', 'db_center')
        self._add('tbl_transactions', 'transactions', 'database', 'db_center')
        self._add('tbl_trades', 'trades', 'database', 'db_center')
        self._add('tbl_tax_events', 'tax_events', 'database', 'db_center')

        # Position & ETL
        self._add('tbl_holdings', 'holdings_snapshots', 'database', 'db_center')
        self._add('tbl_positions', 'position_snapshots', 'database', 'db_center')
        self._add('tbl_raw', 'brokerage_\ntransactions_raw', 'database', 'db_center')

        # Fund Flow & Profiles
        self._add('tbl_ffr', 'fund_flow_requests', 'database', 'db_center')
        self._add('tbl_profiles', 'investor_profiles', 'database', 'db_center')
        self._add('tbl_referrals', 'referrals', 'database', 'db_center')

        # Monitoring
        self._add('tbl_sys_logs', 'system_logs', 'database', 'db_center')
        self._add('tbl_email_logs', 'email_logs', 'database', 'db_center')
        self._add('tbl_recon', 'daily_reconciliation', 'database', 'db_center')
        self._add('tbl_audit', 'audit_log', 'database', 'db_center')

    def _build_writers(self):
        """Left side: processes that WRITE to the database."""
        self._add('writers', 'WRITE Processes', 'workflow')

        self._add('w_nav_pipeline', 'Daily NAV Pipeline\n(daily_nav_enhanced.py)', 'automation', 'writers')
        self._add('w_etl', 'ETL Pipeline\n(run_etl.py)', 'automation', 'writers')
        self._add('w_fund_flow', 'Fund Flow Scripts\n(submit/match/process)', 'workflow', 'writers')
        self._add('w_tax', 'Tax Settlement\n(quarterly_tax_payment.py)', 'workflow', 'writers')
        self._add('w_reporting', 'Report Generation\n(generate_monthly_report.py)', 'workflow', 'writers')
        self._add('w_email_svc', 'EmailService\n(src/automation)', 'library', 'writers')
        self._add('w_profile', 'Profile Manager\n(manage_profile.py)', 'workflow', 'writers')
        self._add('w_referral', 'Referral Generator\n(generate_referral_code.py)', 'workflow', 'writers')
        self._add('w_portal_api', 'Investor Portal API\n(FastAPI)', 'application', 'writers')
        self._add('w_close_acct', 'Close Account\n(close_investor_account.py)', 'workflow', 'writers')

    def _build_readers(self):
        """Right side: processes that READ from the database."""
        self._add('readers', 'READ Processes', 'workflow')

        self._add('r_fund_mgr', 'Fund Manager\nDashboard', 'application', 'readers')
        self._add('r_portal_api', 'Investor Portal API\n(all endpoints)', 'application', 'readers')
        self._add('r_market_mon', 'Market Monitor', 'application', 'readers')
        self._add('r_ops_dash', 'Ops Dashboard\n(HealthCheckService)', 'application', 'readers')
        self._add('r_watchdog', 'Watchdog Monitor', 'automation', 'readers')
        self._add('r_nav_chart', 'Discord NAV Bot\n(chart generation)', 'automation', 'readers')
        self._add('r_monthly_rpt', 'Monthly Reports\n(PDF generation)', 'workflow', 'readers')
        self._add('r_validation', 'Validation Scripts', 'automation', 'readers')

    def _build_flows(self):
        """Arrows: who writes/reads which tables."""
        # === WRITES ===
        # NAV Pipeline writes
        self._flow('w_nav_pipeline', 'tbl_daily_nav', 'Step 2: NAV record')
        self._flow('w_nav_pipeline', 'tbl_holdings', 'Step 4: snapshot')
        self._flow('w_nav_pipeline', 'tbl_positions', 'Step 4: positions')
        self._flow('w_nav_pipeline', 'tbl_recon', 'Step 5: reconciliation')
        self._flow('w_nav_pipeline', 'tbl_sys_logs', 'all steps: logging')

        # ETL writes
        self._flow('w_etl', 'tbl_raw', 'extract: staging')
        self._flow('w_etl', 'tbl_trades', 'load: canonical trades')

        # Fund Flow writes
        self._flow('w_fund_flow', 'tbl_ffr', 'lifecycle records')
        self._flow('w_fund_flow', 'tbl_transactions', 'share accounting')
        self._flow('w_fund_flow', 'tbl_investors', 'balance update')
        self._flow('w_fund_flow', 'tbl_audit', 'change tracking')

        # Tax writes
        self._flow('w_tax', 'tbl_tax_events', 'quarterly settlement')

        # Email logging
        self._flow('w_email_svc', 'tbl_email_logs', 'send/fail audit')

        # Profile & Referral writes
        self._flow('w_profile', 'tbl_profiles', 'KYC data')
        self._flow('w_referral', 'tbl_referrals', 'referral codes')

        # Portal API writes
        self._flow('w_portal_api', 'tbl_ffr', 'fund flow requests')
        self._flow('w_portal_api', 'tbl_profiles', 'profile updates')

        # Close account writes
        self._flow('w_close_acct', 'tbl_ffr', 'withdrawal request')
        self._flow('w_close_acct', 'tbl_transactions', 'final withdrawal')
        self._flow('w_close_acct', 'tbl_investors', 'status=closed')

        # Reporting writes
        self._flow('w_reporting', 'tbl_sys_logs', 'generation log')

        # === READS ===
        self._flow('tbl_investors', 'r_fund_mgr', 'investor data')
        self._flow('tbl_daily_nav', 'r_fund_mgr', 'NAV history')
        self._flow('tbl_trades', 'r_fund_mgr', 'trade data')
        self._flow('tbl_transactions', 'r_fund_mgr', 'transaction history')

        self._flow('tbl_investors', 'r_portal_api', 'position, auth')
        self._flow('tbl_daily_nav', 'r_portal_api', 'NAV chart data')
        self._flow('tbl_transactions', 'r_portal_api', 'history')
        self._flow('tbl_ffr', 'r_portal_api', 'flow status')
        self._flow('tbl_profiles', 'r_portal_api', 'profile data')
        self._flow('tbl_referrals', 'r_portal_api', 'referral info')

        self._flow('tbl_daily_nav', 'r_market_mon', 'latest NAV')
        self._flow('tbl_trades', 'r_market_mon', 'recent trades')

        self._flow('tbl_daily_nav', 'r_ops_dash', 'freshness check')
        self._flow('tbl_recon', 'r_ops_dash', 'reconciliation')
        self._flow('tbl_sys_logs', 'r_ops_dash', 'error counts')
        self._flow('tbl_email_logs', 'r_ops_dash', 'delivery status')

        self._flow('tbl_daily_nav', 'r_watchdog', 'NAV freshness')
        self._flow('tbl_sys_logs', 'r_watchdog', 'error detection')

        self._flow('tbl_daily_nav', 'r_nav_chart', 'chart data')
        self._flow('tbl_investors', 'r_nav_chart', 'investor count')

        self._flow('tbl_investors', 'r_monthly_rpt', 'allocations')
        self._flow('tbl_daily_nav', 'r_monthly_rpt', 'performance')
        self._flow('tbl_transactions', 'r_monthly_rpt', 'activity')
        self._flow('tbl_trades', 'r_monthly_rpt', 'trade summary')

        self._flow('tbl_daily_nav', 'r_validation', 'gap detection')
        self._flow('tbl_recon', 'r_validation', 'mismatch check')
        self._flow('tbl_trades', 'r_validation', 'trade integrity')


# ============================================================
# BUSINESS PROCESS VIEW
# ============================================================

class BusinessProcessData(MindMapData):
    """
    Focused view: manual business processes end-to-end.

    Shows how human-initiated workflows (contributions, withdrawals, onboarding,
    tax payments, reporting) flow through scripts, database, and external systems.
    """

    def build(self):
        """Build the business process model."""
        self._build_processes()

    def _build_processes(self):
        """Build all business process flows."""
        # Root
        self._add('root', 'Business Processes\n(Manual Workflows)', 'root')

        # ---- CONTRIBUTION ----
        self._add('bp_contrib', 'Investor\nContribution', 'workflow', 'root')

        self._add('c1', '1. Investor Sends\nACH Transfer', 'external', 'bp_contrib',
                   actor='Investor', method='Bank ACH to TastyTrade')
        self._add('c2', '2. ACH Lands in\nBrokerage Account', 'external', 'c1',
                   actor='TastyTrade', auto=True)
        self._add('c3', '3. Submit Fund Flow\n(submit_fund_flow.py)', 'workflow', 'c2',
                   actor='Fund Manager', writes='fund_flow_requests')
        self._add('c4', '4. Match to ACH\n(match_fund_flow.py)', 'workflow', 'c3',
                   actor='Fund Manager', writes='fund_flow_requests.matched_trade_id')
        self._add('c5', '5. Process Shares\n(process_fund_flow.py)', 'workflow', 'c4',
                   actor='Fund Manager', writes='transactions, investors')
        self._add('c6', '6. Email Confirmation\n(EmailService)', 'external', 'c5',
                   actor='System', writes='email_logs')
        self._add('c7', '7. NAV Reflects\nNew Shares', 'database', 'c5',
                   actor='System', reads='daily_nav (next day)')

        # ---- WITHDRAWAL ----
        self._add('bp_withdraw', 'Investor\nWithdrawal', 'workflow', 'root')

        self._add('w1', '1. Investor Requests\nWithdrawal', 'external', 'bp_withdraw',
                   actor='Investor', method='Portal or direct request')
        self._add('w2', '2. Submit Fund Flow\n(submit_fund_flow.py)', 'workflow', 'w1',
                   actor='Fund Manager', writes='fund_flow_requests')
        self._add('w3', '3. Calculate Eligible\nAmount (NAV - Tax)', 'workflow', 'w2',
                   actor='System', reads='daily_nav, tax_events')
        self._add('w4', '4. Initiate ACH\nDisbursement', 'external', 'w3',
                   actor='Fund Manager', method='TastyTrade ACH out')
        self._add('w5', '5. Match to ACH\n(match_fund_flow.py)', 'workflow', 'w4',
                   actor='Fund Manager', writes='fund_flow_requests.matched_trade_id')
        self._add('w6', '6. Process Share\nReduction', 'workflow', 'w5',
                   actor='Fund Manager', writes='transactions, investors, tax_events')
        self._add('w7', '7. Email Confirmation\n+ Tax Summary', 'external', 'w6',
                   actor='System', writes='email_logs')

        # ---- DAILY NAV ----
        self._add('bp_nav', 'Daily NAV\nUpdate', 'automation', 'root')

        self._add('n1', '1. Task Scheduler\nTriggers at 4:05 PM', 'automation', 'bp_nav',
                   actor='Windows Task Scheduler')
        self._add('n2', '2. Fetch Balance\nfrom TastyTrade', 'external', 'n1',
                   actor='System', reads='TastyTrade API')
        self._add('n3', '3. Calculate NAV\n= Value / Shares', 'automation', 'n2',
                   writes='daily_nav')
        self._add('n4', '4. Snapshot Holdings\n& Reconcile', 'automation', 'n3',
                   writes='holdings_snapshots, daily_reconciliation')
        self._add('n5', '5. ETL Sync\nRecent Trades', 'automation', 'n4',
                   writes='brokerage_transactions_raw, trades')
        self._add('n6', '6. Update Discord\nPinned NAV Message', 'external', 'n5',
                   actor='Discord Bot')
        self._add('n7', '7. Ping healthchecks.io\n(Success/Fail)', 'external', 'n3',
                   actor='System')

        # ---- MONTHLY REPORTING ----
        self._add('bp_report', 'Monthly\nReporting', 'workflow', 'root')

        self._add('r1', '1. Run Report Script\n(generate_monthly_report.py)', 'workflow', 'bp_report',
                   actor='Fund Manager')
        self._add('r2', '2. Generate PDF\nfor Each Investor', 'workflow', 'r1',
                   reads='daily_nav, transactions, investors')
        self._add('r3', '3. Create Charts\n(charts.py)', 'library', 'r2',
                   reads='daily_nav, trades')
        self._add('r4', '4. Email Reports\nto Investors', 'external', 'r3',
                   writes='email_logs')
        self._add('r5', '5. Post Discord\nMonthly Summary', 'external', 'r4',
                   actor='discord_monthly_summary.py')

        # ---- TAX SETTLEMENT ----
        self._add('bp_tax', 'Quarterly Tax\nSettlement', 'workflow', 'root')

        self._add('t1', '1. Calculate Realized\nGains for Quarter', 'workflow', 'bp_tax',
                   reads='tax_events, trades')
        self._add('t2', '2. Apply 37% Federal\nTax Rate', 'workflow', 't1')
        self._add('t3', '3. Record Tax Payment\n(quarterly_tax_payment.py)', 'workflow', 't2',
                   writes='tax_events')
        self._add('t4', '4. Update Investor\nEligible Balances', 'workflow', 't3',
                   reads='investors, daily_nav')

        # ---- INVESTOR ONBOARDING ----
        self._add('bp_onboard', 'Investor\nOnboarding', 'workflow', 'root')

        self._add('o1', '1. Generate Referral\nCode (optional)', 'workflow', 'bp_onboard',
                   writes='referrals')
        self._add('o2', '2. Create Investor\nRecord', 'workflow', 'o1',
                   writes='investors')
        self._add('o3', '3. Create Portal\nAuth Credentials', 'application', 'o2',
                   writes='investor_auth')
        self._add('o4', '4. Collect KYC Profile\n(manage_profile.py)', 'workflow', 'o3',
                   writes='investor_profiles')
        self._add('o5', '5. Initial Contribution\n(Fund Flow)', 'workflow', 'o4',
                   writes='fund_flow_requests, transactions')
        self._add('o6', '6. Send Welcome Email\n& Portal Access', 'external', 'o5',
                   writes='email_logs')

        # ---- ACCOUNT CLOSURE ----
        self._add('bp_close', 'Account\nClosure', 'workflow', 'root')

        self._add('cl1', '1. Investor Requests\nAccount Closure', 'external', 'bp_close',
                   actor='Investor')
        self._add('cl2', '2. Run Close Account\n(close_investor_account.py)', 'workflow', 'cl1',
                   actor='Fund Manager')
        self._add('cl3', '3. Create Withdrawal\nFund Flow Request', 'workflow', 'cl2',
                   writes='fund_flow_requests')
        self._add('cl4', '4. Process Full\nWithdrawal', 'workflow', 'cl3',
                   writes='transactions, investors, tax_events')
        self._add('cl5', '5. Initiate ACH\nDisbursement', 'external', 'cl4',
                   actor='Fund Manager')
        self._add('cl6', '6. Mark Investor\nStatus = Closed', 'database', 'cl5',
                   writes='investors.status')
        self._add('cl7', '7. Final Confirmation\nEmail', 'external', 'cl6',
                   writes='email_logs')


# ============================================================
# FLOW LAYOUT ENGINE (for focused views)
# ============================================================

class FlowLayout:
    """
    Compute positions for flow-style diagrams (left-to-right or top-to-bottom).

    Used by the Database Impact and Business Process views where a radial
    layout doesn't make sense — these are sequential/columnar.
    """

    def __init__(self, data: MindMapData, mode='columns'):
        self.data = data
        self.mode = mode
        self.positions: dict[str, tuple[float, float]] = {}

    def compute_database_impact(self) -> dict[str, tuple[float, float]]:
        """
        Three-column layout:
        Left: WRITE processes | Center: Database tables | Right: READ processes
        """
        # Center column: tables
        tables = self.data.get_children('db_center')
        center_x = 0
        y_start = -len(tables) * 50 / 2
        self.positions['db_center'] = (center_x, y_start - 80)
        for i, table in enumerate(tables):
            self.positions[table.id] = (center_x, y_start + i * 50)

        # Left column: writers
        writers = self.data.get_children('writers')
        left_x = -400
        y_start_w = -len(writers) * 60 / 2
        self.positions['writers'] = (left_x, y_start_w - 80)
        for i, writer in enumerate(writers):
            self.positions[writer.id] = (left_x, y_start_w + i * 60)

        # Right column: readers
        readers = self.data.get_children('readers')
        right_x = 400
        y_start_r = -len(readers) * 60 / 2
        self.positions['readers'] = (right_x, y_start_r - 80)
        for i, reader in enumerate(readers):
            self.positions[reader.id] = (right_x, y_start_r + i * 60)

        return self.positions

    def compute_business_process(self) -> dict[str, tuple[float, float]]:
        """
        Horizontal swim-lane layout: each business process gets a row,
        steps flow left-to-right. Branching steps appear below the main row.
        """
        self.positions['root'] = (0, -50)

        processes = self.data.get_children('root')
        row_height = 160
        y_start = 80

        for i, process in enumerate(processes):
            py = y_start + i * row_height
            self.positions[process.id] = (-500, py)

            # Get all descendant nodes and position them
            self._layout_process_tree(process.id, py)

        return self.positions

    def _layout_process_tree(self, process_id, base_y):
        """
        Layout all steps in a process. Follows the main chain (first children)
        left-to-right, and places branching nodes offset below.
        """
        # Walk the main chain (first child of first child...)
        main_chain = []
        children = self.data.get_children(process_id)
        if not children:
            return
        current = children[0]
        main_chain.append(current)
        visited = {current.id}
        while True:
            next_children = self.data.get_children(current.id)
            if not next_children:
                break
            current = next_children[0]
            main_chain.append(current)
            visited.add(current.id)

        # Position main chain left-to-right
        for j, step in enumerate(main_chain):
            sx = -300 + j * 140
            self.positions[step.id] = (sx, base_y)

        # Find and position any branching nodes (children not in main chain)
        branch_offset = 60
        for step in main_chain:
            all_children = self.data.get_children(step.id)
            for child in all_children:
                if child.id not in visited:
                    # Position branch below the parent step
                    parent_x, parent_y = self.positions[step.id]
                    self.positions[child.id] = (parent_x + 70, parent_y + branch_offset)
                    visited.add(child.id)


# ============================================================
# RADIAL LAYOUT ENGINE
# ============================================================

class RadialLayout:
    """
    Compute (x, y) positions for all nodes using a radial tree layout.

    - Root at center
    - Level-1 branches at equal angles around center (radius R1)
    - Level-2 sub-branches in arc sectors (radius R2)
    - Level-3 leaves at outer ring (radius R3)
    """

    R1 = 300   # Radius for branch nodes
    R2 = 580   # Radius for sub-branch nodes
    R3 = 800   # Radius for leaf nodes

    def __init__(self, data: MindMapData):
        self.data = data
        self.positions: dict[str, tuple[float, float]] = {}

    def compute(self) -> dict[str, tuple[float, float]]:
        """Compute all node positions."""
        # Root at center
        self.positions['root'] = (0.0, 0.0)

        branches = self.data.get_children('root')
        n_branches = len(branches)
        if n_branches == 0:
            return self.positions

        # Evenly space branches around the circle
        # Start from top (pi/2) and go clockwise
        start_angle = math.pi / 2
        for i, branch in enumerate(branches):
            angle = start_angle - (2 * math.pi * i / n_branches)
            bx = self.R1 * math.cos(angle)
            by = self.R1 * math.sin(angle)
            self.positions[branch.id] = (bx, by)

            # Layout children of this branch
            children = self.data.get_children(branch.id)
            if not children:
                continue

            # Each branch gets a sector proportional to its subtree size
            sector_size = 2 * math.pi / n_branches * 0.85  # leave gap

            # Distribute children within the sector
            n_children = len(children)
            for j, child in enumerate(children):
                if n_children == 1:
                    child_angle = angle
                else:
                    # Spread children within the sector
                    child_angle = angle - sector_size / 2 + sector_size * j / (n_children - 1)

                cx = self.R2 * math.cos(child_angle)
                cy = self.R2 * math.sin(child_angle)
                self.positions[child.id] = (cx, cy)

                # Layout grandchildren (leaves)
                leaves = self.data.get_children(child.id)
                if not leaves:
                    continue

                n_leaves = len(leaves)
                leaf_sector = sector_size / n_children * 0.9
                for k, leaf in enumerate(leaves):
                    if n_leaves == 1:
                        leaf_angle = child_angle
                    else:
                        leaf_angle = child_angle - leaf_sector / 2 + leaf_sector * k / (n_leaves - 1)

                    lx = self.R3 * math.cos(leaf_angle)
                    ly = self.R3 * math.sin(leaf_angle)
                    self.positions[leaf.id] = (lx, ly)

        return self.positions


# ============================================================
# MERMAID GENERATOR
# ============================================================

class MermaidGenerator:
    """Generate a Mermaid flowchart diagram."""

    SHAPE_MAP = {
        'root':        ('([', '])',),   # stadium
        'application': ('[', ']',),     # rect
        'database':    ('[(', ')]',),   # cylinder
        'automation':  ('[[', ']]',),   # subroutine
        'external':    ('{{', '}}',),   # hexagon
        'workflow':    ('([', '])',),    # stadium
        'library':     ('[/', '/]',),   # parallelogram
    }

    def __init__(self, data: MindMapData):
        self.data = data

    def _safe_id(self, id_str):
        """Convert node ID to Mermaid-safe identifier."""
        return id_str.replace('_', '')

    def _node_text(self, node):
        """Format node label for Mermaid (replace newlines with <br>)."""
        return node.label.replace('\n', '<br/>')

    def generate(self, output_path: Path) -> Path:
        """Generate the Mermaid Markdown file."""
        lines = [
            '# Tovito Trader Platform - Mind Map',
            '',
            '```mermaid',
            'flowchart TB',
            '',
        ]

        # Class definitions for styling
        for cat, color in CATEGORY_COLORS.items():
            lines.append(f'    classDef {cat} fill:{color},stroke:{color},color:#fff,stroke-width:2px')
        lines.append('')

        # Find root nodes (nodes with no parent)
        root_nodes = [n for n in self.data.nodes.values() if n.parent_id is None]
        for root in root_nodes:
            sid = self._safe_id(root.id)
            open_s, close_s = self.SHAPE_MAP.get(root.category, ('[', ']'))
            lines.append(f'    {sid}{open_s}"{self._node_text(root)}"{close_s}')
            lines.append(f'    class {sid} {root.category}')
        lines.append('')

        # Branch subgraphs — get children of all root nodes
        all_branches = []
        for root in root_nodes:
            all_branches.extend(self.data.get_children(root.id))

        for branch in all_branches:
            bsid = self._safe_id(branch.id)
            cat_label = CATEGORY_LABELS.get(branch.category, branch.category)
            lines.append(f'    subgraph sg{bsid}["{cat_label}"]')

            open_b, close_b = self.SHAPE_MAP[branch.category]
            lines.append(f'        {bsid}{open_b}"{self._node_text(branch)}"{close_b}')

            children = self.data.get_children(branch.id)
            for child in children:
                csid = self._safe_id(child.id)
                open_c, close_c = self.SHAPE_MAP[child.category]
                lines.append(f'        {csid}{open_c}"{self._node_text(child)}"{close_c}')

                # Show leaf nodes inline with parent (keeps diagram compact)
                leaves = self.data.get_children(child.id)
                for leaf in leaves:
                    lsid = self._safe_id(leaf.id)
                    open_l, close_l = self.SHAPE_MAP[leaf.category]
                    lines.append(f'        {lsid}{open_l}"{self._node_text(leaf)}"{close_l}')
                    lines.append(f'        {csid} --> {lsid}')

                lines.append(f'        {bsid} --> {csid}')

            lines.append('    end')
            if branch.parent_id:
                parent_sid = self._safe_id(branch.parent_id)
                lines.append(f'    {parent_sid} --> {bsid}')
            lines.append('')

            # Apply class styles
            lines.append(f'    class {bsid} {branch.category}')
            for child in children:
                csid = self._safe_id(child.id)
                lines.append(f'    class {csid} {child.category}')
                for leaf in self.data.get_children(child.id):
                    lsid = self._safe_id(leaf.id)
                    lines.append(f'    class {lsid} {leaf.category}')
            lines.append('')

        # Data flow arrows (dashed)
        lines.append('    %% Data Flow Connections')
        for edge in self.data.edges:
            if edge.edge_type == 'dataflow':
                src = self._safe_id(edge.source_id)
                tgt = self._safe_id(edge.target_id)
                if edge.label:
                    lines.append(f'    {src} -.->|"{edge.label}"| {tgt}')
                else:
                    lines.append(f'    {src} -.-> {tgt}')

        lines.append('```')
        lines.append('')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        return output_path


# ============================================================
# MATPLOTLIB PNG/SVG GENERATOR
# ============================================================

class MatplotlibGenerator:
    """Generate a high-resolution static mind map image."""

    FIG_WIDTH = 40   # inches
    FIG_HEIGHT = 30  # inches
    DPI = 150        # 6000x4500 px at full size

    def __init__(self, data: MindMapData, layout: dict[str, tuple[float, float]]):
        self.data = data
        self.positions = layout

    def _get_node_style(self, node):
        """Get visual style for a node based on its depth."""
        depth = self.data.get_depth(node.id)
        color = CATEGORY_COLORS.get(node.category, '#95a5a6')

        if depth == 0:  # Root
            return {
                'width': 2.8, 'height': 1.2,
                'facecolor': color, 'edgecolor': '#8b1a1a',
                'textcolor': 'white', 'fontsize': 16, 'fontweight': 'bold',
                'linewidth': 3,
            }
        elif depth == 1:  # Branch
            return {
                'width': 2.4, 'height': 1.0,
                'facecolor': color, 'edgecolor': color,
                'textcolor': 'white', 'fontsize': 11, 'fontweight': 'bold',
                'linewidth': 2,
            }
        elif depth == 2:  # Sub-branch
            return {
                'width': 2.2, 'height': 0.85,
                'facecolor': '#ffffff', 'edgecolor': color,
                'textcolor': '#333333', 'fontsize': 9, 'fontweight': 'normal',
                'linewidth': 1.5,
            }
        else:  # Leaf
            # Lighter version of category color
            return {
                'width': 2.0, 'height': 0.7,
                'facecolor': color + '20', 'edgecolor': color + '80',
                'textcolor': '#444444', 'fontsize': 7.5, 'fontweight': 'normal',
                'linewidth': 1,
            }

    def generate(self, png_path: Path, svg_path: Path) -> tuple[Path, Path]:
        """Generate PNG and SVG outputs."""
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.size': 9,
            'figure.facecolor': '#f8f9fa',
        })

        fig, ax = plt.subplots(figsize=(self.FIG_WIDTH, self.FIG_HEIGHT))
        ax.set_facecolor('#f8f9fa')
        ax.set_aspect('equal')
        ax.axis('off')

        # Scale factor to convert layout coords to figure coords
        scale = 0.04  # Each layout unit = 0.04 inches

        # Draw hierarchy edges first (behind nodes)
        for node in self.data.nodes.values():
            if node.parent_id and node.parent_id in self.positions and node.id in self.positions:
                px, py = self.positions[node.parent_id]
                nx, ny = self.positions[node.id]
                color = CATEGORY_COLORS.get(node.category, '#95a5a6')
                ax.plot(
                    [px * scale, nx * scale],
                    [py * scale, ny * scale],
                    color=color, alpha=0.4, linewidth=1.5,
                    zorder=1,
                )

        # Draw data flow edges (dashed, on top of hierarchy edges)
        for edge in self.data.edges:
            if edge.edge_type == 'dataflow':
                if edge.source_id in self.positions and edge.target_id in self.positions:
                    sx, sy = self.positions[edge.source_id]
                    tx, ty = self.positions[edge.target_id]
                    ax.annotate(
                        '', xy=(tx * scale, ty * scale),
                        xytext=(sx * scale, sy * scale),
                        arrowprops=dict(
                            arrowstyle='->', color='#555555',
                            lw=1.0, ls='--', alpha=0.5,
                            connectionstyle='arc3,rad=0.15',
                        ),
                        zorder=2,
                    )

        # Draw nodes
        for node_id, (x, y) in self.positions.items():
            node = self.data.nodes[node_id]
            style = self._get_node_style(node)

            sx, sy = x * scale, y * scale
            w, h = style['width'], style['height']

            # Draw rounded rectangle
            rect = FancyBboxPatch(
                (sx - w / 2, sy - h / 2), w, h,
                boxstyle=f"round,pad=0.1",
                facecolor=style['facecolor'],
                edgecolor=style['edgecolor'],
                linewidth=style['linewidth'],
                zorder=3,
            )
            ax.add_patch(rect)

            # Draw label text
            label = node.label.replace('\n', '\n')
            ax.text(
                sx, sy, label,
                ha='center', va='center',
                fontsize=style['fontsize'],
                fontweight=style['fontweight'],
                color=style['textcolor'],
                zorder=4,
                linespacing=1.2,
            )

        # Draw legend
        legend_x = self.FIG_WIDTH * 0.42
        legend_y = -self.FIG_HEIGHT * 0.40
        ax.text(legend_x, legend_y + 1.5, 'LEGEND', fontsize=12, fontweight='bold',
                color='#333333', zorder=5)
        for i, (cat, color) in enumerate(CATEGORY_COLORS.items()):
            if cat == 'root':
                continue
            yy = legend_y + 0.8 - i * 0.6
            rect = FancyBboxPatch(
                (legend_x - 0.3, yy - 0.15), 0.5, 0.3,
                boxstyle="round,pad=0.05",
                facecolor=color, edgecolor=color, linewidth=1, zorder=5,
            )
            ax.add_patch(rect)
            ax.text(legend_x + 0.5, yy, CATEGORY_LABELS.get(cat, cat),
                    fontsize=9, va='center', color='#333333', zorder=5)

        # Title
        ax.set_title('Tovito Trader Platform - Architecture Mind Map',
                      fontsize=22, fontweight='bold', color='#1e3a5f', pad=30)

        # Adjust limits with padding
        all_x = [p[0] * scale for p in self.positions.values()]
        all_y = [p[1] * scale for p in self.positions.values()]
        margin = 4
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)

        # Save
        png_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(png_path), dpi=self.DPI, bbox_inches='tight',
                    facecolor='#f8f9fa', edgecolor='none')
        fig.savefig(str(svg_path), format='svg', bbox_inches='tight',
                    facecolor='#f8f9fa', edgecolor='none')
        plt.close(fig)

        return png_path, svg_path


# ============================================================
# INTERACTIVE HTML GENERATOR
# ============================================================

class HtmlGenerator:
    """Generate an interactive self-contained HTML mind map."""

    def __init__(self, data: MindMapData, layout: dict[str, tuple[float, float]]):
        self.data = data
        self.positions = layout

    def _build_nodes_json(self):
        """Convert nodes to JSON-serializable format."""
        nodes = []
        for nid, node in self.data.nodes.items():
            if nid not in self.positions:
                continue
            x, y = self.positions[nid]
            depth = self.data.get_depth(nid)
            children_ids = [c.id for c in self.data.get_children(nid)]
            nodes.append({
                'id': nid,
                'label': node.label,
                'category': node.category,
                'parentId': node.parent_id,
                'x': round(x, 2),
                'y': round(-y, 2),  # Flip Y for SVG (Y grows downward)
                'depth': depth,
                'children': children_ids,
                'details': node.details,
                'color': CATEGORY_COLORS.get(node.category, '#95a5a6'),
            })
        return nodes

    def _build_edges_json(self):
        """Convert edges to JSON-serializable format."""
        edges = []
        # Hierarchy edges
        for node in self.data.nodes.values():
            if node.parent_id and node.id in self.positions and node.parent_id in self.positions:
                edges.append({
                    'source': node.parent_id,
                    'target': node.id,
                    'type': 'hierarchy',
                    'label': '',
                })
        # Data flow edges
        for edge in self.data.edges:
            if edge.edge_type == 'dataflow':
                edges.append({
                    'source': edge.source_id,
                    'target': edge.target_id,
                    'type': 'dataflow',
                    'label': edge.label,
                })
        return edges

    def generate(self, output_path: Path) -> Path:
        """Generate the interactive HTML file."""
        nodes_json = json.dumps(self._build_nodes_json(), indent=2)
        edges_json = json.dumps(self._build_edges_json(), indent=2)
        colors_json = json.dumps(CATEGORY_COLORS)
        labels_json = json.dumps(CATEGORY_LABELS)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tovito Trader - Platform Mind Map</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ margin: 0; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
        #mindmap-svg {{ cursor: grab; }}
        #mindmap-svg:active {{ cursor: grabbing; }}
        .node-group {{ cursor: pointer; transition: opacity 0.3s; }}
        .node-group:hover {{ opacity: 0.85; }}
        .node-rect {{ transition: stroke-width 0.2s; }}
        .node-group:hover .node-rect {{ stroke-width: 3; }}
        .edge-hierarchy {{ transition: opacity 0.3s; }}
        .edge-dataflow {{ stroke-dasharray: 8 4; }}
        .tooltip {{
            position: fixed; padding: 8px 12px; background: rgba(30,58,95,0.95);
            color: white; border-radius: 6px; font-size: 12px; pointer-events: none;
            z-index: 1000; max-width: 250px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            display: none;
        }}
        .search-highlight .node-rect {{ stroke: #f39c12 !important; stroke-width: 4 !important; }}
        .search-dimmed {{ opacity: 0.15; }}
        .collapsed {{ display: none; }}
        .legend-item {{ cursor: pointer; }}
        .legend-item:hover {{ opacity: 0.7; }}
    </style>
</head>
<body class="bg-gray-100">
    <!-- Header -->
    <header class="fixed top-0 left-0 right-0 z-50 bg-white shadow-md px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-3">
            <h1 class="text-lg font-bold text-gray-800">Tovito Trader - Platform Mind Map</h1>
        </div>
        <div class="flex items-center gap-3">
            <input id="search-input" type="text" placeholder="Search nodes..."
                   class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-56 focus:ring-2 focus:ring-blue-400 focus:outline-none">
            <button id="btn-reset" class="px-3 py-1.5 bg-gray-200 hover:bg-gray-300 rounded-lg text-sm font-medium transition">
                Reset View
            </button>
            <button id="btn-expand" class="px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-800 rounded-lg text-sm font-medium transition">
                Expand All
            </button>
            <button id="btn-collapse" class="px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-800 rounded-lg text-sm font-medium transition">
                Collapse All
            </button>
            <span class="text-xs text-gray-400">Scroll to zoom | Drag to pan | Click to expand/collapse</span>
        </div>
    </header>

    <!-- Legend -->
    <aside id="legend" class="fixed bottom-4 left-4 z-40 bg-white rounded-xl shadow-lg p-4 text-sm">
        <h3 class="font-bold text-gray-700 mb-2">Legend</h3>
        <div id="legend-items" class="space-y-1.5"></div>
        <div class="mt-3 pt-2 border-t border-gray-200">
            <div class="flex items-center gap-2">
                <svg width="30" height="10"><line x1="0" y1="5" x2="30" y2="5" stroke="#555" stroke-width="1.5" stroke-dasharray="4 3"/><polygon points="28,2 30,5 28,8" fill="#555"/></svg>
                <span class="text-gray-600">Data Flow</span>
            </div>
        </div>
    </aside>

    <!-- Tooltip -->
    <div id="tooltip" class="tooltip"></div>

    <!-- SVG Canvas -->
    <svg id="mindmap-svg" width="100%" height="100%" style="position:fixed;top:48px;left:0;right:0;bottom:0;">
        <g id="viewport">
            <g id="edges-layer"></g>
            <g id="nodes-layer"></g>
        </g>
    </svg>

    <script>
    // ============================
    // DATA
    // ============================
    const NODES = {nodes_json};
    const EDGES = {edges_json};
    const COLORS = {colors_json};
    const LABELS = {labels_json};

    // ============================
    // STATE
    // ============================
    let viewBox = {{ x: -900, y: -900, w: 1800, h: 1800 }};
    let isPanning = false;
    let panStart = {{ x: 0, y: 0 }};
    const collapsedNodes = new Set();
    const nodeMap = {{}};
    NODES.forEach(n => nodeMap[n.id] = n);

    // ============================
    // RENDERING
    // ============================
    const svg = document.getElementById('mindmap-svg');
    const viewport = document.getElementById('viewport');
    const edgesLayer = document.getElementById('edges-layer');
    const nodesLayer = document.getElementById('nodes-layer');
    const tooltip = document.getElementById('tooltip');

    function updateViewBox() {{
        svg.setAttribute('viewBox', `${{viewBox.x}} ${{viewBox.y}} ${{viewBox.w}} ${{viewBox.h}}`);
    }}

    function getNodeSize(depth) {{
        if (depth === 0) return {{ w: 180, h: 70 }};
        if (depth === 1) return {{ w: 150, h: 60 }};
        if (depth === 2) return {{ w: 140, h: 55 }};
        return {{ w: 130, h: 48 }};
    }}

    function isHidden(nodeId) {{
        const node = nodeMap[nodeId];
        if (!node) return false;
        let current = node.parentId;
        while (current) {{
            if (collapsedNodes.has(current)) return true;
            current = nodeMap[current] ? nodeMap[current].parentId : null;
        }}
        return false;
    }}

    function render() {{
        edgesLayer.innerHTML = '';
        nodesLayer.innerHTML = '';

        // Draw edges
        EDGES.forEach(edge => {{
            const src = nodeMap[edge.source];
            const tgt = nodeMap[edge.target];
            if (!src || !tgt) return;
            if (isHidden(edge.source) || isHidden(edge.target)) return;

            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', src.x);
            line.setAttribute('y1', src.y);
            line.setAttribute('x2', tgt.x);
            line.setAttribute('y2', tgt.y);

            if (edge.type === 'dataflow') {{
                line.setAttribute('stroke', '#888');
                line.setAttribute('stroke-width', '1.5');
                line.classList.add('edge-dataflow');
                line.setAttribute('marker-end', 'url(#arrowhead)');
            }} else {{
                line.setAttribute('stroke', tgt.color + '66');
                line.setAttribute('stroke-width', '2');
                line.classList.add('edge-hierarchy');
            }}
            edgesLayer.appendChild(line);
        }});

        // Draw nodes
        NODES.forEach(node => {{
            if (isHidden(node.id)) return;

            const size = getNodeSize(node.depth);
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.classList.add('node-group');
            g.setAttribute('data-id', node.id);
            g.setAttribute('transform', `translate(${{node.x}}, ${{node.y}})`);

            // Rectangle
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', -size.w / 2);
            rect.setAttribute('y', -size.h / 2);
            rect.setAttribute('width', size.w);
            rect.setAttribute('height', size.h);
            rect.setAttribute('rx', 8);
            rect.classList.add('node-rect');

            if (node.depth <= 1) {{
                rect.setAttribute('fill', node.color);
                rect.setAttribute('stroke', node.color);
                rect.setAttribute('stroke-width', '2');
            }} else if (node.depth === 2) {{
                rect.setAttribute('fill', '#ffffff');
                rect.setAttribute('stroke', node.color);
                rect.setAttribute('stroke-width', '1.5');
            }} else {{
                rect.setAttribute('fill', node.color + '18');
                rect.setAttribute('stroke', node.color + '60');
                rect.setAttribute('stroke-width', '1');
            }}
            g.appendChild(rect);

            // Collapse indicator
            if (node.children && node.children.length > 0) {{
                const indicator = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                indicator.setAttribute('x', size.w / 2 - 12);
                indicator.setAttribute('y', -size.h / 2 + 14);
                indicator.setAttribute('font-size', '12');
                indicator.setAttribute('fill', node.depth <= 1 ? '#ffffff99' : '#99999999');
                indicator.textContent = collapsedNodes.has(node.id) ? '+' : (node.children.length > 0 ? '-' : '');
                g.appendChild(indicator);
            }}

            // Label text
            const lines = node.label.split('\\n');
            lines.forEach((line, i) => {{
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', 0);
                const yOffset = (i - (lines.length - 1) / 2) * 14;
                text.setAttribute('y', yOffset + 4);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('fill', node.depth <= 1 ? '#ffffff' : '#333333');
                text.setAttribute('font-size', node.depth === 0 ? '14' : node.depth === 1 ? '11' : '9');
                text.setAttribute('font-weight', node.depth <= 1 ? 'bold' : 'normal');
                text.style.pointerEvents = 'none';
                text.textContent = line;
                g.appendChild(text);
            }});

            // Events
            g.addEventListener('click', () => toggleCollapse(node.id));
            g.addEventListener('mouseenter', (e) => showTooltip(e, node));
            g.addEventListener('mouseleave', () => hideTooltip());

            nodesLayer.appendChild(g);
        }});

        // Add arrowhead marker
        let defs = svg.querySelector('defs');
        if (!defs) {{
            defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            svg.insertBefore(defs, svg.firstChild);
        }}
        if (!defs.querySelector('#arrowhead')) {{
            const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
            marker.setAttribute('id', 'arrowhead');
            marker.setAttribute('markerWidth', '8');
            marker.setAttribute('markerHeight', '6');
            marker.setAttribute('refX', '8');
            marker.setAttribute('refY', '3');
            marker.setAttribute('orient', 'auto');
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', 'M0,0 L8,3 L0,6 Z');
            path.setAttribute('fill', '#888');
            marker.appendChild(path);
            defs.appendChild(marker);
        }}
    }}

    // ============================
    // INTERACTIONS
    // ============================
    function toggleCollapse(nodeId) {{
        const node = nodeMap[nodeId];
        if (!node || !node.children || node.children.length === 0) return;
        if (collapsedNodes.has(nodeId)) {{
            collapsedNodes.delete(nodeId);
        }} else {{
            collapsedNodes.add(nodeId);
        }}
        render();
    }}

    function showTooltip(event, node) {{
        let info = `<strong>${{node.label.replace(/\\n/g, ' ')}}</strong>`;
        info += `<br><em>${{LABELS[node.category] || node.category}}</em>`;
        if (node.details) {{
            if (node.details.tech) info += `<br>Tech: ${{node.details.tech}}`;
            if (node.details.port) info += `<br>Port: ${{node.details.port}}`;
        }}
        if (node.children && node.children.length > 0) {{
            info += `<br>Children: ${{node.children.length}}`;
        }}
        tooltip.innerHTML = info;
        tooltip.style.display = 'block';
        tooltip.style.left = (event.clientX + 15) + 'px';
        tooltip.style.top = (event.clientY - 10) + 'px';
    }}

    function hideTooltip() {{
        tooltip.style.display = 'none';
    }}

    // Zoom
    svg.addEventListener('wheel', (e) => {{
        e.preventDefault();
        const scale = e.deltaY > 0 ? 1.1 : 0.9;
        const rect = svg.getBoundingClientRect();
        const mx = (e.clientX - rect.left) / rect.width;
        const my = (e.clientY - rect.top) / rect.height;

        const newW = viewBox.w * scale;
        const newH = viewBox.h * scale;
        viewBox.x += (viewBox.w - newW) * mx;
        viewBox.y += (viewBox.h - newH) * my;
        viewBox.w = newW;
        viewBox.h = newH;
        updateViewBox();
    }});

    // Pan
    svg.addEventListener('mousedown', (e) => {{
        if (e.target.closest('.node-group')) return;
        isPanning = true;
        panStart.x = e.clientX;
        panStart.y = e.clientY;
    }});

    window.addEventListener('mousemove', (e) => {{
        if (!isPanning) return;
        const rect = svg.getBoundingClientRect();
        const dx = (e.clientX - panStart.x) / rect.width * viewBox.w;
        const dy = (e.clientY - panStart.y) / rect.height * viewBox.h;
        viewBox.x -= dx;
        viewBox.y -= dy;
        panStart.x = e.clientX;
        panStart.y = e.clientY;
        updateViewBox();
    }});

    window.addEventListener('mouseup', () => {{ isPanning = false; }});

    // Search
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', () => {{
        const query = searchInput.value.toLowerCase().trim();
        document.querySelectorAll('.node-group').forEach(g => {{
            g.classList.remove('search-highlight', 'search-dimmed');
        }});
        if (!query) return;

        const matchIds = new Set();
        NODES.forEach(n => {{
            if (n.label.toLowerCase().includes(query) || n.id.toLowerCase().includes(query)) {{
                matchIds.add(n.id);
            }}
        }});

        document.querySelectorAll('.node-group').forEach(g => {{
            const id = g.getAttribute('data-id');
            if (matchIds.has(id)) {{
                g.classList.add('search-highlight');
            }} else {{
                g.classList.add('search-dimmed');
            }}
        }});
    }});

    // Buttons
    document.getElementById('btn-reset').addEventListener('click', () => {{
        viewBox = {{ x: -900, y: -900, w: 1800, h: 1800 }};
        collapsedNodes.clear();
        searchInput.value = '';
        document.querySelectorAll('.node-group').forEach(g => {{
            g.classList.remove('search-highlight', 'search-dimmed');
        }});
        updateViewBox();
        render();
    }});

    document.getElementById('btn-expand').addEventListener('click', () => {{
        collapsedNodes.clear();
        render();
    }});

    document.getElementById('btn-collapse').addEventListener('click', () => {{
        NODES.forEach(n => {{
            if (n.children && n.children.length > 0 && n.depth >= 1) {{
                collapsedNodes.add(n.id);
            }}
        }});
        render();
    }});

    // Legend
    const legendItems = document.getElementById('legend-items');
    Object.entries(LABELS).forEach(([cat, label]) => {{
        if (cat === 'root') return;
        const color = COLORS[cat];
        const div = document.createElement('div');
        div.className = 'flex items-center gap-2 legend-item';
        div.innerHTML = `<span class="inline-block w-4 h-4 rounded" style="background:${{color}}"></span><span class="text-gray-700">${{label}}</span>`;
        legendItems.appendChild(div);
    }});

    // ============================
    // INIT
    // ============================
    updateViewBox();
    render();
    </script>
</body>
</html>"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        return output_path


# ============================================================
# CLI ENTRY POINT
# ============================================================

def _generate_view(name, title, data, positions, output_dir, fmt, results):
    """Generate all requested formats for a single view."""
    prefix = name  # e.g. 'tovito_platform', 'database_impact', 'business_process'

    if fmt in ('all', 'mermaid'):
        mermaid_path = output_dir / f'{prefix}.md'
        MermaidGenerator(data).generate(mermaid_path)
        size = mermaid_path.stat().st_size / 1024
        print(f'  Mermaid: {mermaid_path} ({size:.0f} KB)')
        results.append((f'{title} Mermaid', mermaid_path))

    if fmt in ('all', 'png'):
        png_path = output_dir / f'{prefix}.png'
        svg_path = output_dir / f'{prefix}.svg'
        MatplotlibGenerator(data, positions).generate(png_path, svg_path)
        png_size = png_path.stat().st_size / 1024
        svg_size = svg_path.stat().st_size / 1024
        print(f'  PNG: {png_path} ({png_size:.0f} KB)')
        print(f'  SVG: {svg_path} ({svg_size:.0f} KB)')
        results.append((f'{title} PNG', png_path))
        results.append((f'{title} SVG', svg_path))

    if fmt in ('all', 'html'):
        html_path = output_dir / f'{prefix}.html'
        HtmlGenerator(data, positions).generate(html_path)
        size = html_path.stat().st_size / 1024
        print(f'  HTML: {html_path} ({size:.0f} KB)')
        results.append((f'{title} HTML', html_path))


def main():
    parser = argparse.ArgumentParser(
        description='Generate Tovito Trader platform mind map in multiple formats.'
    )
    parser.add_argument(
        '--format', choices=['all', 'html', 'mermaid', 'png'],
        default='all',
        help='Output format (default: all)',
    )
    parser.add_argument(
        '--output-dir', type=Path, default=OUTPUT_DIR,
        help=f'Output directory (default: {OUTPUT_DIR})',
    )
    parser.add_argument(
        '--open', action='store_true',
        help='Open HTML output in browser after generation',
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print('=' * 60)
    print('Tovito Trader Platform Mind Map Generator')
    print('=' * 60)

    results = []

    # --------------------------------------------------------
    # VIEW 1: Architecture (comprehensive platform overview)
    # --------------------------------------------------------
    print('\n--- View 1: Platform Architecture ---')
    print('Building data model...')
    arch_data = MindMapData()
    arch_data.build()
    print(f'  Nodes: {len(arch_data.nodes)}, Data flows: {len(arch_data.edges)}')

    print('Computing radial layout...')
    arch_positions = RadialLayout(arch_data).compute()
    print(f'  Positioned: {len(arch_positions)} nodes')

    _generate_view('tovito_platform', 'Architecture', arch_data, arch_positions,
                    output_dir, args.format, results)

    # --------------------------------------------------------
    # VIEW 2: Database Impact (processes → tables)
    # --------------------------------------------------------
    print('\n--- View 2: Database Impact ---')
    print('Building database impact model...')
    db_data = DatabaseImpactData()
    db_data.build()
    print(f'  Nodes: {len(db_data.nodes)}, Data flows: {len(db_data.edges)}')

    print('Computing column layout...')
    db_layout = FlowLayout(db_data)
    db_positions = db_layout.compute_database_impact()
    print(f'  Positioned: {len(db_positions)} nodes')

    _generate_view('database_impact', 'DB Impact', db_data, db_positions,
                    output_dir, args.format, results)

    # --------------------------------------------------------
    # VIEW 3: Business Processes (manual workflows end-to-end)
    # --------------------------------------------------------
    print('\n--- View 3: Business Processes ---')
    print('Building business process model...')
    bp_data = BusinessProcessData()
    bp_data.build()
    print(f'  Nodes: {len(bp_data.nodes)}, Flows: {len(bp_data.edges)}')

    print('Computing swim-lane layout...')
    bp_layout = FlowLayout(bp_data)
    bp_positions = bp_layout.compute_business_process()
    print(f'  Positioned: {len(bp_positions)} nodes')

    _generate_view('business_process', 'Biz Process', bp_data, bp_positions,
                    output_dir, args.format, results)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    print('\n' + '=' * 60)
    print('Generation Summary')
    print('=' * 60)
    for fmt_label, path in results:
        print(f'  {fmt_label:25s} {path}')
    print(f'  Output directory: {output_dir}')

    # Open in browser
    if args.open:
        html_path = output_dir / 'tovito_platform.html'
        if html_path.exists():
            print(f'\nOpening {html_path} in browser...')
            webbrowser.open(str(html_path))

    return 0


if __name__ == '__main__':
    sys.exit(main())
