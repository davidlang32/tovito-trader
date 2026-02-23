"""
Tutorial: Starting the Fund Manager
=====================================

Records how to launch the fund manager desktop application.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'launch_fund_manager'


class FundManagerLaunchTutorial(BaseRecorder):
    """Records how to start the fund manager dashboard."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        launch_text = (
            "# Starting the Fund Manager Dashboard\n"
            "#\n"
            "# The fund manager is a CustomTkinter desktop application for:\n"
            "#   - Viewing and managing all investor accounts\n"
            "#   - Processing fund flow requests\n"
            "#   - Running NAV updates\n"
            "#   - Generating reports\n"
            "#   - Database management\n"
            "\n"
            "$ python run.py\n"
            "\n"
            "# Or launch directly:\n"
            "$ python apps/fund_manager/main.py\n"
            "\n"
            "# The desktop application window will open.\n"
            "# Close the window or press Ctrl+C to stop."
        )
        path = save_terminal_frame(
            launch_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Fund Manager',
        )
        self.add_step(
            'Launch Fund Manager',
            'Run python run.py or launch directly from apps/fund_manager/. '
            'A desktop window opens with the fund management interface.',
            str(path),
        )


if __name__ == '__main__':
    FundManagerLaunchTutorial(TUTORIAL_ID).run()
