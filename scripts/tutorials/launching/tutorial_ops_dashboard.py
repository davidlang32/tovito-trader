"""
Tutorial: Starting the Ops Dashboard
======================================

Records how to launch the operations health dashboard.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'launch_ops_dashboard'


class OpsDashboardLaunchTutorial(BaseRecorder):
    """Records how to start the ops dashboard."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        launch_text = (
            "# Starting the Operations Health Dashboard\n"
            "#\n"
            "# The ops dashboard monitors system health:\n"
            "#   - Overall health score\n"
            "#   - Data freshness indicators\n"
            "#   - Automation status (NAV, watchdog, trades)\n"
            "#   - Reconciliation results\n"
            "#   - NAV gap detection\n"
            "#   - System logs and email delivery\n"
            "#   - Actionable remediation guidance\n"
            "\n"
            "$ python -m streamlit run apps/ops_dashboard/app.py --server.port 8502\n"
            "\n"
            "  You can now view your Streamlit app in your browser.\n"
            "\n"
            "  Local URL: http://localhost:8502\n"
            "  Network URL: http://192.168.1.100:8502\n"
            "\n"
            "# Open http://localhost:8502 in your browser.\n"
            "# Note: Uses port 8502 to avoid conflict with market monitor (8501)."
        )
        path = save_terminal_frame(
            launch_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Ops Dashboard',
        )
        self.add_step(
            'Launch Ops Dashboard',
            'Run streamlit on port 8502. The dashboard shows health scores, automation status, '
            'and provides remediation guidance for any issues detected.',
            str(path),
        )


if __name__ == '__main__':
    OpsDashboardLaunchTutorial(TUTORIAL_ID).run()
