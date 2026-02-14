"""
TOVITO TRADER - Watchdog Monitor
================================
This runs SEPARATELY from the daily NAV task to monitor if things are working.

Schedule this to run ~1 hour AFTER the daily NAV task.
If daily NAV runs at 4:05 PM, run this at 5:00 PM.

What it checks:
1. Was NAV updated today (in database)?
2. Did the daily task run (heartbeat file)?
3. Any errors in recent logs?
4. Is the database accessible?

What it does on failure:
1. Sends email alert
2. Pings external monitoring service (healthchecks.io)
3. Logs the issue

External monitoring (healthchecks.io) will alert you if THIS script fails to run.
"""

import os
import sys
import sqlite3
import smtplib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuration
PROJECT_DIR = Path("C:/tovito-trader")
DB_PATH = PROJECT_DIR / "data" / "tovito.db"
HEARTBEAT_FILE = PROJECT_DIR / "logs" / "daily_nav_heartbeat.txt"
LOG_FILE = PROJECT_DIR / "logs" / "watchdog.log"
DAILY_LOG = PROJECT_DIR / "logs" / "daily_runner.log"

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

# External monitoring URLs (get free account at healthchecks.io)
# These are webhook URLs that expect a ping. If no ping, they alert you.
HEALTHCHECK_WATCHDOG_URL = os.getenv('HEALTHCHECK_WATCHDOG_URL', '')  # Ping when watchdog runs successfully
HEALTHCHECK_DAILY_NAV_URL = os.getenv('HEALTHCHECK_DAILY_NAV_URL', '')  # Ping when daily NAV confirmed OK

# Email settings
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
ALERT_EMAIL = os.getenv('ALERT_EMAIL', 'dlang32@gmail.com')


class WatchdogMonitor:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.checks_passed = 0
        self.checks_failed = 0
        
    def log(self, message, level="INFO"):
        """Write to watchdog log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except Exception as e:
            print(f"Could not write to log: {e}")
    
    def check_database_accessible(self):
        """Check 1: Can we connect to the database?"""
        self.log("Checking database accessibility...")
        try:
            if not DB_PATH.exists():
                self.issues.append(f"Database not found at {DB_PATH}")
                self.checks_failed += 1
                return False
            
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM daily_nav")
            count = cursor.fetchone()[0]
            conn.close()
            
            self.log(f"[OK] Database accessible ({count} NAV records)")
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"Database error: {e}")
            self.checks_failed += 1
            return False
    
    def check_nav_updated_today(self):
        """Check 2: Was NAV updated today?"""
        self.log("Checking if NAV was updated today...")
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT date, nav_per_share, total_portfolio_value FROM daily_nav WHERE date = ?", (today,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                self.log(f"[OK] NAV updated today: ${result[1]:.4f} (Portfolio: ${result[2]:,.2f})")
                self.checks_passed += 1
                return True
            else:
                # Check if it's a weekend or holiday (market closed)
                day_of_week = datetime.now().weekday()
                if day_of_week >= 5:  # Saturday = 5, Sunday = 6
                    self.log(f"○ NAV not updated (Weekend - market closed)")
                    self.warnings.append("NAV not updated - Weekend")
                    self.checks_passed += 1
                    return True
                else:
                    self.issues.append(f"NAV NOT updated today ({today})")
                    self.checks_failed += 1
                    return False
                    
        except Exception as e:
            self.issues.append(f"Error checking NAV: {e}")
            self.checks_failed += 1
            return False
    
    def check_heartbeat_file(self):
        """Check 3: Did the daily task write a heartbeat file?"""
        self.log("Checking heartbeat file...")
        try:
            if not HEARTBEAT_FILE.exists():
                # First run - file might not exist yet
                self.warnings.append("Heartbeat file not found (may be first run)")
                self.checks_passed += 1
                return True
            
            # Check file modification time
            mtime = datetime.fromtimestamp(HEARTBEAT_FILE.stat().st_mtime)
            age_hours = (datetime.now() - mtime).total_seconds() / 3600
            
            # Read content
            with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if age_hours <= 24:
                self.log(f"[OK] Heartbeat file fresh ({age_hours:.1f} hours old)")
                self.log(f"  Last run: {content}")
                self.checks_passed += 1
                return True
            else:
                self.issues.append(f"Heartbeat file stale ({age_hours:.1f} hours old)")
                self.checks_failed += 1
                return False
                
        except Exception as e:
            self.warnings.append(f"Heartbeat check warning: {e}")
            self.checks_passed += 1
            return True
    
    def check_recent_errors(self):
        """Check 4: Any errors in recent logs?"""
        self.log("Checking for recent errors in logs...")
        try:
            if not DAILY_LOG.exists():
                self.warnings.append("Daily log file not found")
                self.checks_passed += 1
                return True
            
            # Read last 50 lines of log
            with open(DAILY_LOG, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-50:]
            
            error_keywords = ['ERROR', 'FAILED', 'Exception', 'Traceback']
            recent_errors = []
            
            for line in lines:
                for keyword in error_keywords:
                    if keyword in line:
                        recent_errors.append(line.strip()[:100])
                        break
            
            if recent_errors:
                self.warnings.append(f"Found {len(recent_errors)} error(s) in recent logs")
                for err in recent_errors[:3]:  # Show first 3
                    self.log(f"  ! {err}")
                self.checks_passed += 1  # Warning, not failure
                return True
            else:
                self.log("[OK] No recent errors in logs")
                self.checks_passed += 1
                return True
                
        except Exception as e:
            self.warnings.append(f"Log check warning: {e}")
            self.checks_passed += 1
            return True
    
    def check_portfolio_value_reasonable(self):
        """Check 5: Is portfolio value within expected range?"""
        self.log("Checking portfolio value is reasonable...")
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            
            # Get latest two values
            cursor.execute("""
                SELECT date, total_portfolio_value 
                FROM daily_nav 
                ORDER BY date DESC 
                LIMIT 2
            """)
            results = cursor.fetchall()
            conn.close()
            
            if len(results) < 2:
                self.log("○ Not enough history to check (normal for new system)")
                self.checks_passed += 1
                return True
            
            latest = results[0][1]
            previous = results[1][1]
            
            # Check for suspicious changes (>20% in one day)
            if previous > 0:
                change_pct = abs((latest - previous) / previous * 100)
                if change_pct > 20:
                    self.issues.append(f"Suspicious portfolio change: {change_pct:.1f}% in one day (${previous:,.0f} → ${latest:,.0f})")
                    self.checks_failed += 1
                    return False
            
            # Check for zero or negative
            if latest <= 0:
                self.issues.append(f"Invalid portfolio value: ${latest:,.2f}")
                self.checks_failed += 1
                return False
            
            self.log(f"[OK] Portfolio value reasonable: ${latest:,.2f}")
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.warnings.append(f"Portfolio check warning: {e}")
            self.checks_passed += 1
            return True
    
    def send_alert(self, subject, body):
        """Send email alert"""
        if not SMTP_USER or not SMTP_PASSWORD:
            self.log("Email not configured - skipping alert", "WARNING")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = SMTP_USER
            msg['To'] = ALERT_EMAIL
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            self.log(f"[OK] Alert email sent to {ALERT_EMAIL}")
            return True
            
        except Exception as e:
            self.log(f"Failed to send email: {e}", "ERROR")
            return False
    
    def ping_healthcheck(self, url, status="success"):
        """Ping external monitoring service"""
        if not url:
            return False
        
        try:
            # Healthchecks.io supports /fail suffix for failures
            ping_url = url if status == "success" else f"{url}/fail"
            response = requests.get(ping_url, timeout=10)
            self.log(f"[OK] Pinged external monitor ({status})")
            return response.status_code == 200
        except Exception as e:
            self.log(f"Failed to ping external monitor: {e}", "WARNING")
            return False
    
    def run_all_checks(self):
        """Run all monitoring checks"""
        self.log("=" * 60)
        self.log("TOVITO WATCHDOG MONITOR")
        self.log("=" * 60)
        
        # Run all checks
        self.check_database_accessible()
        self.check_nav_updated_today()
        self.check_heartbeat_file()
        self.check_recent_errors()
        self.check_portfolio_value_reasonable()
        
        # Summary
        self.log("-" * 60)
        self.log(f"RESULTS: {self.checks_passed} passed, {self.checks_failed} failed, {len(self.warnings)} warnings")
        
        # Determine overall status
        if self.checks_failed > 0:
            status = "CRITICAL"
            self.log(f"STATUS: {status} - Issues detected!", "ERROR")
        elif self.warnings:
            status = "WARNING"
            self.log(f"STATUS: {status} - Check warnings")
        else:
            status = "OK"
            self.log(f"STATUS: {status} - All systems operational")
        
        # Send alerts if needed
        if self.checks_failed > 0:
            subject = f"🚨 TOVITO ALERT: {self.checks_failed} monitoring check(s) FAILED"
            body = self.format_alert_body()
            self.send_alert(subject, body)
            self.ping_healthcheck(HEALTHCHECK_WATCHDOG_URL, "fail")
        else:
            # All good - ping success
            self.ping_healthcheck(HEALTHCHECK_WATCHDOG_URL, "success")
            if not self.warnings:
                # NAV confirmed OK - ping that too
                self.ping_healthcheck(HEALTHCHECK_DAILY_NAV_URL, "success")
        
        self.log("=" * 60)
        return self.checks_failed == 0
    
    def format_alert_body(self):
        """Format alert email body"""
        lines = [
            "TOVITO TRADER - Monitoring Alert",
            "=" * 40,
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "ISSUES DETECTED:",
        ]
        
        for issue in self.issues:
            lines.append(f"  [FAIL] {issue}")
        
        if self.warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  ⚠️ {warning}")
        
        lines.extend([
            "",
            f"Checks Passed: {self.checks_passed}",
            f"Checks Failed: {self.checks_failed}",
            "",
            "Please investigate immediately.",
            "",
            "---",
            "Tovito Trader Watchdog Monitor"
        ])
        
        return "\n".join(lines)


def main():
    """Main entry point"""
    os.chdir(PROJECT_DIR)
    
    monitor = WatchdogMonitor()
    success = monitor.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
