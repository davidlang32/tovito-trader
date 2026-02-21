"""
Manage Investor Profile
========================
Interactive CLI for viewing and editing investor profile data.
Sensitive fields (SSN, bank info) are encrypted at rest and only
shown in the interactive terminal session.

Usage:
    python scripts/investor/manage_profile.py
    python scripts/investor/manage_profile.py --investor 20260101-01A
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'data' / 'tovito.db'

# Try to load encryption
ENC_AVAILABLE = False
try:
    from src.utils.encryption import FieldEncryptor
    encryptor = FieldEncryptor()
    ENC_AVAILABLE = True
except Exception:
    encryptor = None


ENCRYPTED_FIELDS = {
    'ssn_encrypted', 'tax_id_encrypted',
    'bank_routing_encrypted', 'bank_account_encrypted',
    'date_of_birth',
}

# Sections for organized display
SECTIONS = {
    'Contact Information': [
        'full_legal_name', 'home_address_line1', 'home_address_line2',
        'home_city', 'home_state', 'home_zip', 'home_country',
        'mailing_same_as_home',
        'mailing_address_line1', 'mailing_address_line2',
        'mailing_city', 'mailing_state', 'mailing_zip', 'mailing_country',
        'email_primary', 'phone_mobile', 'phone_home', 'phone_work',
    ],
    'Personal Information': [
        'date_of_birth', 'marital_status', 'num_dependents', 'citizenship',
    ],
    'Employment Information': [
        'employment_status', 'occupation', 'job_title',
        'employer_name', 'employer_address',
    ],
    'Sensitive / Banking': [
        'ssn_encrypted', 'tax_id_encrypted',
        'bank_routing_encrypted', 'bank_account_encrypted',
        'bank_name', 'bank_account_type',
    ],
    'Accreditation': [
        'is_accredited', 'accreditation_method',
        'accreditation_verified_date', 'accreditation_expires_date',
        'accreditation_docs_on_file',
    ],
    'Preferences': [
        'communication_preference', 'statement_delivery',
    ],
}


def get_active_investors(conn):
    """Get list of active investors."""
    cursor = conn.execute(
        "SELECT investor_id, name FROM investors WHERE status = 'Active' ORDER BY name"
    )
    return cursor.fetchall()


def get_or_create_profile(conn, investor_id):
    """Get existing profile or create a stub."""
    cursor = conn.execute(
        "SELECT * FROM investor_profiles WHERE investor_id = ?", (investor_id,)
    )
    profile = cursor.fetchone()

    if profile:
        return dict(profile)

    # Create stub
    conn.execute(
        "INSERT INTO investor_profiles (investor_id) VALUES (?)",
        (investor_id,)
    )
    conn.commit()

    cursor = conn.execute(
        "SELECT * FROM investor_profiles WHERE investor_id = ?", (investor_id,)
    )
    return dict(cursor.fetchone())


def display_value(field_name, value):
    """Format a field value for display, decrypting if needed."""
    if value is None:
        return "(not set)"

    if field_name in ENCRYPTED_FIELDS:
        if not ENC_AVAILABLE:
            return "(encrypted - key not available)"
        try:
            decrypted = encryptor.decrypt(str(value))
            # Mask for display (show last 4 chars only)
            if field_name == 'ssn_encrypted' and len(decrypted) >= 4:
                return f"***-**-{decrypted[-4:]}"
            elif field_name in ('bank_routing_encrypted', 'bank_account_encrypted'):
                return f"****{decrypted[-4:]}" if len(decrypted) >= 4 else "****"
            return decrypted
        except Exception:
            return "(decryption failed)"

    if field_name == 'mailing_same_as_home':
        return "Yes" if value else "No"
    if field_name in ('is_accredited', 'accreditation_docs_on_file'):
        return "Yes" if value else "No"

    return str(value)


def display_profile(profile):
    """Display the full profile organized by section."""
    print()
    for section_name, fields in SECTIONS.items():
        print(f"  {section_name}")
        print(f"  {'-' * len(section_name)}")
        for field in fields:
            label = field.replace('_encrypted', '').replace('_', ' ').title()
            value = profile.get(field)
            display = display_value(field, value)
            print(f"    {label:30s}  {display}")
        print()


def edit_section(conn, profile, section_name, fields, investor_id):
    """Interactive editing of a profile section."""
    print(f"\nEditing: {section_name}")
    print("-" * 40)

    updates = {}
    for field in fields:
        label = field.replace('_encrypted', '').replace('_', ' ').title()
        current = display_value(field, profile.get(field))

        new_val = input(f"  {label} [{current}]: ").strip()

        if not new_val:
            continue  # Keep existing value

        # Encrypt sensitive fields
        if field in ENCRYPTED_FIELDS and ENC_AVAILABLE:
            new_val = encryptor.encrypt(new_val)

        updates[field] = new_val

    if not updates:
        print("  No changes made.")
        return

    # Apply updates
    now = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [now, investor_id]

    conn.execute(
        f"UPDATE investor_profiles SET {set_clause}, updated_at = ? WHERE investor_id = ?",
        params,
    )
    conn.commit()
    print(f"\n  Updated {len(updates)} field(s).")


def check_completion(profile):
    """Check profile completeness."""
    required_fields = [
        'full_legal_name', 'home_address_line1', 'home_city',
        'home_state', 'home_zip', 'email_primary', 'phone_mobile',
        'date_of_birth', 'citizenship',
    ]
    filled = sum(1 for f in required_fields if profile.get(f))
    total = len(required_fields)
    pct = (filled / total * 100) if total > 0 else 0

    missing = [f.replace('_', ' ').title() for f in required_fields if not profile.get(f)]

    return {
        'filled': filled,
        'total': total,
        'percent': pct,
        'missing': missing,
    }


def manage_profile():
    """Main interactive profile management flow."""
    parser = argparse.ArgumentParser(description="Manage investor profile")
    parser.add_argument('--investor', help="Investor ID (skip selection)")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("INVESTOR PROFILE MANAGEMENT")
    print("=" * 60)

    if not ENC_AVAILABLE:
        print("\nNote: Encryption not available (set ENCRYPTION_KEY in .env)")
        print("Sensitive fields will not be decryptable.\n")

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

            print("\nActive Investors:")
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

        # Get/create profile
        profile = get_or_create_profile(conn, investor_id)

        while True:
            print()
            print(f"PROFILE: {investor_id}")
            print("=" * 60)
            display_profile(profile)

            # Show completion
            completion = check_completion(profile)
            print(f"Profile Completion: {completion['percent']:.0f}% "
                  f"({completion['filled']}/{completion['total']} required fields)")
            if completion['missing']:
                print(f"  Missing: {', '.join(completion['missing'][:5])}")
            print()

            # Action menu
            print("Actions:")
            print("  1. Edit Contact Information")
            print("  2. Edit Personal Information")
            print("  3. Edit Employment Information")
            print("  4. Edit Sensitive / Banking")
            print("  5. Edit Accreditation")
            print("  6. Edit Preferences")
            print("  7. Mark Profile as Complete")
            print("  q. Quit")
            print()

            action = input("Select action: ").strip().lower()

            if action == 'q':
                break
            elif action == '7':
                if completion['percent'] >= 80:
                    conn.execute(
                        "UPDATE investor_profiles SET profile_completed = 1, updated_at = ? WHERE investor_id = ?",
                        (datetime.now().isoformat(), investor_id)
                    )
                    conn.commit()
                    print("Profile marked as complete.")
                else:
                    print(f"Profile only {completion['percent']:.0f}% complete. "
                          f"Fill required fields first.")
                profile = get_or_create_profile(conn, investor_id)
            elif action in ('1', '2', '3', '4', '5', '6'):
                section_names = list(SECTIONS.keys())
                section_idx = int(action) - 1
                section_name = section_names[section_idx]
                fields = SECTIONS[section_name]
                edit_section(conn, profile, section_name, fields, investor_id)
                profile = get_or_create_profile(conn, investor_id)
            else:
                print("Invalid choice.")

        return True

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        return False
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        success = manage_profile()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nExiting.")
        sys.exit(0)
