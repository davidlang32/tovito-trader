"""
Find email_service location

This helps us fix the import in monthly report generator
"""

import os
import sys
from pathlib import Path

print("=" * 70)
print("FINDING EMAIL SERVICE")
print("=" * 70)
print()

# Check possible locations
project_root = Path(__file__).parent.parent
possible_locations = [
    project_root / 'src' / 'automation' / 'email_service.py',
    project_root / 'src' / 'email_service.py',
    project_root / 'email_service.py',
    project_root / 'scripts' / 'email_service.py',
]

print("Checking possible locations:")
print()

found = False
for loc in possible_locations:
    exists = loc.exists()
    status = "✅ FOUND" if exists else "❌ Not here"
    print(f"{status}: {loc}")
    if exists:
        found = True
        actual_location = loc

print()

if found:
    print(f"✅ Email service found at: {actual_location}")
    print()
    print("Relative to project root:")
    print(f"   {actual_location.relative_to(project_root)}")
    print()
    
    # Show how test_email.py imports it
    test_email_path = project_root / 'scripts' / 'test_email.py'
    if test_email_path.exists():
        print("How test_email.py imports it:")
        with open(test_email_path, 'r') as f:
            for line in f:
                if 'import' in line and ('email' in line.lower() or 'send_email' in line):
                    print(f"   {line.strip()}")
else:
    print("❌ Email service not found!")
    print()
    print("It should be at one of the locations above.")

print()
print("=" * 70)
