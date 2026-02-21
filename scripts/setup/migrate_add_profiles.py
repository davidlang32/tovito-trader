"""
Database Migration - Investor Profiles & Referrals

Adds tables for comprehensive investor profiles (with encrypted PII)
and referral tracking.

Run once to add the tables to your database.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))


def get_database_path():
    """Get database path"""
    return PROJECT_DIR / 'data' / 'tovito.db'


def migrate():
    """Add investor_profiles and referrals tables"""

    db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    print("=" * 70)
    print("DATABASE MIGRATION - INVESTOR PROFILES & REFERRALS")
    print("=" * 70)
    print()
    print("This will add two tables:")
    print("  1. investor_profiles  — Comprehensive KYC profile data")
    print("     (contact, personal, employment, sensitive PII encrypted)")
    print("  2. referrals          — Referral code tracking and incentives")
    print()
    print("Sensitive fields (SSN, bank routing, etc.) use application-level")
    print("encryption via the ENCRYPTION_KEY in .env.")
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

        # --- investor_profiles table ---
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'investor_profiles'
        """)
        if cursor.fetchone():
            print("Warning: investor_profiles table already exists")
            overwrite = input("Continue anyway? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                conn.close()
                return False
            print()

        print("Creating investor_profiles table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investor_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                investor_id TEXT NOT NULL UNIQUE,

                -- Contact Information
                full_legal_name TEXT,
                home_address_line1 TEXT,
                home_address_line2 TEXT,
                home_city TEXT,
                home_state TEXT,
                home_zip TEXT,
                home_country TEXT DEFAULT 'US',
                mailing_same_as_home INTEGER DEFAULT 1,
                mailing_address_line1 TEXT,
                mailing_address_line2 TEXT,
                mailing_city TEXT,
                mailing_state TEXT,
                mailing_zip TEXT,
                mailing_country TEXT,
                email_primary TEXT,
                phone_mobile TEXT,
                phone_home TEXT,
                phone_work TEXT,

                -- Personal Information
                date_of_birth TEXT,
                marital_status TEXT CHECK (marital_status IN (
                    'single', 'married', 'divorced', 'widowed', 'domestic_partnership', NULL
                )),
                num_dependents INTEGER DEFAULT 0,
                citizenship TEXT DEFAULT 'US',

                -- Employment Information
                employment_status TEXT CHECK (employment_status IN (
                    'employed', 'self_employed', 'retired', 'unemployed', 'student', NULL
                )),
                occupation TEXT,
                job_title TEXT,
                employer_name TEXT,
                employer_address TEXT,

                -- Sensitive PII (Application-level encrypted via Fernet)
                ssn_encrypted TEXT,
                tax_id_encrypted TEXT,
                bank_routing_encrypted TEXT,
                bank_account_encrypted TEXT,
                bank_name TEXT,
                bank_account_type TEXT CHECK (bank_account_type IN ('checking', 'savings', NULL)),

                -- Accreditation
                is_accredited INTEGER DEFAULT 0,
                accreditation_method TEXT,
                accreditation_verified_date DATE,
                accreditation_expires_date DATE,
                accreditation_docs_on_file INTEGER DEFAULT 0,

                -- Preferences
                communication_preference TEXT DEFAULT 'email'
                    CHECK (communication_preference IN ('email', 'phone', 'mail')),
                statement_delivery TEXT DEFAULT 'electronic'
                    CHECK (statement_delivery IN ('electronic', 'paper', 'both')),

                -- Metadata
                profile_completed INTEGER DEFAULT 0,
                last_verified_date DATE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
            )
        """)
        print("   investor_profiles table created")

        # --- referrals table ---
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'referrals'
        """)
        if cursor.fetchone():
            print("Warning: referrals table already exists")
            print("   Skipping referrals creation")
        else:
            print("Creating referrals table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Referrer
                    referrer_investor_id TEXT NOT NULL,
                    referral_code TEXT NOT NULL UNIQUE,

                    -- Referred person
                    referred_name TEXT,
                    referred_email TEXT,
                    referred_date DATE NOT NULL,

                    -- Outcome
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'contacted', 'onboarded', 'expired', 'declined')),
                    converted_investor_id TEXT,
                    converted_date DATE,

                    -- Incentive
                    incentive_type TEXT,
                    incentive_amount REAL,
                    incentive_paid INTEGER DEFAULT 0,
                    incentive_paid_date DATE,

                    -- Metadata
                    notes TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (referrer_investor_id) REFERENCES investors(investor_id),
                    FOREIGN KEY (converted_investor_id) REFERENCES investors(investor_id)
                )
            """)
            print("   referrals table created")

        # --- Create indexes ---
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_profiles_investor
            ON investor_profiles(investor_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer
            ON referrals(referrer_investor_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_referrals_code
            ON referrals(referral_code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_referrals_status
            ON referrals(status)
        """)
        print("   Indexes created")

        # --- Create profile stubs for existing active investors ---
        print("Creating profile stubs for existing investors...")
        cursor.execute("""
            SELECT investor_id, name, email, phone FROM investors
            WHERE status = 'Active'
        """)
        investors = cursor.fetchall()

        stubs_created = 0
        for inv in investors:
            inv_id = inv[0]
            # Check if profile already exists
            cursor.execute(
                "SELECT profile_id FROM investor_profiles WHERE investor_id = ?",
                (inv_id,)
            )
            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO investor_profiles (
                    investor_id, full_legal_name, email_primary, phone_mobile
                ) VALUES (?, ?, ?, ?)
            """, (inv_id, inv[1], inv[2], inv[3]))
            stubs_created += 1

        if stubs_created:
            print(f"   Created {stubs_created} profile stub(s)")
        else:
            print("   No new stubs needed")

        conn.commit()

        # --- Check encryption key ---
        print()
        print("Checking encryption key...")
        import os
        from dotenv import load_dotenv
        load_dotenv()

        enc_key = os.getenv('ENCRYPTION_KEY')
        if enc_key:
            print("   ENCRYPTION_KEY found in .env")
        else:
            print("   WARNING: ENCRYPTION_KEY not found in .env")
            print("   Sensitive fields will not be usable until key is configured.")
            print()
            generate = input("Generate encryption key now? (yes/no): ").strip().lower()
            if generate in ('yes', 'y'):
                from src.utils.encryption import FieldEncryptor
                new_key = FieldEncryptor.generate_key()
                print()
                print(f"   Generated key: {new_key}")
                print()
                print("   Add this to your .env file:")
                print(f"   ENCRYPTION_KEY={new_key}")
                print()
                print("   IMPORTANT: Back up this key separately!")
            else:
                print("   You can generate later: python src/utils/encryption.py")

        # Verify
        print()
        print("Verifying migration...")
        for table in ['investor_profiles', 'referrals']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count} rows")

        conn.close()

        print()
        print("=" * 70)
        print("MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("New tables:")
        print("  investor_profiles — KYC data, encrypted PII, accreditation")
        print("  referrals         — Referral codes, tracking, incentives")
        print()
        print("Next steps:")
        print("  1. Set ENCRYPTION_KEY in .env (if not done)")
        print("  2. Manage profiles: python scripts/investor/manage_profile.py")
        print("  3. Generate codes:  python scripts/investor/generate_referral_code.py")
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
