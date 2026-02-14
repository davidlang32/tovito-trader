"""
TOVITO TRADER - Enhanced Daily NAV Update
==========================================
Comprehensive daily update that:
1. Syncs Tradier transactions
2. Fetches current portfolio balance
3. Calculates NAV
4. Writes heartbeat file for monitoring
5. Pings external monitoring service
6. Logs everything

This script should be monitored by watchdog_monitor.py
"""

import os
import sys
import sqlite3
import requests
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for Task Scheduler
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 mode
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# Configuration
PROJECT_DIR = Path("C:/tovito-trader")
DB_PATH = PROJECT_DIR / "data" / "tovito.db"
HEARTBEAT_FILE = PROJECT_DIR / "logs" / "daily_nav_heartbeat.txt"
LOG_FILE = PROJECT_DIR / "logs" / "daily_runner.log"

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

# API settings
TRADIER_API_KEY = os.getenv('TRADIER_API_KEY', '')
TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID', '')
TRADIER_BASE_URL = os.getenv('TRADIER_BASE_URL', 'https://api.tradier.com/v1')

# External monitoring
HEALTHCHECK_DAILY_NAV_URL = os.getenv('HEALTHCHECK_DAILY_NAV_URL', '')

# Email settings (for alerts on failure)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
ALERT_EMAIL = os.getenv('ALERT_EMAIL', '')


class DailyNAVUpdater:
    def __init__(self):
        self.errors = []
        self.portfolio_value = None
        self.nav_per_share = None
        
    def log(self, message, level="INFO"):
        """Write to log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Try to write to log, handle permission errors gracefully
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            except PermissionError:
                # Try alternate log file if main one is locked
                alt_log = LOG_FILE.parent / f"daily_runner_{datetime.now().strftime('%Y%m%d')}.log"
                with open(alt_log, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
        except Exception as e:
            # Don't let logging failures stop the script
            pass  # Silently continue - we already printed to console
    
    def write_heartbeat(self):
        """Write heartbeat file so watchdog knows we ran"""
        try:
            HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HEARTBEAT_FILE, 'w', encoding='utf-8') as f:
                f.write(f"Last successful run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Portfolio Value: ${self.portfolio_value:,.2f}\n" if self.portfolio_value else "")
                f.write(f"NAV per Share: ${self.nav_per_share:.4f}\n" if self.nav_per_share else "")
            self.log("[OK] Heartbeat file updated")
        except Exception as e:
            self.log(f"Failed to write heartbeat: {e}", "ERROR")
    
    def ping_healthcheck(self, status="success"):
        """Ping external monitoring service"""
        if not HEALTHCHECK_DAILY_NAV_URL:
            self.log("External monitoring not configured (HEALTHCHECK_DAILY_NAV_URL)")
            return
        
        try:
            url = HEALTHCHECK_DAILY_NAV_URL if status == "success" else f"{HEALTHCHECK_DAILY_NAV_URL}/fail"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.log(f"[OK] Pinged external monitor ({status})")
            else:
                self.log(f"External monitor returned {response.status_code}", "WARNING")
        except Exception as e:
            self.log(f"Failed to ping external monitor: {e}", "WARNING")
    
    def send_failure_alert(self, error_message):
        """Send email alert on failure"""
        if not SMTP_USER or not SMTP_PASSWORD or not ALERT_EMAIL:
            self.log("Email not configured - cannot send failure alert", "WARNING")
            return
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = SMTP_USER
            msg['To'] = ALERT_EMAIL
            msg['Subject'] = "🚨 TOVITO: Daily NAV Update FAILED"
            
            body = f"""
TOVITO TRADER - Daily NAV Update FAILED
=======================================
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Error:
{error_message}

Errors encountered:
{chr(10).join(self.errors)}

Please check the system immediately.

---
Automated alert from daily_nav_enhanced.py
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            self.log("[OK] Failure alert email sent")
            
        except Exception as e:
            self.log(f"Failed to send alert email: {e}", "ERROR")
    
    def get_tradier_balance(self):
        """Fetch account balance from Tradier API"""
        self.log("Fetching balance from Tradier...")
        
        if not TRADIER_API_KEY or not TRADIER_ACCOUNT_ID:
            error = "TRADIER_API_KEY or TRADIER_ACCOUNT_ID not configured"
            self.errors.append(error)
            self.log(error, "ERROR")
            return None
        
        try:
            url = f"{TRADIER_BASE_URL}/accounts/{TRADIER_ACCOUNT_ID}/balances"
            headers = {
                'Authorization': f'Bearer {TRADIER_API_KEY}',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                balances = data.get('balances', {})
                total_equity = balances.get('total_equity', 0)
                self.log(f"[OK] Tradier balance: ${total_equity:,.2f}")
                return total_equity
            else:
                error = f"Tradier API error: {response.status_code} - {response.text[:200]}"
                self.errors.append(error)
                self.log(error, "ERROR")
                return None
                
        except requests.exceptions.Timeout:
            error = "Tradier API timeout"
            self.errors.append(error)
            self.log(error, "ERROR")
            return None
        except Exception as e:
            error = f"Tradier API exception: {e}"
            self.errors.append(error)
            self.log(error, "ERROR")
            return None
    
    def get_total_shares(self):
        """Get total shares from database"""
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(current_shares) 
                FROM investors 
                WHERE status = 'Active' OR status IS NULL OR status = ''
            """)
            result = cursor.fetchone()
            conn.close()
            
            total_shares = result[0] if result and result[0] else 0
            self.log(f"[OK] Total shares: {total_shares:,.2f}")
            return total_shares
            
        except Exception as e:
            error = f"Database error getting shares: {e}"
            self.errors.append(error)
            self.log(error, "ERROR")
            return None
    
    def get_previous_nav(self):
        """Get previous day's NAV for change calculation"""
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT total_portfolio_value, nav_per_share 
                FROM daily_nav 
                ORDER BY date DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()
            return result if result else (0, 0)
        except Exception as e:
            self.log(f"Warning: Could not get previous NAV: {e}", "WARNING")
            return (0, 0)
    
    def update_nav(self, portfolio_value, total_shares):
        """Update NAV in database"""
        try:
            if total_shares <= 0:
                error = "No shares found - cannot calculate NAV"
                self.errors.append(error)
                self.log(error, "ERROR")
                return False
            
            nav_per_share = portfolio_value / total_shares
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Get previous values for change calculation
            prev_value, prev_nav = self.get_previous_nav()
            daily_change_dollars = portfolio_value - prev_value if prev_value else 0
            daily_change_percent = ((nav_per_share - prev_nav) / prev_nav * 100) if prev_nav else 0
            
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            
            # Check if today's entry exists
            cursor.execute("SELECT date FROM daily_nav WHERE date = ?", (today,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute("""
                    UPDATE daily_nav SET
                        nav_per_share = ?,
                        total_portfolio_value = ?,
                        total_shares = ?,
                        daily_change_dollars = ?,
                        daily_change_percent = ?,
                        source = 'API'
                    WHERE date = ?
                """, (nav_per_share, portfolio_value, total_shares,
                      daily_change_dollars, daily_change_percent, today))
                self.log(f"[OK] Updated existing NAV entry for {today}")
            else:
                cursor.execute("""
                    INSERT INTO daily_nav (
                        date, nav_per_share, total_portfolio_value, total_shares,
                        daily_change_dollars, daily_change_percent, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'API', datetime('now'))
                """, (today, nav_per_share, portfolio_value, total_shares,
                      daily_change_dollars, daily_change_percent))
                self.log(f"[OK] Created new NAV entry for {today}")
            
            conn.commit()
            conn.close()
            
            # Store for heartbeat
            self.portfolio_value = portfolio_value
            self.nav_per_share = nav_per_share
            
            self.log(f"[OK] NAV Updated Successfully!")
            self.log(f"  Date: {today}")
            self.log(f"  Portfolio: ${portfolio_value:,.2f}")
            self.log(f"  Shares: {total_shares:,.2f}")
            self.log(f"  NAV/Share: ${nav_per_share:.4f}")
            self.log(f"  Change: ${daily_change_dollars:,.2f} ({daily_change_percent:+.2f}%)")
            
            return True
            
        except Exception as e:
            error = f"Database error updating NAV: {e}"
            self.errors.append(error)
            self.log(error, "ERROR")
            return False
    
    def run(self):
        """Main execution"""
        self.log("=" * 60)
        self.log("TOVITO TRADER - Daily NAV Update")
        self.log("=" * 60)
        self.log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        success = False
        
        try:
            # Step 1: Get Tradier balance
            portfolio_value = self.get_tradier_balance()
            if portfolio_value is None:
                raise Exception("Failed to get portfolio balance")
            
            # Step 2: Get total shares
            total_shares = self.get_total_shares()
            if total_shares is None or total_shares <= 0:
                raise Exception("Failed to get total shares")
            
            # Step 3: Update NAV
            if not self.update_nav(portfolio_value, total_shares):
                raise Exception("Failed to update NAV")
            
            # Success!
            success = True
            self.log("=" * 60)
            self.log("[OK] DAILY NAV UPDATE COMPLETED SUCCESSFULLY")
            self.log("=" * 60)
            
        except Exception as e:
            self.log(f"FATAL ERROR: {e}", "ERROR")
            self.errors.append(str(e))
        
        # Always write heartbeat (even on failure - shows we tried)
        self.write_heartbeat()
        
        # Ping external monitor
        if success:
            self.ping_healthcheck("success")
        else:
            self.ping_healthcheck("fail")
            self.send_failure_alert(str(self.errors))
        
        return success


def main():
    """Entry point"""
    os.chdir(PROJECT_DIR)
    
    updater = DailyNAVUpdater()
    success = updater.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
