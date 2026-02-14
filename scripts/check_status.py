"""
TOVITO TRADER - System Status Check
Quick overview of system health - run anytime to see status
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path("C:/tovito-trader")
DB_PATH = PROJECT_DIR / "data" / "tovito.db"
HEARTBEAT_FILE = PROJECT_DIR / "logs" / "daily_nav_heartbeat.txt"

def check_status():
    print("=" * 60)
    print("TOVITO TRADER - SYSTEM STATUS")
    print("=" * 60)
    print(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    issues = []
    
    # Check 1: Database
    print("📊 DATABASE")
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            # Latest NAV
            cursor.execute("SELECT date, nav_per_share, total_portfolio_value FROM daily_nav ORDER BY date DESC LIMIT 1")
            nav = cursor.fetchone()
            if nav:
                nav_date = datetime.strptime(nav[0], '%Y-%m-%d')
                days_old = (datetime.now() - nav_date).days
                print(f"   Last NAV: {nav[0]} (${nav[1]:.4f})")
                print(f"   Portfolio: ${nav[2]:,.2f}")
                if days_old > 1 and datetime.now().weekday() < 5:  # Weekday
                    issues.append(f"NAV is {days_old} days old!")
                    print(f"   ⚠️  NAV is {days_old} days old!")
                else:
                    print(f"   ✓ NAV age: {days_old} day(s)")
            
            # Investor count
            cursor.execute("SELECT COUNT(*) FROM investors WHERE status = 'Active'")
            inv_count = cursor.fetchone()[0]
            print(f"   Active investors: {inv_count}")
            
            conn.close()
        except Exception as e:
            print(f"   ❌ Error: {e}")
            issues.append(f"Database error: {e}")
    else:
        print(f"   ❌ Database not found!")
        issues.append("Database not found")
    
    print()
    
    # Check 2: Heartbeat
    print("💓 HEARTBEAT")
    if HEARTBEAT_FILE.exists():
        mtime = datetime.fromtimestamp(HEARTBEAT_FILE.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        print(f"   Last update: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Age: {age_hours:.1f} hours")
        if age_hours > 24:
            issues.append(f"Heartbeat is {age_hours:.0f} hours old!")
            print(f"   ⚠️  Heartbeat is stale!")
        else:
            print(f"   ✓ Heartbeat is fresh")
        
        # Show content
        with open(HEARTBEAT_FILE, encoding='utf-8') as f:
            content = f.read().strip()
        for line in content.split('\n'):
            print(f"   {line}")
    else:
        print("   ⚠️  No heartbeat file (first run?)")
    
    print()
    
    # Check 3: Log files
    print("📝 RECENT LOGS")
    log_files = [
        ("daily_runner.log", "Daily NAV"),
        ("watchdog.log", "Watchdog"),
        ("task_scheduler.log", "Task Scheduler"),
    ]
    
    for log_name, label in log_files:
        log_path = PROJECT_DIR / "logs" / log_name
        if log_path.exists():
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            age = datetime.now() - mtime
            print(f"   {label}: Updated {age.days}d {age.seconds//3600}h ago")
        else:
            print(f"   {label}: Not found")
    
    print()
    
    # Check 4: Environment
    print("🔧 CONFIGURATION")
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        from dotenv import dotenv_values
        config = dotenv_values(env_path)
        
        checks = [
            ('TRADIER_API_KEY', 'Tradier API'),
            ('TRADIER_ACCOUNT_ID', 'Tradier Account'),
            ('HEALTHCHECK_DAILY_NAV_URL', 'Healthcheck (NAV)'),
            ('HEALTHCHECK_WATCHDOG_URL', 'Healthcheck (Watchdog)'),
            ('SMTP_USER', 'Email (SMTP)'),
        ]
        
        for key, label in checks:
            if config.get(key):
                print(f"   ✓ {label}: Configured")
            else:
                print(f"   ○ {label}: Not configured")
    else:
        print("   ❌ .env file not found!")
        issues.append(".env file missing")
    
    print()
    
    # Summary
    print("=" * 60)
    if issues:
        print(f"⚠️  STATUS: {len(issues)} ISSUE(S) FOUND")
        for issue in issues:
            print(f"   • {issue}")
    else:
        print("✅ STATUS: ALL SYSTEMS OPERATIONAL")
    print("=" * 60)

if __name__ == "__main__":
    os.chdir(PROJECT_DIR)
    check_status()
