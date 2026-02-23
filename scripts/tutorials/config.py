"""
Tutorial System Configuration
==============================

Central configuration for video resolution, output paths, quality settings,
and the tutorial registry mapping IDs to metadata.
"""

import shutil
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / 'scripts'
TUTORIALS_DIR = SCRIPTS_DIR / 'tutorials'
TEMPLATES_DIR = TUTORIALS_DIR / 'templates'

# Output directories
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'tutorials'
VIDEO_DIR = OUTPUT_DIR / 'videos'
GUIDE_DIR = OUTPUT_DIR / 'guides'
SCREENSHOT_DIR = OUTPUT_DIR / 'screenshots'

# Dev database for recordings
DEV_DB_PATH = PROJECT_ROOT / 'data' / 'dev_tovito.db'

# Frontend public directory (for deploying investor-facing tutorials)
FRONTEND_PUBLIC_DIR = (
    PROJECT_ROOT / 'apps' / 'investor_portal' / 'frontend'
    / 'investor_portal' / 'public' / 'tutorials'
)

# ============================================================
# VIDEO / IMAGE SETTINGS
# ============================================================

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
VIDEO_CRF = 28  # H.264 quality (lower = better, 18-28 is typical)
FRAME_DURATION_SECONDS = 3  # How long each CLI frame shows in video
TITLE_CARD_DURATION = 3  # Seconds for title card
END_CARD_DURATION = 2  # Seconds for end card

# Terminal rendering (for CLI tutorials)
TERMINAL_COLS = 100
TERMINAL_ROWS = 35
TERMINAL_BG_COLOR = (30, 30, 46)  # Dark background
TERMINAL_FG_COLOR = (205, 214, 244)  # Light text
TERMINAL_FONT_SIZE = 16
TERMINAL_PADDING = 20

# Screenshot annotations
CALLOUT_COLOR = (239, 68, 68)  # Red for numbered callouts
CALLOUT_FONT_SIZE = 18
ARROW_COLOR = (59, 130, 246)  # Blue for arrows
LABEL_BG_COLOR = (0, 0, 0, 180)  # Semi-transparent black
LABEL_FG_COLOR = (255, 255, 255)  # White text

# ============================================================
# TUTORIAL REGISTRY
# ============================================================

TUTORIAL_REGISTRY = {
    # Admin CLI tutorials
    'admin_fund_flow': {
        'title': 'Processing a Contribution/Withdrawal',
        'description': 'Walk through the 3-step fund flow process: submit, match, and process.',
        'category': 'admin',
        'duration': '1:30',
        'module': 'scripts.tutorials.admin.tutorial_fund_flow',
    },
    'admin_daily_nav': {
        'title': 'Running Daily NAV Update',
        'description': 'Execute the daily NAV calculation pipeline.',
        'category': 'admin',
        'duration': '0:45',
        'module': 'scripts.tutorials.admin.tutorial_daily_nav',
    },
    'admin_close_account': {
        'title': 'Closing an Investor Account',
        'description': 'Full account liquidation via the fund flow pathway.',
        'category': 'admin',
        'duration': '1:00',
        'module': 'scripts.tutorials.admin.tutorial_close_account',
    },
    'admin_profile_mgmt': {
        'title': 'Managing Investor Profiles',
        'description': 'View and edit investor profile information.',
        'category': 'admin',
        'duration': '0:45',
        'module': 'scripts.tutorials.admin.tutorial_profile_mgmt',
    },
    'admin_monthly_report': {
        'title': 'Generating Monthly Reports',
        'description': 'Generate and review monthly investor statements.',
        'category': 'admin',
        'duration': '0:30',
        'module': 'scripts.tutorials.admin.tutorial_monthly_report',
    },
    'admin_backup': {
        'title': 'Backing Up the Database',
        'description': 'Create a timestamped backup of the production database.',
        'category': 'admin',
        'duration': '0:20',
        'module': 'scripts.tutorials.admin.tutorial_backup',
    },

    # Launch tutorials
    'launch_investor_portal': {
        'title': 'Starting the Investor Portal',
        'description': 'Launch the FastAPI backend and React frontend.',
        'category': 'launching',
        'duration': '0:30',
        'module': 'scripts.tutorials.launching.tutorial_investor_portal',
    },
    'launch_market_monitor': {
        'title': 'Starting the Market Monitor',
        'description': 'Launch the Streamlit market monitoring dashboard.',
        'category': 'launching',
        'duration': '0:20',
        'module': 'scripts.tutorials.launching.tutorial_market_monitor',
    },
    'launch_ops_dashboard': {
        'title': 'Starting the Ops Dashboard',
        'description': 'Launch the operations health dashboard.',
        'category': 'launching',
        'duration': '0:20',
        'module': 'scripts.tutorials.launching.tutorial_ops_dashboard',
    },
    'launch_fund_manager': {
        'title': 'Starting the Fund Manager',
        'description': 'Launch the fund manager desktop application.',
        'category': 'launching',
        'duration': '0:20',
        'module': 'scripts.tutorials.launching.tutorial_fund_manager',
    },

    # Investor portal browser tutorials
    'investor_login': {
        'title': 'Logging Into Your Account',
        'description': 'How to sign in to the Tovito Trader investor portal.',
        'category': 'getting-started',
        'duration': '0:30',
        'module': 'scripts.tutorials.investor.tutorial_login',
    },
    'investor_dashboard': {
        'title': 'Your Dashboard Overview',
        'description': 'Tour of the main dashboard showing your portfolio and performance.',
        'category': 'getting-started',
        'duration': '0:45',
        'module': 'scripts.tutorials.investor.tutorial_dashboard',
    },
    'investor_portfolio': {
        'title': 'Viewing Your Portfolio',
        'description': 'How to check your current position, NAV, and returns.',
        'category': 'getting-started',
        'duration': '0:30',
        'module': 'scripts.tutorials.investor.tutorial_portfolio',
    },
    'investor_transactions': {
        'title': 'Transaction History',
        'description': 'How to view your contribution and withdrawal history.',
        'category': 'getting-started',
        'duration': '0:30',
        'module': 'scripts.tutorials.investor.tutorial_transactions',
    },
}

# Category display names
CATEGORY_LABELS = {
    'admin': 'Admin Operations',
    'launching': 'Launching Apps',
    'getting-started': 'Getting Started',
}


def get_tutorials_by_category(category):
    """Return tutorial IDs matching a category."""
    return [
        tid for tid, meta in TUTORIAL_REGISTRY.items()
        if meta['category'] == category
    ]


def ensure_output_dirs():
    """Create output directories if they don't exist."""
    for d in [OUTPUT_DIR, VIDEO_DIR, GUIDE_DIR, SCREENSHOT_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def check_ffmpeg():
    """Check if ffmpeg is available on PATH."""
    return shutil.which('ffmpeg') is not None
