"""
Database Migration - Fund Flow Requests

Adds the fund_flow_requests table for unified contribution/withdrawal
lifecycle tracking. Migrates existing data from withdrawal_requests
into the new table.

Run once to add the table to your database.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def migrate():
    """Add fund_flow_requests table and migrate withdrawal_requests data"""

    db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    print("=" * 70)
    print("DATABASE MIGRATION - FUND FLOW REQUESTS")
    print("=" * 70)
    print()
    print("This will:")
    print("  1. Create the fund_flow_requests table for unified")
    print("     contribution + withdrawal lifecycle tracking")
    print("  2. Migrate existing withdrawal_requests data (if any)")
    print("     into the new table")
    print("  3. Keep the old withdrawal_requests table intact")
    print()
    print("Fund Flow Lifecycle:")
    print("  pending -> approved -> awaiting_funds -> matched -> processed")
    print()

    confirm = input("Proceed with migration? (yes/no): ").strip().lower()

    if confirm not in ['yes', 'y']:
        print("Migration cancelled.")
        return False

    print()
    print("Running migration...")
    print()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if fund_flow_requests already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'fund_flow_requests'
        """)
        existing = cursor.fetchone()

        if existing:
            print("Warning: fund_flow_requests table already exists")
            overwrite = input("Continue anyway? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                print("Migration cancelled.")
                conn.close()
                return False
            print()

        # Create fund_flow_requests table
        print("Creating fund_flow_requests table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fund_flow_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Request details
                investor_id TEXT NOT NULL,
                flow_type TEXT NOT NULL CHECK (flow_type IN ('contribution', 'withdrawal')),
                requested_amount REAL NOT NULL CHECK (requested_amount > 0),
                request_date DATE NOT NULL,
                request_method TEXT NOT NULL DEFAULT 'portal'
                    CHECK (request_method IN ('portal', 'email', 'verbal', 'admin', 'other')),

                -- Lifecycle status
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'awaiting_funds', 'matched',
                                      'processed', 'rejected', 'cancelled')),

                -- Approval
                approved_by TEXT,
                approved_date TIMESTAMP,
                rejection_reason TEXT,

                -- Brokerage matching
                matched_trade_id INTEGER,
                matched_raw_id INTEGER,
                matched_date TIMESTAMP,
                matched_by TEXT,

                -- Processing (share accounting)
                processed_date TIMESTAMP,
                actual_amount REAL,
                shares_transacted REAL,
                nav_per_share REAL,
                transaction_id INTEGER,

                -- Withdrawal-specific tax fields
                realized_gain REAL,
                tax_withheld REAL DEFAULT 0,
                net_proceeds REAL,

                -- Notes
                notes TEXT,

                -- Metadata
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                -- Foreign keys
                FOREIGN KEY (investor_id) REFERENCES investors(investor_id),
                FOREIGN KEY (matched_trade_id) REFERENCES trades(trade_id),
                FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
            )
        """)
        print("   fund_flow_requests table created")

        # Create indexes
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fund_flow_investor
            ON fund_flow_requests(investor_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fund_flow_status
            ON fund_flow_requests(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fund_flow_type
            ON fund_flow_requests(flow_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fund_flow_matched_trade
            ON fund_flow_requests(matched_trade_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fund_flow_date
            ON fund_flow_requests(request_date)
        """)
        print("   Indexes created")

        # Migrate data from withdrawal_requests if it exists
        migrated_count = 0
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'withdrawal_requests'
        """)
        wr_exists = cursor.fetchone()

        if wr_exists:
            cursor.execute("SELECT COUNT(*) FROM withdrawal_requests")
            wr_count = cursor.fetchone()[0]

            if wr_count > 0:
                print()
                print(f"Found {wr_count} existing withdrawal request(s) to migrate...")

                # Map withdrawal_requests columns to fund_flow_requests
                cursor.execute("SELECT * FROM withdrawal_requests")
                wr_rows = cursor.fetchall()
                wr_columns = [desc[0] for desc in cursor.description]

                for row in wr_rows:
                    wr = dict(zip(wr_columns, row))

                    # Map status: Pending->pending, Approved->approved,
                    #             Processed->processed, Rejected->rejected
                    old_status = (wr.get('status') or 'Pending').lower()
                    if old_status == 'pending':
                        new_status = 'pending'
                    elif old_status == 'approved':
                        new_status = 'approved'
                    elif old_status == 'processed':
                        new_status = 'processed'
                    elif old_status == 'rejected':
                        new_status = 'rejected'
                    else:
                        new_status = 'pending'

                    # Map request_method: normalize to our allowed values
                    old_method = (wr.get('request_method') or 'other').lower()
                    if old_method in ('portal', 'email', 'verbal', 'admin', 'other'):
                        new_method = old_method
                    else:
                        new_method = 'other'

                    cursor.execute("""
                        INSERT INTO fund_flow_requests (
                            investor_id, flow_type, requested_amount, request_date,
                            request_method, status,
                            approved_by, approved_date, rejection_reason,
                            processed_date, actual_amount, shares_transacted,
                            realized_gain, tax_withheld, net_proceeds,
                            notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        wr.get('investor_id'),
                        'withdrawal',  # All old records are withdrawals
                        wr.get('requested_amount', 0),
                        wr.get('request_date'),
                        new_method,
                        new_status,
                        wr.get('approved_by'),
                        wr.get('approved_date'),
                        wr.get('rejection_reason'),
                        wr.get('processed_date'),
                        wr.get('actual_amount'),
                        wr.get('shares_sold'),
                        wr.get('realized_gain'),
                        wr.get('tax_withheld'),
                        wr.get('net_proceeds'),
                        wr.get('notes', '') + (
                            f' [Migrated from withdrawal_requests.id={wr.get("id")}]'
                            if wr.get('id') else ''
                        ),
                        wr.get('created_at', datetime.now().isoformat()),
                        wr.get('updated_at', datetime.now().isoformat()),
                    ))
                    migrated_count += 1

                print(f"   Migrated {migrated_count} withdrawal request(s)")
            else:
                print("   No existing withdrawal requests to migrate")
        else:
            print("   No withdrawal_requests table found (nothing to migrate)")

        conn.commit()

        # Verify table
        print()
        print("Verifying migration...")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'fund_flow_requests'
        """)
        table = cursor.fetchone()

        if table:
            cursor.execute("SELECT COUNT(*) FROM fund_flow_requests")
            count = cursor.fetchone()[0]
            print(f"   fund_flow_requests: {count} rows")

        conn.close()

        print()
        print("=" * 70)
        print("MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("New table: fund_flow_requests")
        print()
        print("Lifecycle Statuses:")
        print("  pending        - Request submitted, awaiting approval")
        print("  approved       - Approved by fund manager")
        print("  awaiting_funds - Waiting for brokerage ACH to arrive/clear")
        print("  matched        - Brokerage ACH matched to this request")
        print("  processed      - Share accounting complete")
        print("  rejected       - Request denied")
        print("  cancelled      - Request cancelled by investor/admin")
        print()
        if migrated_count > 0:
            print(f"Migrated {migrated_count} withdrawal request(s) from old table.")
            print("Old withdrawal_requests table kept intact (not dropped).")
            print()
        print("Next steps:")
        print("  1. Submit request:  python scripts/investor/submit_fund_flow.py")
        print("  2. Match to ACH:    python scripts/investor/match_fund_flow.py")
        print("  3. Process:         python scripts/investor/process_fund_flow.py")
        print()

        return True

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = migrate()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
