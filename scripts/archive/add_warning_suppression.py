"""
Add Warning Suppression to Python Scripts

Adds these two lines to the top of all Python scripts in scripts/ folder:
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)

This will suppress DeprecationWarning messages for cleaner output.
"""

import os
from pathlib import Path


def add_warning_suppression(script_path):
    """Add warning suppression to a Python script"""
    
    # Read the file
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already has warning suppression
    if 'warnings.filterwarnings' in content:
        return False  # Already has it
    
    # Find where to insert (after docstring, before imports)
    lines = content.split('\n')
    
    # Find first import or first non-comment/docstring line
    insert_index = 0
    in_docstring = False
    docstring_char = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Check for docstring start
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = True
                docstring_char = stripped[:3]
                # Check if docstring ends on same line
                if stripped.count(docstring_char) >= 2:
                    in_docstring = False
                    insert_index = i + 1
                continue
        else:
            # Check for docstring end
            if docstring_char in stripped:
                in_docstring = False
                insert_index = i + 1
                continue
        
        # If we're past docstring and hit an import or code, insert before it
        if not in_docstring and stripped and not stripped.startswith('#'):
            insert_index = i
            break
    
    # Insert warning suppression
    suppression_code = [
        'import warnings',
        "warnings.filterwarnings('ignore', category=DeprecationWarning)",
        ''
    ]
    
    # Insert at the appropriate location
    new_lines = lines[:insert_index] + suppression_code + lines[insert_index:]
    
    # Write back
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    return True


def main():
    scripts_dir = Path(__file__).parent.parent / 'scripts'
    
    if not scripts_dir.exists():
        print(f"❌ Scripts directory not found: {scripts_dir}")
        return
    
    print("=" * 70)
    print("ADD WARNING SUPPRESSION TO SCRIPTS")
    print("=" * 70)
    print()
    print("This will add these lines to the top of all Python scripts:")
    print("  import warnings")
    print("  warnings.filterwarnings('ignore', category=DeprecationWarning)")
    print()
    
    confirm = input("Proceed? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    print()
    print("Processing scripts...")
    print()
    
    updated = []
    skipped = []
    
    # Process all .py files in scripts directory
    for script_path in scripts_dir.glob('*.py'):
        if script_path.name == '__init__.py':
            continue
        
        print(f"  {script_path.name}...", end=' ')
        
        try:
            if add_warning_suppression(script_path):
                print("✅ Updated")
                updated.append(script_path.name)
            else:
                print("⏭️  Skipped (already has suppression)")
                skipped.append(script_path.name)
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print(f"Updated: {len(updated)}")
    print(f"Skipped: {len(skipped)}")
    print()
    
    if updated:
        print("Updated scripts:")
        for name in updated:
            print(f"  • {name}")
    
    print()
    print("✅ Done! Scripts will now suppress DeprecationWarnings.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
