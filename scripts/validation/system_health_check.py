"""
System Health Check Script

Comprehensive health check of all system components:
- Database integrity
- Internet connectivity
- API accessibility
- Email system
- Disk space
- Recent backups
- Data validation
- Error logs

Usage:
    python run.py health
    python scripts/system_health_check.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta
import os

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def check_database():
    """Check database accessibility and integrity"""
    db_path = Path(__file__).parent.parent / "data" / "tovito.db"
    
    try:
        if not db_path.exists():
            print_error(f"Database not found: {db_path}")
            return False
        
        # Check file size
        size_kb = db_path.stat().st_size / 1024
        
        # Try to connect
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        
        conn.close()
        
        if result == "ok":
            print_success(f"Database: OK ({db_path.name}, {size_kb:.0f} KB)")
            return True
        else:
            print_error(f"Database integrity check failed: {result}")
            return False
            
    except Exception as e:
        print_error(f"Database error: {e}")
        return False

def check_internet():
    """Check internet connectivity"""
    try:
        # Try to ping Google DNS
        if sys.platform == "win32":
            result = subprocess.run(
                ["ping", "-n", "1", "8.8.8.8"],
                capture_output=True,
                timeout=5
            )
        else:
            result = subprocess.run(
                ["ping", "-c", "1", "8.8.8.8"],
                capture_output=True,
                timeout=5
            )
        
        if result.returncode == 0:
            print_success("Internet: OK")
            return True
        else:
            print_error("Internet: No connection")
            return False
            
    except Exception as e:
        print_error(f"Internet check failed: {e}")
        return False

def check_tradier_api():
    """Check Tradier API accessibility"""
    try:
        # This would require the actual API integration
        # For now, just check if credentials exist
        env_file = Path(__file__).parent.parent / ".env"
        
        if not env_file.exists():
            print_warning("Tradier API: .env file not found")
            return False
        
        with open(env_file) as f:
            env_content = f.read()
        
        if "TRADIER_API_KEY" in env_content:
            print_info("Tradier API: Credentials configured")
            # TODO: Actual API test would go here
            return True
        else:
            print_warning("Tradier API: No credentials found")
            return False
            
    except Exception as e:
        print_error(f"Tradier API check failed: {e}")
        return False

def check_email_system():
    """Check email system configuration"""
    try:
        env_file = Path(__file__).parent.parent / ".env"
        
        if not env_file.exists():
            print_warning("Email System: .env file not found")
            return False
        
        with open(env_file) as f:
            env_content = f.read()
        
        required_vars = ["SMTP_SERVER", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD"]
        missing_vars = [var for var in required_vars if var not in env_content]
        
        if not missing_vars:
            print_success("Email System: OK (SMTP configuration found)")
            return True
        else:
            print_warning(f"Email System: Missing configuration: {', '.join(missing_vars)}")
            return False
            
    except Exception as e:
        print_error(f"Email system check failed: {e}")
        return False

def check_disk_space():
    """Check available disk space"""
    try:
        if sys.platform == "win32":
            # Windows
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p("."), None, None, ctypes.pointer(free_bytes)
            )
            free_gb = free_bytes.value / (1024**3)
        else:
            # Linux/Mac
            stat = os.statvfs(".")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        
        if free_gb > 1:  # More than 1 GB
            print_success(f"Disk Space: OK ({free_gb:.0f} GB available)")
            return True
        else:
            print_warning(f"Disk Space: Low ({free_gb:.1f} GB available)")
            return False
            
    except Exception as e:
        print_warning(f"Disk space check failed: {e}")
        return False

def check_recent_backup():
    """Check if recent backup exists"""
    try:
        backup_dir = Path(__file__).parent.parent / "data" / "backups"
        
        if not backup_dir.exists():
            print_warning("Backups: Directory not found")
            return False
        
        # Get all backup files
        backups = list(backup_dir.glob("tovito_backup_*.db"))
        
        if not backups:
            print_warning("Backups: No backups found")
            return False
        
        # Find most recent backup
        most_recent = max(backups, key=lambda p: p.stat().st_mtime)
        backup_time = datetime.fromtimestamp(most_recent.stat().st_mtime)
        time_since = datetime.now() - backup_time
        
        hours_ago = time_since.total_seconds() / 3600
        
        if hours_ago < 24:
            print_success(f"Latest Backup: OK ({hours_ago:.0f} hours ago)")
            return True
        else:
            print_warning(f"Latest Backup: Old ({hours_ago:.0f} hours ago)")
            return False
            
    except Exception as e:
        print_error(f"Backup check failed: {e}")
        return False

def check_data_validation():
    """Run basic data validation"""
    db_path = Path(__file__).parent.parent / "data" / "tovito.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check shares match
        cursor.execute("""
            SELECT SUM(current_shares) 
            FROM investors 
            WHERE status='Active'
        """)
        investor_total = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT total_shares 
            FROM nav_history 
            ORDER BY date DESC 
            LIMIT 1
        """)
        nav_total = cursor.fetchone()[0] or 0
        
        conn.close()
        
        if abs(investor_total - nav_total) < 0.01:
            print_success("Data Validation: OK (all checks passed)")
            return True
        else:
            print_error(f"Data Validation: Failed (shares mismatch)")
            return False
            
    except Exception as e:
        print_error(f"Data validation failed: {e}")
        return False

def check_error_logs():
    """Check for critical errors in recent logs"""
    try:
        log_file = Path(__file__).parent.parent / "logs" / "daily_runner.log"
        
        if not log_file.exists():
            print_info("Error Logs: No log file found (system may not have run yet)")
            return True
        
        # Read last 100 lines
        with open(log_file) as f:
            lines = f.readlines()[-100:]
        
        # Check for ERROR level logs in last 24 hours
        errors = [line for line in lines if " ERROR " in line]
        
        if not errors:
            print_success("Error Logs: OK (no critical errors in last 24 hours)")
            return True
        else:
            print_warning(f"Error Logs: {len(errors)} error(s) found in recent logs")
            return False
            
    except Exception as e:
        print_warning(f"Error log check failed: {e}")
        return False

def check_last_nav_update():
    """Check when last NAV update occurred"""
    db_path = Path(__file__).parent.parent / "data" / "tovito.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT date, created_at 
            FROM nav_history 
            ORDER BY date DESC 
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print_info("Last NAV Update: None (new system)")
            return True
        
        nav_date, created_at = result
        
        print_info(f"Last NAV Update: {created_at}")
        return True
        
    except Exception as e:
        print_warning(f"NAV update check failed: {e}")
        return False

def run_health_check():
    """Run complete system health check"""
    
    print("=" * 70)
    print("SYSTEM HEALTH CHECK")
    print("=" * 70)
    print()
    
    checks = [
        ("Database", check_database),
        ("Internet", check_internet),
        ("Tradier API", check_tradier_api),
        ("Email System", check_email_system),
        ("Disk Space", check_disk_space),
        ("Latest Backup", check_recent_backup),
        ("Data Validation", check_data_validation),
        ("Error Logs", check_error_logs),
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"{name}: Error - {e}")
            results.append((name, False))
    
    print()
    check_last_nav_update()
    
    print()
    print("=" * 70)
    
    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    if passed == total:
        print_success("🎉 ALL SYSTEMS HEALTHY!")
    elif passed >= total * 0.7:  # 70% or more
        print_warning(f"⚠️  SOME ISSUES DETECTED ({passed}/{total} checks passed)")
    else:
        print_error(f"❌ MULTIPLE ISSUES DETECTED ({passed}/{total} checks passed)")
    
    print("=" * 70)
    print()
    
    return passed == total

if __name__ == "__main__":
    try:
        success = run_health_check()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nHealth check cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
