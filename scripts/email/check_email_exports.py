"""
Check what's exported from email_service module
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("EMAIL SERVICE MODULE INSPECTION")
print("=" * 70)
print()

try:
    import src.automation.email_service as email_module
    
    print("✅ Module imported successfully")
    print()
    print("Available functions and attributes:")
    print()
    
    for item in dir(email_module):
        if not item.startswith('_'):
            obj = getattr(email_module, item)
            obj_type = type(obj).__name__
            print(f"  • {item} ({obj_type})")
    
    print()
    print("=" * 70)
    print()
    
    # Check specifically for send functions
    send_functions = [item for item in dir(email_module) if 'send' in item.lower()]
    
    if send_functions:
        print("Functions with 'send' in the name:")
        for func in send_functions:
            print(f"  • {func}")
    
    print()
    
except Exception as e:
    print(f"❌ Error importing: {e}")
    import traceback
    traceback.print_exc()
