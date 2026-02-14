"""
Organize Tovito Trader Scripts into Logical Folder Structure

This script will organize your scripts/ folder into a logical structure:
- 01_daily/
- 02_investor_management/
- 03_reporting/
- 04_validation/
- 05_trading_analysis/
- 06_utilities/
- archive/

Usage:
    python organize_scripts.py --preview    # Show what will be moved
    python organize_scripts.py --execute    # Actually move the files
"""

import os
import shutil
from pathlib import Path
import argparse

# Define folder structure and file mappings
FOLDER_STRUCTURE = {
    '01_daily': [
        'daily_runner.py',
        'daily_nav_enhanced.py'
    ],
    '02_investor_management': [
        'process_contribution.py',
        'process_withdrawal.py',
        'process_withdrawal_enhanced.py',
        'close_investor_account.py',
        'request_withdrawal.py',
        'submit_withdrawal_request.py'
    ],
    '03_reporting': [
        'generate_monthly_report.py',
        'export_transactions_excel.py',
        'email_adapter.py',
        'email_service.py'
    ],
    '04_validation': [
        'validate_with_ach.py',
        'validate_comprehensive.py',
        'validate_reconciliation.py',
        'nav_helper.py'
    ],
    '05_trading_analysis': [
        'import_tradier_history.py',
        'query_trades.py',
        'trades_table_schema.py',
        'sync_tradier_transactions.py'
    ],
    '06_utilities': [
        'list_investors.py',
        'backup_database.py',
        'system_health_check.py',
        'check_database_schema.py',
        'check_email_config.py',
        'update_investor_emails.py',
        'view_investor_emails.py',
        'view_logs.py',
        'view_positions.py',
        'reverse_transaction.py'
    ],
    'archive': [
        'process_contribution_old.py',
        'process_withdrawal_old.py',
        'process_contribution_historical.py',
        'process_withdrawal_historical.py',
        'validate.py',
        'sync_tradier_deposits.py',
        'populate_missing_transactions.py',
        'quick_fix_nav.py',
        'fix_january1_nav.py',
        'fix_jan21_and_contribute.py',
        'check_january1_nav.py',
        'add_warning_suppression.py',
        'find_email_service.py',
        'check_email_exports.py',
        'show_test_email_usage.py'
    ]
}


def get_scripts_path():
    """Get the scripts directory path"""
    return Path(__file__).parent.parent / 'scripts'


def preview_organization():
    """Preview what will be moved"""
    scripts_path = get_scripts_path()
    
    if not scripts_path.exists():
        print(f"❌ Scripts directory not found: {scripts_path}")
        return
    
    print("=" * 80)
    print("PREVIEW: Script Organization Plan")
    print("=" * 80)
    print()
    
    # Check what exists
    existing_files = [f.name for f in scripts_path.iterdir() if f.is_file() and f.suffix == '.py']
    
    total_files = 0
    moved_files = 0
    
    for folder, files in sorted(FOLDER_STRUCTURE.items()):
        print(f"📁 {folder}/")
        print("-" * 80)
        
        files_to_move = [f for f in files if f in existing_files]
        
        if files_to_move:
            for file in files_to_move:
                print(f"  ✅ {file}")
                moved_files += 1
        else:
            print(f"  (no files to move)")
        
        print()
    
    # Check for unmapped files
    all_mapped_files = set()
    for files in FOLDER_STRUCTURE.values():
        all_mapped_files.update(files)
    
    unmapped_files = [f for f in existing_files if f not in all_mapped_files and f != 'organize_scripts.py']
    
    if unmapped_files:
        print("⚠️  UNMAPPED FILES (will stay in scripts/):")
        print("-" * 80)
        for file in sorted(unmapped_files):
            print(f"  {file}")
        print()
    
    total_files = len(existing_files)
    
    print("=" * 80)
    print(f"Total files found: {total_files}")
    print(f"Files to organize: {moved_files}")
    print(f"Files staying in root: {len(unmapped_files) + 1}")  # +1 for organize_scripts.py
    print("=" * 80)
    print()
    print("💡 To execute this organization, run:")
    print("   python organize_scripts.py --execute")
    print()


def execute_organization():
    """Actually move the files"""
    scripts_path = get_scripts_path()
    
    if not scripts_path.exists():
        print(f"❌ Scripts directory not found: {scripts_path}")
        return
    
    print("=" * 80)
    print("EXECUTING: Script Organization")
    print("=" * 80)
    print()
    
    # Create folders
    print("📁 Creating folders...")
    for folder in FOLDER_STRUCTURE.keys():
        folder_path = scripts_path / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True)
            print(f"  ✅ Created: {folder}/")
        else:
            print(f"  ℹ️  Exists: {folder}/")
    print()
    
    # Move files
    print("📦 Moving files...")
    moved_count = 0
    skipped_count = 0
    error_count = 0
    
    for folder, files in FOLDER_STRUCTURE.items():
        for file in files:
            source = scripts_path / file
            dest = scripts_path / folder / file
            
            if source.exists():
                try:
                    shutil.move(str(source), str(dest))
                    print(f"  ✅ Moved: {file} → {folder}/")
                    moved_count += 1
                except Exception as e:
                    print(f"  ❌ Error moving {file}: {e}")
                    error_count += 1
            else:
                skipped_count += 1
    
    print()
    print("=" * 80)
    print("ORGANIZATION COMPLETE")
    print("=" * 80)
    print(f"Files moved: {moved_count}")
    print(f"Files skipped (not found): {skipped_count}")
    print(f"Errors: {error_count}")
    print()
    
    if error_count == 0:
        print("✅ All files organized successfully!")
    else:
        print("⚠️  Some errors occurred - check messages above")
    
    print()
    print("💡 Your scripts are now organized into logical folders!")
    print("   See SCRIPT_ORGANIZATION_GUIDE.md for the complete reference")


def main():
    parser = argparse.ArgumentParser(description='Organize Tovito Trader scripts into folders')
    parser.add_argument('--preview', action='store_true', help='Preview what will be moved')
    parser.add_argument('--execute', action='store_true', help='Actually move the files')
    
    args = parser.parse_args()
    
    if not args.preview and not args.execute:
        print("❌ Must specify either --preview or --execute")
        print()
        print("Usage:")
        print("  python organize_scripts.py --preview    # Show what will be moved")
        print("  python organize_scripts.py --execute    # Actually move the files")
        return
    
    if args.preview:
        preview_organization()
    
    if args.execute:
        # Ask for confirmation
        print("⚠️  WARNING: This will reorganize your scripts folder!")
        print()
        response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
        
        if response in ['yes', 'y']:
            print()
            execute_organization()
        else:
            print("❌ Organization cancelled")


if __name__ == "__main__":
    main()
