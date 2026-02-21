"""
TOVITO TRADER - Enhanced Daily NAV Update
==========================================
Comprehensive daily update that:
1. Fetches current portfolio balance from configured brokerage
2. Calculates NAV
3. Writes heartbeat file for monitoring
4. Pings external monitoring service
5. Logs everything

Supports multiple brokerage providers (Tradier, TastyTrade) via
the BROKERAGE_PROVIDER environment variable.

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

# Brokerage settings
BROKERAGE_PROVIDER = os.getenv('BROKERAGE_PROVIDER', 'tradier')

# Legacy Tradier settings (kept for _get_tradier_balance_legacy fallback)
TRADIER_API_KEY = os.getenv('TRADIER_API_KEY', '')
TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID', '')
TRADIER_BASE_URL = os.getenv('TRADIER_BASE_URL', 'https://api.tradier.com/v1')

# External monitoring
HEALTHCHECK_DAILY_NAV_URL = os.getenv('HEALTHCHECK_DAILY_NAV_URL', '')

# Email settings (for alerts on failure)
# Support both SMTP_USERNAME (standard) and SMTP_USER (legacy) env var names
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USERNAME') or os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
ALERT_EMAIL = os.getenv('ALERT_EMAIL') or os.getenv('ADMIN_EMAIL', '')


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
        """Send email alert on NAV update failure.

        Uses the centralized EmailService so the attempt is logged
        in the email_logs table for audit trail.
        """
        if not ALERT_EMAIL:
            self.log("ALERT_EMAIL / ADMIN_EMAIL not configured - cannot send failure alert", "WARNING")
            return

        try:
            from src.automation.email_service import EmailService
            service = EmailService()

            subject = "TOVITO: Daily NAV Update FAILED"
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

            success = service.send_email(
                to_email=ALERT_EMAIL,
                subject=subject,
                message=body,
                email_type='Alert',
            )

            if success:
                self.log("[OK] Failure alert email sent")
            else:
                self.log("Failure alert email could not be sent", "WARNING")

        except Exception as e:
            self.log(f"Failed to send alert email: {e}", "ERROR")
    
    def get_portfolio_balance(self):
        """
        Fetch combined account balance from ALL configured brokerages.

        Reads BROKERAGE_PROVIDERS env var (comma-separated, e.g. "tradier,tastytrade").
        Falls back to BROKERAGE_PROVIDER for single-provider backwards compatibility.

        The combined total_equity across all brokerages becomes the fund's
        total portfolio value, which determines the NAV per share.
        """
        try:
            # Ensure project root is in path for imports
            if str(PROJECT_DIR) not in sys.path:
                sys.path.insert(0, str(PROJECT_DIR))

            from src.api.brokerage import get_combined_balance, get_configured_providers

            providers = get_configured_providers()
            self.log(f"Fetching balance from brokerages: {', '.join(providers)}...")

            combined = get_combined_balance()
            total_equity = combined['total_equity']

            # Log per-brokerage breakdown for audit trail
            for provider, detail in combined.get('brokerage_details', {}).items():
                prov_equity = detail.get('total_equity', 0)
                self.log(f"  [OK] {provider}: ${prov_equity:,.2f}")

            self.log(f"[OK] Combined portfolio balance: ${total_equity:,.2f}")
            return total_equity

        except Exception as e:
            error = f"Brokerage API exception: {e}"
            self.errors.append(error)
            self.log(error, "ERROR")
            return None

    def _get_tradier_balance_legacy(self):
        """
        Legacy: Fetch account balance directly from Tradier API.

        Kept as fallback per project policy — DO NOT remove Tradier
        code until TastyTrade equivalents are fully tested.
        """
        self.log("Fetching balance from Tradier (legacy)...")

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
    
    def snapshot_holdings(self):
        """
        Capture current positions from all brokerages for historical tracking.

        Stores a daily snapshot of every position held across all brokerage
        accounts. This builds the dataset for per-holding performance charts
        in monthly reports.

        Non-fatal: if this fails, the NAV update is still valid.
        """
        try:
            if str(PROJECT_DIR) not in sys.path:
                sys.path.insert(0, str(PROJECT_DIR))

            from src.api.brokerage import get_all_brokerage_clients

            clients = get_all_brokerage_clients()
            today = datetime.now().strftime('%Y-%m-%d')
            now = datetime.now().isoformat()

            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()

            for provider, client in clients.items():
                try:
                    positions = client.get_positions()
                except Exception as e:
                    self.log(f"  Holdings snapshot skipped for {provider}: {e}", "WARNING")
                    continue

                # Insert or replace snapshot header
                cursor.execute("""
                    INSERT OR REPLACE INTO holdings_snapshots
                    (date, source, snapshot_time, total_positions)
                    VALUES (?, ?, ?, ?)
                """, (today, provider, now, len(positions)))

                snapshot_id = cursor.lastrowid

                # Clear any existing position records for this snapshot
                cursor.execute(
                    "DELETE FROM position_snapshots WHERE snapshot_id = ?",
                    (snapshot_id,)
                )

                # Insert each position
                for pos in positions:
                    qty = pos.get('quantity', 0) or 0
                    price = pos.get('close_price', 0) or 0
                    avg_price = pos.get('average_open_price', 0) or 0
                    market_value = qty * price
                    cost_basis = qty * avg_price if avg_price else None
                    unrealized_pl = (market_value - cost_basis) if cost_basis else None

                    cursor.execute("""
                        INSERT INTO position_snapshots (
                            snapshot_id, symbol, underlying_symbol, quantity,
                            instrument_type, average_open_price, close_price,
                            market_value, cost_basis, unrealized_pl,
                            option_type, strike, expiration_date, multiplier
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        pos.get('symbol'),
                        pos.get('underlying_symbol'),
                        qty,
                        pos.get('instrument_type'),
                        avg_price if avg_price else None,
                        price if price else None,
                        round(market_value, 2),
                        round(cost_basis, 2) if cost_basis else None,
                        round(unrealized_pl, 2) if unrealized_pl is not None else None,
                        pos.get('option_type'),
                        pos.get('strike'),
                        pos.get('expiration_date'),
                        pos.get('multiplier'),
                    ))

                self.log(f"  [OK] Holdings snapshot: {provider} - {len(positions)} positions")

            conn.commit()
            conn.close()

        except Exception as e:
            self.log(f"Holdings snapshot failed: {e}", "WARNING")

    def run_daily_reconciliation(self, portfolio_value, total_shares):
        """
        Verify NAV integrity by cross-checking key financial figures.

        Checks:
        1. Brokerage balance matches what we recorded
        2. Investor shares sum matches total_shares in daily_nav
        3. Portfolio value is positive and reasonable
        4. NAV per share is within expected bounds

        Non-fatal: warnings are logged but don't block the NAV update.
        """
        self.log("Running daily reconciliation...")
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')

            # Get the NAV we just wrote
            cursor.execute(
                "SELECT nav_per_share, total_portfolio_value, total_shares "
                "FROM daily_nav WHERE date = ?", (today,)
            )
            nav_row = cursor.fetchone()
            if not nav_row:
                self.log("Reconciliation skipped: no NAV entry for today", "WARNING")
                conn.close()
                return

            recorded_nav = nav_row[0]
            recorded_value = nav_row[1]
            recorded_shares = nav_row[2]

            # Cross-check: sum of investor shares vs daily_nav total_shares
            cursor.execute("""
                SELECT SUM(current_shares) FROM investors
                WHERE status = 'Active' OR status IS NULL OR status = ''
            """)
            investor_shares_sum = cursor.fetchone()[0] or 0

            share_diff = abs(recorded_shares - investor_shares_sum)
            shares_match = share_diff < 0.01  # Allow tiny float rounding

            # Cross-check: portfolio value matches brokerage balance
            value_diff = abs(recorded_value - portfolio_value)
            value_match = value_diff < 0.01

            # NAV sanity checks
            nav_positive = recorded_nav > 0
            nav_reasonable = 0.01 < recorded_nav < 1000  # Guard against wild values

            # Determine status
            issues = []
            if not shares_match:
                issues.append(f"Share mismatch: NAV table={recorded_shares:.4f}, "
                              f"investor sum={investor_shares_sum:.4f}, "
                              f"diff={share_diff:.4f}")
            if not value_match:
                issues.append(f"Value mismatch: NAV table={recorded_value:.2f}, "
                              f"brokerage={portfolio_value:.2f}, "
                              f"diff={value_diff:.2f}")
            if not nav_positive:
                issues.append(f"NAV is not positive: {recorded_nav:.4f}")
            if not nav_reasonable:
                issues.append(f"NAV outside expected range: {recorded_nav:.4f}")

            status = 'matched' if not issues else 'mismatch'
            notes = '; '.join(issues) if issues else None

            # Write reconciliation record
            cursor.execute("""
                INSERT OR REPLACE INTO daily_reconciliation (
                    date, tradier_balance, calculated_portfolio_value,
                    difference, total_shares, nav_per_share,
                    new_deposits, new_withdrawals, unallocated_deposits,
                    status, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, CURRENT_TIMESTAMP)
            """, (
                today, portfolio_value, recorded_value,
                value_diff, recorded_shares, recorded_nav,
                status, notes,
            ))

            conn.commit()
            conn.close()

            if issues:
                for issue in issues:
                    self.log(f"  RECONCILIATION WARNING: {issue}", "WARNING")
            else:
                self.log("[OK] Daily reconciliation passed - all checks matched")

        except Exception as e:
            self.log(f"Daily reconciliation failed: {e}", "WARNING")

    def run_trade_sync(self):
        """
        Step 6: Sync brokerage trades via ETL pipeline (non-fatal).

        Runs the ETL pipeline for the last 3 days to catch any trades
        made since the last sync (covers weekends and holidays).
        """
        try:
            self.log("Running trade sync via ETL pipeline...")
            from src.etl.load import run_full_pipeline
            from datetime import timedelta

            stats = run_full_pipeline(
                start_date=datetime.now() - timedelta(days=3),
                end_date=datetime.now(),
            )

            # Log extract results
            for provider, extract_stats in stats.get('extract', {}).items():
                if 'error' in extract_stats:
                    self.log(f"  Trade sync extract [{provider}]: FAILED - {extract_stats['error']}", "WARNING")
                else:
                    ingested = extract_stats.get('ingested', 0)
                    skipped = extract_stats.get('skipped', 0)
                    self.log(f"  [OK] Trade sync [{provider}]: {ingested} new, {skipped} existing")

            # Log load results
            load_stats = stats.get('load', {})
            loaded = load_stats.get('loaded', 0)
            dupes = load_stats.get('duplicates', 0)
            errors = load_stats.get('load_errors', 0)

            if errors > 0:
                self.log(f"  Trade sync load: {loaded} loaded, {dupes} dupes, {errors} errors", "WARNING")
            else:
                self.log(f"  [OK] Trade sync: {loaded} new trades loaded, {dupes} already existed")

        except Exception as e:
            self.log(f"Trade sync failed: {e}", "WARNING")

    def run(self):
        """Main execution"""
        self.log("=" * 60)
        self.log("TOVITO TRADER - Daily NAV Update")
        self.log("=" * 60)
        self.log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        success = False
        
        try:
            # Step 1: Get portfolio balance from configured brokerage
            portfolio_value = self.get_portfolio_balance()
            if portfolio_value is None:
                raise Exception("Failed to get portfolio balance")
            
            # Step 2: Get total shares
            total_shares = self.get_total_shares()
            if total_shares is None or total_shares <= 0:
                raise Exception("Failed to get total shares")
            
            # Step 3: Update NAV
            if not self.update_nav(portfolio_value, total_shares):
                raise Exception("Failed to update NAV")

            # Step 4: Snapshot holdings (non-fatal)
            self.snapshot_holdings()

            # Step 5: Daily reconciliation (non-fatal)
            self.run_daily_reconciliation(portfolio_value, total_shares)

            # Step 6: Sync brokerage trades via ETL (non-fatal)
            self.run_trade_sync()

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
