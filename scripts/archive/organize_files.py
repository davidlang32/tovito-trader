"""
Tovito Trader - Smart File Organizer
Automatically organizes files based on extension and naming patterns

This script will:
- Move all .md files to docs/ (organized by type)
- Move all .py files to scripts/ (except run.py)
- Move all .xlsx/.xlsm files to excel/
- Keep essential files in root (.env, run.py, README.md, etc.)

Usage:
    python organize_files_smart.py
"""

import os
import shutil
from pathlib import Path
import re

class SmartOrganizer:
    def __init__(self, root_path=None):
        self.root = Path(root_path) if root_path else Path.cwd()
        self.moved_count = 0
        self.skipped_count = 0
        
        # Files that should ALWAYS stay in root
        self.keep_in_root = {
            '.env',
            'run.py',
            'README.md',
            'setup.py',
            'requirements.txt',
            'requirements-test.txt',
            '.gitignore',
            'organize_files_smart.py',  # Don't move this script!
        }
        
        # Directories to ignore
        self.ignore_dirs = {
            'data', 'scripts', 'logs', 'docs', 'excel', 'archive',
            'src', 'tests', 'reports', '__pycache__', '.git'
        }
    
    def create_directory_structure(self):
        """Create the standard directory structure"""
        dirs = [
            'docs/guides',
            'docs/quickstart',
            'docs/reference',
            'excel',
            'archive'
        ]
        
        for dir_path in dirs:
            (self.root / dir_path).mkdir(parents=True, exist_ok=True)
    
    def categorize_markdown_file(self, filename):
        """Determine which docs subfolder a .md file belongs to"""
        filename_lower = filename.lower()
        
        # Comprehensive guides (detailed how-to)
        guide_keywords = [
            'guide', 'workflow', 'migration', 'testing', 'integration',
            'polish', 'summary', 'complete', 'deployment'
        ]
        
        # Quick start / completion summaries
        quickstart_keywords = [
            'option_', 'complete.md', 'quick_start', 'quickstart'
        ]
        
        # Reference documentation
        reference_keywords = [
            'reference', 'tax', 'investor', 'handoff', 'design',
            'roadmap', 'backup', 'scheduler', 'structure', 'tree'
        ]
        
        # Check for quickstart first (more specific)
        if any(keyword in filename_lower for keyword in quickstart_keywords):
            return 'docs/quickstart'
        
        # Then guides
        if any(keyword in filename_lower for keyword in guide_keywords):
            return 'docs/guides'
        
        # Then reference
        if any(keyword in filename_lower for keyword in reference_keywords):
            return 'docs/reference'
        
        # Default to reference for unknown .md files
        return 'docs/reference'
    
    def should_organize_file(self, filepath):
        """Determine if a file should be organized"""
        # Don't organize files already in subdirectories
        if filepath.parent != self.root:
            return False
        
        # Don't organize files in the keep_in_root list
        if filepath.name in self.keep_in_root:
            return False
        
        # Don't organize directories
        if filepath.is_dir():
            return False
        
        return True
    
    def get_destination(self, filepath):
        """Determine where a file should go"""
        filename = filepath.name
        ext = filepath.suffix.lower()
        
        # Python scripts (except those in keep_in_root)
        if ext == '.py':
            return 'scripts'
        
        # Markdown documentation
        if ext == '.md':
            return self.categorize_markdown_file(filename)
        
        # Excel files
        if ext in ['.xlsx', '.xlsm', '.xls']:
            return 'excel'
        
        # Text files (could be reference docs)
        if ext == '.txt' and filename not in self.keep_in_root:
            return 'docs/reference'
        
        # Batch files
        if ext == '.bat':
            return 'scripts'
        
        # Unknown files - don't move them
        return None
    
    def organize_files(self, dry_run=True):
        """Organize all files in root directory"""
        files_to_move = []
        
        # Find all files in root directory
        for item in self.root.iterdir():
            if self.should_organize_file(item) and item.is_file():
                destination = self.get_destination(item)
                if destination:
                    files_to_move.append((item, destination))
        
        if not files_to_move:
            print("ℹ️  No files to organize (everything is already in place)")
            return
        
        # Show what will be done
        print(f"\n{'DRY RUN - ' if dry_run else ''}Files to organize:")
        print("-" * 70)
        
        for source, dest_dir in files_to_move:
            dest = self.root / dest_dir / source.name
            
            if dry_run:
                print(f"  📄 {source.name}")
                print(f"     → {dest_dir}/")
            else:
                try:
                    # Create destination directory if needed
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Move the file
                    shutil.move(str(source), str(dest))
                    print(f"  ✅ Moved: {source.name}")
                    print(f"     → {dest_dir}/")
                    self.moved_count += 1
                except Exception as e:
                    print(f"  ❌ Error moving {source.name}: {e}")
                    self.skipped_count += 1
        
        print()
        if not dry_run:
            print(f"✅ Moved {self.moved_count} file(s)")
            if self.skipped_count > 0:
                print(f"⚠️  Skipped {self.skipped_count} file(s)")

def main():
    print("=" * 70)
    print("TOVITO TRADER - SMART FILE ORGANIZER")
    print("=" * 70)
    print()
    
    organizer = SmartOrganizer()
    
    print(f"📍 Working directory: {organizer.root}")
    print()
    
    print("This script will automatically organize files by type:")
    print("  • .md files → docs/ (categorized by content)")
    print("  • .py files → scripts/ (except run.py)")
    print("  • .xlsx/.xlsm → excel/")
    print("  • Essential files stay in root (.env, run.py, README.md)")
    print()
    
    # Step 1: Create directory structure
    print("STEP 1: Creating directory structure...")
    print("-" * 70)
    organizer.create_directory_structure()
    print("✅ Directory structure ready")
    print()
    
    # Step 2: Show what will be organized (dry run)
    print("STEP 2: Analyzing files...")
    print("-" * 70)
    organizer.organize_files(dry_run=True)
    
    # Step 3: Ask for confirmation
    print("=" * 70)
    response = input("Proceed with organizing these files? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Cancelled. No files were moved.")
        return
    
    # Step 4: Actually organize the files
    print()
    print("=" * 70)
    print("ORGANIZING FILES...")
    print("=" * 70)
    print()
    
    organizer.organize_files(dry_run=False)
    
    # Step 5: Summary
    print()
    print("=" * 70)
    print("✅ ORGANIZATION COMPLETE!")
    print("=" * 70)
    print()
    print("📁 Your organized structure:")
    print("   tovito-trader/")
    print("   ├── docs/")
    print("   │   ├── guides/      (comprehensive how-to guides)")
    print("   │   ├── quickstart/  (quick 5-min overviews)")
    print("   │   └── reference/   (reference documentation)")
    print("   ├── scripts/         (Python scripts)")
    print("   ├── excel/           (Excel files)")
    print("   ├── data/            (database & backups)")
    print("   ├── logs/            (log files)")
    print("   └── reports/         (generated reports)")
    print()
    print("🎯 Root directory now contains only:")
    print("   • .env (configuration)")
    print("   • run.py (main CLI)")
    print("   • README.md (overview)")
    print("   • setup.py (Python package config)")
    print("   • requirements.txt (dependencies)")
    print()
    print("💡 In the future, just run this script again to organize new files!")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")