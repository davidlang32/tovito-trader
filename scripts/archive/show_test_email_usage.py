"""
Show how test_email.py actually imports and calls email functions
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
test_email_path = project_root / 'scripts' / 'test_email.py'

print("=" * 70)
print("HOW TEST_EMAIL.PY USES EMAIL SERVICE")
print("=" * 70)
print()

if not test_email_path.exists():
    print(f"❌ test_email.py not found at {test_email_path}")
else:
    print(f"Reading: {test_email_path}")
    print()
    
    with open(test_email_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print("IMPORT STATEMENTS:")
    print("-" * 70)
    for i, line in enumerate(lines, 1):
        if 'import' in line and ('email' in line.lower() or 'automation' in line.lower()):
            print(f"{i:3}: {line.rstrip()}")
    
    print()
    print("FUNCTION CALLS:")
    print("-" * 70)
    for i, line in enumerate(lines, 1):
        if 'send' in line.lower() and '(' in line:
            print(f"{i:3}: {line.rstrip()}")
    
    print()
    print("=" * 70)
