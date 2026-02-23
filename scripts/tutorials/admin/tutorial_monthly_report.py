"""
Tutorial: Generating Monthly Reports
======================================

Records the monthly report generation process.
This is non-interactive (CLI args only).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'admin_monthly_report'


class MonthlyReportTutorial(BaseRecorder):
    """Records the monthly report generation workflow."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Overview
        overview_text = (
            "# Generating Monthly Reports\n"
            "#\n"
            "# Creates PDF investor statements with:\n"
            "#   - Account summary and current position\n"
            "#   - Monthly performance with NAV chart\n"
            "#   - Transaction history for the month\n"
            "#   - Fund performance metrics\n"
            "#\n"
            "# Common usage:\n"
            "#   Generate for all investors:     --month 1 --year 2026\n"
            "#   Generate for one investor:      --investor 20260101-01A\n"
            "#   Email reports automatically:    --email\n"
            "#   Previous month (for automation): --previous-month --email\n"
            "\n"
            "$ python scripts/reporting/generate_monthly_report.py --month 1 --year 2026"
        )
        path = save_terminal_frame(
            overview_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Monthly Reports',
        )
        self.add_step(
            'Report Generation Options',
            'The report script accepts month/year, investor ID, and email flags. '
            'Use --previous-month for automated monthly runs.',
            str(path),
        )

        # Execution output
        run_text = (
            "$ python scripts/reporting/generate_monthly_report.py --month 1 --year 2026 --email\n"
            "\n"
            "=== Monthly Report Generation ===\n"
            "Period: January 2026\n"
            "\n"
            "Generating reports for 4 active investors...\n"
            "\n"
            "  Alpha Investor... PDF saved to data/reports/2026-01_alpha.pdf\n"
            "    Email sent to alpha@test.com\n"
            "  Beta Investor...  PDF saved to data/reports/2026-01_beta.pdf\n"
            "    Email sent to beta@test.com\n"
            "  Gamma Investor... PDF saved to data/reports/2026-01_gamma.pdf\n"
            "    Email sent to gamma@test.com\n"
            "  Delta Investor... PDF saved to data/reports/2026-01_delta.pdf\n"
            "    Email sent to delta@test.com\n"
            "\n"
            "SUCCESS: 4 reports generated, 4 emails sent.\n"
            "  Output directory: data/reports/"
        )
        path = save_terminal_frame(
            run_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step02.png',
            title='generate_monthly_report.py',
        )
        self.add_step(
            'Generate and Email Reports',
            'The script generates a PDF for each active investor and optionally emails '
            'them. Reports are saved to data/reports/ with a YYYY-MM prefix.',
            str(path),
        )


if __name__ == '__main__':
    MonthlyReportTutorial(TUTORIAL_ID).run()
