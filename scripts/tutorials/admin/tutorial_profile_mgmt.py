"""
Tutorial: Managing Investor Profiles
======================================

Records the profile management workflow using manage_profile.py.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'admin_profile_mgmt'


class ProfileMgmtTutorial(BaseRecorder):
    """Records the investor profile management workflow."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Launch
        launch_text = (
            "# Managing Investor Profiles\n"
            "#\n"
            "# View and edit investor profile information including:\n"
            "#   - Contact information (name, address, phone, email)\n"
            "#   - Personal information (DOB, marital status)\n"
            "#   - Employment information\n"
            "#   - Sensitive PII (SSN, bank details) - encrypted at rest\n"
            "#   - Accreditation status\n"
            "#   - Preferences\n"
            "\n"
            "$ python scripts/investor/manage_profile.py --investor 20260101-01A"
        )
        path = save_terminal_frame(
            launch_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Profile Management',
        )
        self.add_step(
            'Launch Profile Manager',
            'Run manage_profile.py with --investor flag, or omit it to select from a list.',
            str(path),
        )

        # Profile view
        view_text = (
            "$ python scripts/investor/manage_profile.py --investor 20260101-01A\n"
            "\n"
            "=== Investor Profile: Alpha Investor ===\n"
            "\n"
            "Contact Information:\n"
            "  Name: Alpha Investor\n"
            "  Address: 123 Main St, New York, NY 10001\n"
            "  Phone: (555) 123-4567\n"
            "  Email: alpha@test.com\n"
            "\n"
            "Personal Information:\n"
            "  Date of Birth: ***-**-1990 (encrypted)\n"
            "  Marital Status: Single\n"
            "  Citizenship: US\n"
            "\n"
            "Sensitive (Encrypted):\n"
            "  SSN: ***-**-**** (stored encrypted)\n"
            "  Bank Routing: ******** (stored encrypted)\n"
            "  Bank Account: ******** (stored encrypted)\n"
            "\n"
            "Actions:\n"
            "  1. Edit contact info\n"
            "  2. Edit personal info\n"
            "  3. Edit employment info\n"
            "  4. Edit sensitive info\n"
            "  5. Edit accreditation\n"
            "  6. Edit preferences\n"
            "  7. View full profile (decrypted)\n"
            "  q. Quit\n"
            "\n"
            "Select action: "
        )
        path = save_terminal_frame(
            view_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step02.png',
            title='manage_profile.py',
        )
        self.add_step(
            'View Current Profile',
            'The profile manager shows all sections. Sensitive fields (SSN, bank details) '
            'are shown masked. Select an action to edit a section.',
            str(path),
        )

        # Edit example
        edit_text = (
            "Select action: 1\n"
            "\n"
            "=== Edit Contact Information ===\n"
            "Press Enter to keep current value.\n"
            "\n"
            "  Name [Alpha Investor]: \n"
            "  Address [123 Main St, New York, NY 10001]: 456 Oak Ave, Boston, MA 02101\n"
            "  Phone [(555) 123-4567]: \n"
            "  Email [alpha@test.com]: \n"
            "\n"
            "SUCCESS: Contact information updated.\n"
            "  Address changed: 123 Main St -> 456 Oak Ave, Boston, MA 02101\n"
            "\n"
            "Select action: q\n"
            "Profile management complete."
        )
        path = save_terminal_frame(
            edit_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step03.png',
            title='manage_profile.py',
        )
        self.add_step(
            'Edit Profile Fields',
            'Select a section to edit. Press Enter to keep current values, or type new values. '
            'Changes are saved immediately. Enter "q" to quit.',
            str(path),
        )


if __name__ == '__main__':
    ProfileMgmtTutorial(TUTORIAL_ID).run()
