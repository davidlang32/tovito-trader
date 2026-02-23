"""
Tutorial: Backing Up the Database
===================================

Records the database backup process.
This is non-interactive (no args needed).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'admin_backup'


class BackupTutorial(BaseRecorder):
    """Records the database backup workflow."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Overview and execution
        run_text = (
            "# Database Backup\n"
            "#\n"
            "# CRITICAL: Always back up before any database modifications.\n"
            "# Backups are timestamped and stored in data/backups/\n"
            "\n"
            "$ python scripts/utilities/backup_database.py\n"
            "\n"
            "=== Database Backup ===\n"
            "\n"
            "Source: data/tovito.db (2.4 MB)\n"
            "Backup: data/backups/tovito_20260105_160500.db\n"
            "\n"
            "SUCCESS: Database backed up.\n"
            "  Size: 2.4 MB\n"
            "  Timestamp: 2026-01-05 16:05:00\n"
            "\n"
            "# List existing backups:\n"
            "$ python scripts/utilities/backup_database.py --list\n"
            "\n"
            "  data/backups/tovito_20260105_160500.db  (2.4 MB)\n"
            "  data/backups/tovito_20260104_160500.db  (2.4 MB)\n"
            "  data/backups/tovito_20260103_160500.db  (2.3 MB)\n"
            "  Total: 3 backups (7.1 MB)"
        )
        path = save_terminal_frame(
            run_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Database Backup',
        )
        self.add_step(
            'Create a Database Backup',
            'Run backup_database.py to create a timestamped copy. '
            'Use --list to see existing backups. Always back up before schema changes or data modifications.',
            str(path),
        )


if __name__ == '__main__':
    BackupTutorial(TUTORIAL_ID).run()
