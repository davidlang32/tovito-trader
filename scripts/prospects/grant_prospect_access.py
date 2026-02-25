"""
Grant Prospect Access
======================

Generate a time-limited access token for a prospect to view
the fund performance preview page.

Usage:
    python scripts/prospects/grant_prospect_access.py
    python scripts/prospects/grant_prospect_access.py --prospect-id 5
    python scripts/prospects/grant_prospect_access.py --prospect-id 5 --days 60
"""

import os
import sys
import secrets
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "http://localhost:3000")

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_DIR / ".env")
    # Re-read after loading .env
    DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))
    PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "http://localhost:3000")
except ImportError:
    pass


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_prospects():
    """List all prospects with their access status."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.name, p.email, p.status, p.date_added,
                   t.token, t.expires_at, t.last_accessed_at,
                   t.access_count, t.is_revoked
            FROM prospects p
            LEFT JOIN prospect_access_tokens t ON t.prospect_id = p.id
                AND t.is_revoked = 0
            ORDER BY p.date_added DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def grant_access(prospect_id: int, expiry_days: int = 30):
    """Grant access to a prospect."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Verify prospect exists
        cursor.execute("SELECT id, name, email FROM prospects WHERE id = ?", (prospect_id,))
        prospect = cursor.fetchone()
        if not prospect:
            print(f"[ERROR] Prospect {prospect_id} not found.")
            return None

        # Revoke any existing tokens
        cursor.execute("""
            UPDATE prospect_access_tokens
            SET is_revoked = 1
            WHERE prospect_id = ? AND is_revoked = 0
        """, (prospect_id,))

        # Generate token
        token = secrets.token_urlsafe(36)
        expires_at = (datetime.utcnow() + timedelta(days=expiry_days)).isoformat()

        cursor.execute("""
            INSERT INTO prospect_access_tokens
                (prospect_id, token, expires_at, created_by)
            VALUES (?, ?, ?, 'cli')
        """, (prospect_id, token, expires_at))

        conn.commit()

        prospect_url = f"{PORTAL_BASE_URL}/fund-preview?token={token}"

        return {
            "prospect_name": prospect["name"],
            "prospect_email": prospect["email"],
            "token": token,
            "prospect_url": prospect_url,
            "expires_at": expires_at,
        }
    finally:
        conn.close()


def interactive_mode():
    """Interactive mode: select prospect and grant access."""
    prospects = list_prospects()

    if not prospects:
        print("No prospects found in database.")
        print("Prospects are created via the landing page inquiry form.")
        return

    print("=" * 70)
    print("  PROSPECT ACCESS MANAGEMENT")
    print("=" * 70)
    print()
    print(f"{'#':<4} {'Name':<25} {'Email':<30} {'Access':<10}")
    print("-" * 70)

    for p in prospects:
        has_token = p.get("token") is not None
        access_str = "ACTIVE" if has_token else "-"
        if has_token and p.get("access_count"):
            access_str = f"ACTIVE ({p['access_count']} views)"
        print(f"{p['id']:<4} {p['name'][:24]:<25} {p['email'][:29]:<30} {access_str:<10}")

    print()
    prospect_input = input("Enter prospect ID to grant access (or 'q' to quit): ").strip()

    if prospect_input.lower() == 'q':
        return

    try:
        prospect_id = int(prospect_input)
    except ValueError:
        print("[ERROR] Invalid prospect ID.")
        return

    days_input = input("Expiry days [30]: ").strip()
    expiry_days = int(days_input) if days_input else 30

    result = grant_access(prospect_id, expiry_days)
    if result:
        print()
        print("[OK] Access granted!")
        print(f"  Prospect: {result['prospect_name']} ({result['prospect_email']})")
        print(f"  Expires:  {result['expires_at'][:10]} ({expiry_days} days)")
        print()
        print(f"  Fund Preview URL:")
        print(f"  {result['prospect_url']}")
        print()
        print("  Share this URL with the prospect.")


def main():
    parser = argparse.ArgumentParser(
        description="Grant prospect access to the fund preview page"
    )
    parser.add_argument(
        "--prospect-id",
        type=int,
        help="Prospect ID to grant access to",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days until token expires (default: 30)",
    )
    args = parser.parse_args()

    if args.prospect_id:
        result = grant_access(args.prospect_id, args.days)
        if result:
            print(f"[OK] Access granted to {result['prospect_name']}")
            print(f"  URL: {result['prospect_url']}")
            print(f"  Expires: {result['expires_at'][:10]}")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
