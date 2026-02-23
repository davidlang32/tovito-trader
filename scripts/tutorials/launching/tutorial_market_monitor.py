"""
Tutorial: Starting the Market Monitor
=======================================

Records how to launch the Streamlit market monitoring dashboard.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'launch_market_monitor'


class MarketMonitorLaunchTutorial(BaseRecorder):
    """Records how to start the market monitor."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        launch_text = (
            "# Starting the Market Monitor\n"
            "#\n"
            "# The market monitor is a Streamlit dashboard showing:\n"
            "#   - Portfolio alerts and notifications\n"
            "#   - Real-time market data streaming\n"
            "#   - Alert rule configuration\n"
            "\n"
            "$ cd apps/market_monitor\n"
            "$ streamlit run main.py\n"
            "\n"
            "  You can now view your Streamlit app in your browser.\n"
            "\n"
            "  Local URL: http://localhost:8501\n"
            "  Network URL: http://192.168.1.100:8501\n"
            "\n"
            "# Open http://localhost:8501 in your browser.\n"
            "# Press Ctrl+C to stop."
        )
        path = save_terminal_frame(
            launch_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Market Monitor',
        )
        self.add_step(
            'Launch Market Monitor',
            'Run streamlit from the market_monitor directory. The dashboard opens '
            'automatically at http://localhost:8501.',
            str(path),
        )


if __name__ == '__main__':
    MarketMonitorLaunchTutorial(TUTORIAL_ID).run()
