"""
Generate Referral Code
========================
Creates a unique referral code for an investor and optionally
records a referral with the referred person's details.

Code format: TOVITO-{6 alphanumeric chars}

Usage:
    python scripts/investor/generate_referral_code.py
    python scripts/investor/generate_referral_code.py --investor 20260101-01A
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import argparse
import sqlite3
import sys
import secrets
import string
from pathlib import Path
from datetime import datetime, date

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'data' / 'tovito.db'


def generate_code(conn, max_attempts=10):
    """Generate a unique referral code."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(max_attempts):
        code = 'TOVITO-' + ''.join(secrets.choice(chars) for _ in range(6))
        # Check uniqueness
        cursor = conn.execute(
            "SELECT referral_id FROM referrals WHERE referral_code = ?", (code,)
        )
        if not cursor.fetchone():
            return code
    raise RuntimeError("Failed to generate unique code after multiple attempts")


def get_active_investors(conn):
    """Get list of active investors."""
    cursor = conn.execute(
        "SELECT investor_id, name FROM investors WHERE status = 'Active' ORDER BY name"
    )
    return cursor.fetchall()


def get_existing_codes(conn, investor_id):
    """Get existing referral codes for an investor."""
    cursor = conn.execute("""
        SELECT referral_code, referred_name, referred_date, status
        FROM referrals
        WHERE referrer_investor_id = ?
        ORDER BY referred_date DESC
    """, (investor_id,))
    return cursor.fetchall()


def run():
    """Interactive referral code generation."""
    parser = argparse.ArgumentParser(description="Generate referral code")
    parser.add_argument('--investor', help="Investor ID (skip selection)")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("GENERATE REFERRAL CODE")
    print("=" * 60)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Select investor
        if args.investor:
            investor_id = args.investor
        else:
            investors = get_active_investors(conn)
            if not investors:
                print("No active investors found.")
                return False

            print("Active Investors:")
            for i, inv in enumerate(investors, 1):
                print(f"  {i}. {inv['name']} ({inv['investor_id']})")
            print()

            choice = input("Select investor number: ").strip()
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(investors):
                    print("Invalid selection.")
                    return False
                investor_id = investors[idx]['investor_id']
            except ValueError:
                print("Invalid input.")
                return False

        # Show existing codes
        existing = get_existing_codes(conn, investor_id)
        if existing:
            print(f"\nExisting referral codes for {investor_id}:")
            for ref in existing:
                name = ref['referred_name'] or '(no name)'
                print(f"  {ref['referral_code']}  — {name}  [{ref['status']}]")
            print()

        # Get referred person details (optional)
        print("Enter details for the referred person (or press Enter to skip):")
        referred_name = input("  Referred person's name: ").strip() or None
        referred_email = input("  Referred person's email: ").strip() or None

        # Generate code
        code = generate_code(conn)

        # Insert referral record
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO referrals (
                referrer_investor_id, referral_code,
                referred_name, referred_email, referred_date,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            investor_id, code, referred_name, referred_email,
            date.today().isoformat(), now, now,
        ))

        # Log
        conn.execute("""
            INSERT INTO system_logs (timestamp, level, category, message, details)
            VALUES (?, 'INFO', 'Referral', ?, ?)
        """, (
            now,
            f"Referral code {code} generated for investor {investor_id}",
            f"referred_name={referred_name or 'N/A'}",
        ))

        conn.commit()

        print()
        print("=" * 60)
        print(f"  REFERRAL CODE:  {code}")
        print("=" * 60)
        print()
        print(f"  Referrer:  {investor_id}")
        if referred_name:
            print(f"  Referred:  {referred_name}")
        if referred_email:
            print(f"  Email:     {referred_email}")
        print(f"  Status:    pending")
        print()
        print("Share this code with the referred person.")
        print("Update status: python scripts/investor/manage_profile.py")
        print()

        return True

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        success = run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)
