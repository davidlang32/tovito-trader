"""
Database Backup Script
======================

Creates timestamped backup of the Tovito database.
Keeps all backups indefinitely (no automatic cleanup).

Usage:
    python scripts/backup_database.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import shutil
from datetime import datetime
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)


class DatabaseBackup:
    """Handle database backups"""
    
    def __init__(self):
        self.db_path = 'data/tovito.db'
        self.backup_dir = 'data/backups'
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self) -> dict:
        """
        Create a timestamped backup of the database
        
        Returns:
            dict: Result with status, backup_path, and size
        """
        try:
            # Check if database exists
            if not os.path.exists(self.db_path):
                return {
                    'status': 'error',
                    'error': f'Database not found: {self.db_path}'
                }
            
            # Get database size
            db_size = os.path.getsize(self.db_path)
            
            # Create timestamp: YYYY-MM-DD_HHMMSS
            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            
            # Create backup filename
            backup_filename = f'tovito_backup_{timestamp}.db'
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Copy database file
            print(f"💾 Creating backup...")
            print(f"   Source: {self.db_path}")
            print(f"   Destination: {backup_path}")
            
            shutil.copy2(self.db_path, backup_path)
            
            # Verify backup was created
            if not os.path.exists(backup_path):
                return {
                    'status': 'error',
                    'error': 'Backup file was not created'
                }
            
            # Get backup size
            backup_size = os.path.getsize(backup_path)
            
            # Verify sizes match
            if backup_size != db_size:
                return {
                    'status': 'error',
                    'error': f'Size mismatch: original={db_size}, backup={backup_size}'
                }
            
            print(f"✅ Backup created successfully!")
            print(f"   Size: {backup_size:,} bytes")
            print(f"   Location: {backup_path}")
            
            logger.info("Database backup created", 
                       backup_file=backup_filename,
                       size_bytes=backup_size)
            
            return {
                'status': 'success',
                'backup_path': backup_path,
                'backup_filename': backup_filename,
                'size_bytes': backup_size,
                'timestamp': timestamp
            }
        
        except Exception as e:
            error_msg = f"Backup failed: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error("Database backup failed", error=str(e))
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def list_backups(self):
        """List all existing backups"""
        try:
            backups = []
            
            if not os.path.exists(self.backup_dir):
                return backups
            
            for filename in os.listdir(self.backup_dir):
                if filename.endswith('.db'):
                    filepath = os.path.join(self.backup_dir, filename)
                    size = os.path.getsize(filepath)
                    modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    backups.append({
                        'filename': filename,
                        'path': filepath,
                        'size_bytes': size,
                        'modified': modified
                    })
            
            # Sort by modified date (newest first)
            backups.sort(key=lambda x: x['modified'], reverse=True)
            
            return backups
        
        except Exception as e:
            logger.error("Failed to list backups", error=str(e))
            return []
    
    def show_backup_summary(self):
        """Display summary of all backups"""
        backups = self.list_backups()
        
        if not backups:
            print("\n📋 No backups found")
            return
        
        print(f"\n{'='*70}")
        print(f"DATABASE BACKUPS")
        print(f"{'='*70}")
        print(f"Location: {self.backup_dir}")
        print(f"Total backups: {len(backups)}")
        print(f"{'='*70}\n")
        
        total_size = 0
        
        for backup in backups:
            size_kb = backup['size_bytes'] / 1024
            total_size += backup['size_bytes']
            
            print(f"📁 {backup['filename']}")
            print(f"   Date: {backup['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Size: {size_kb:.1f} KB")
            print()
        
        print(f"{'='*70}")
        total_mb = total_size / (1024 * 1024)
        print(f"Total storage: {total_mb:.2f} MB")
        print(f"{'='*70}\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backup Tovito database')
    parser.add_argument('--list', action='store_true', help='List all backups')
    parser.add_argument('--summary', action='store_true', help='Show backup summary')
    
    args = parser.parse_args()
    
    backup_manager = DatabaseBackup()
    
    if args.list or args.summary:
        backup_manager.show_backup_summary()
    else:
        # Create backup
        result = backup_manager.create_backup()
        
        if result['status'] == 'success':
            print("\n✅ Backup complete!")
            sys.exit(0)
        else:
            print(f"\n❌ Backup failed: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
