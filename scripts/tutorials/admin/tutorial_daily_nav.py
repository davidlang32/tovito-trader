"""
Tutorial: Running Daily NAV Update
====================================

Records the daily NAV calculation pipeline execution.
This is a non-interactive script, so we use CLICommandRecorder.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import CLICommandRecorder, save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'admin_daily_nav'


class DailyNavTutorial(BaseRecorder):
    """Records the daily NAV update pipeline."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Overview frame
        overview_text = (
            "# Daily NAV Update Pipeline\n"
            "#\n"
            "# This script runs automatically at 4:05 PM EST via Task Scheduler.\n"
            "# It can also be run manually when needed.\n"
            "#\n"
            "# 7-Step Pipeline:\n"
            "#   1. Fetch portfolio balance from TastyTrade\n"
            "#   2. Calculate NAV (total_value / total_shares)\n"
            "#   3. Write heartbeat + ping healthchecks.io\n"
            "#   4. Snapshot holdings & positions\n"
            "#   5. Run daily reconciliation\n"
            "#   6. Sync brokerage trades via ETL (last 3 days)\n"
            "#   7. Update Discord pinned NAV message\n"
            "\n"
            "$ python scripts/daily_nav_enhanced.py"
        )
        path = save_terminal_frame(
            overview_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Daily NAV Update',
        )
        self.add_step(
            'Pipeline Overview',
            'The daily NAV script runs 7 steps to update the fund\'s Net Asset Value. '
            'Steps 4-7 are non-fatal (failures don\'t block the NAV update).',
            str(path),
        )

        # Step 1-2: Fetch and Calculate
        fetch_text = (
            "$ python scripts/daily_nav_enhanced.py\n"
            "\n"
            "=== Daily NAV Update ===\n"
            "Date: 2026-01-05\n"
            "\n"
            "[Step 1] Fetching portfolio balance...\n"
            "  Provider: TastyTrade\n"
            "  Account balance: (fetched successfully)\n"
            "\n"
            "[Step 2] Calculating NAV...\n"
            "  Total portfolio value: $40,260.00\n"
            "  Total shares: 38,000.0000\n"
            "  NAV per share: $1.0595\n"
            "  Daily change: +$0.0125 (+1.20%)\n"
            "  Written to daily_nav table.\n"
        )
        path = save_terminal_frame(
            fetch_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step02.png',
            title='daily_nav_enhanced.py',
        )
        self.add_step(
            'Fetch Balance & Calculate NAV',
            'The script fetches the current portfolio balance from the brokerage and calculates '
            'NAV per share by dividing total portfolio value by total outstanding shares.',
            str(path),
        )

        # Steps 3-7: Remaining pipeline
        remaining_text = (
            "[Step 3] Writing heartbeat...\n"
            "  Heartbeat: logs/daily_nav_heartbeat.txt\n"
            "  Healthchecks.io ping: sent\n"
            "\n"
            "[Step 4] Snapshotting holdings...\n"
            "  Holdings snapshot saved (12 positions)\n"
            "\n"
            "[Step 5] Running reconciliation...\n"
            "  Reconciliation: matched (diff: $0.00)\n"
            "\n"
            "[Step 6] Syncing trades via ETL...\n"
            "  ETL: 0 new trades (last 3 days)\n"
            "\n"
            "[Step 7] Updating Discord NAV message...\n"
            "  Discord: pinned message updated with chart\n"
            "\n"
            "=== NAV Update Complete ===\n"
            "  Date: 2026-01-05\n"
            "  NAV: $1.0595\n"
            "  All 7 steps completed successfully."
        )
        path = save_terminal_frame(
            remaining_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step03.png',
            title='daily_nav_enhanced.py',
        )
        self.add_step(
            'Complete Pipeline Execution',
            'Steps 3-7 handle heartbeat monitoring, position snapshots, reconciliation, '
            'trade sync via ETL, and Discord notification. All steps report their status.',
            str(path),
        )

        # Automation note
        automation_text = (
            "# Automated Scheduling\n"
            "#\n"
            "# The daily NAV update is scheduled via Windows Task Scheduler:\n"
            "#   Task: Tovito Daily NAV\n"
            "#   Schedule: Daily at 4:05 PM EST (after market close)\n"
            "#   Launcher: run_daily.bat\n"
            "#\n"
            "# Monitoring:\n"
            "#   - Heartbeat file: logs/daily_nav_heartbeat.txt\n"
            "#   - Healthchecks.io: alerts if no ping within grace period\n"
            "#   - Watchdog: runs at 5:05 PM to verify NAV was updated\n"
            "#\n"
            "# To run manually:\n"
            "$ python scripts/daily_nav_enhanced.py\n"
            "#\n"
            "# Or use the batch file:\n"
            "$ run_daily.bat"
        )
        path = save_terminal_frame(
            automation_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step04.png',
            title='Automation',
        )
        self.add_step(
            'Automated Scheduling',
            'The NAV update runs automatically via Task Scheduler. Healthchecks.io and '
            'the watchdog monitor alert if the update fails.',
            str(path),
        )


if __name__ == '__main__':
    DailyNavTutorial(TUTORIAL_ID).run()
