"""
Tests for investor profiles and referral tracking.

Covers:
- Profile CRUD operations
- Encrypted field storage and retrieval
- Profile completion tracking
- Referral code generation and uniqueness
- Referral lifecycle (status transitions)
- Edge cases and constraints
"""

import sqlite3
import os
import pytest
from datetime import date, datetime
from cryptography.fernet import Fernet

from src.utils.encryption import FieldEncryptor

TEST_DB_PATH = "data/test_tovito.db"


@pytest.fixture
def profile_db(test_db):
    """
    Test database with investors and investor_profiles table populated.
    Uses the test_db fixture which creates the full schema.
    """
    now = datetime.now().isoformat()

    # Insert test investors
    test_db.execute("""
        INSERT INTO investors (id, name, initial_capital, join_date, status,
                               current_shares, net_investment, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('INV-001', 'Test Investor A', 10000, '2026-01-01', 'Active',
          10000, 10000, now, now))

    test_db.execute("""
        INSERT INTO investors (id, name, initial_capital, join_date, status,
                               current_shares, net_investment, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('INV-002', 'Test Investor B', 25000, '2026-01-15', 'Active',
          25000, 25000, now, now))

    test_db.execute("""
        INSERT INTO investors (id, name, initial_capital, join_date, status,
                               current_shares, net_investment, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('INV-003', 'Test Investor C', 5000, '2026-02-01', 'Inactive',
          0, 5000, now, now))

    test_db.commit()
    return test_db


@pytest.fixture
def encryptor():
    """Create a FieldEncryptor with a test key."""
    key = Fernet.generate_key().decode('utf-8')
    return FieldEncryptor(key=key)


# ============================================================
# PROFILE CREATION & BASIC CRUD
# ============================================================

class TestProfileCreation:
    """Tests for creating and reading investor profiles."""

    def test_create_profile_stub(self, profile_db):
        """Creating a profile stub links it to an existing investor."""
        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id, email_primary)
            VALUES (?, ?)
        """, ('INV-001', 'investor_a@test.com'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT * FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['investor_id'] == 'INV-001'
        assert row['email_primary'] == 'investor_a@test.com'
        assert row['profile_completed'] == 0

    def test_investor_id_unique_constraint(self, profile_db):
        """Only one profile per investor (UNIQUE constraint)."""
        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id) VALUES (?)
        """, ('INV-001',))
        profile_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            profile_db.execute("""
                INSERT INTO investor_profiles (investor_id) VALUES (?)
            """, ('INV-001',))

    def test_update_contact_info(self, profile_db):
        """Updating contact fields persists correctly."""
        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id) VALUES (?)
        """, ('INV-001',))
        profile_db.commit()

        profile_db.execute("""
            UPDATE investor_profiles
            SET full_legal_name = ?,
                home_address_line1 = ?,
                home_city = ?,
                home_state = ?,
                home_zip = ?,
                phone_mobile = ?,
                updated_at = datetime('now')
            WHERE investor_id = ?
        """, ('Test Legal Name', '123 Main St', 'Springfield', 'IL',
              '62701', '555-123-4567', 'INV-001'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT * FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        row = cursor.fetchone()
        assert row['full_legal_name'] == 'Test Legal Name'
        assert row['home_city'] == 'Springfield'
        assert row['home_state'] == 'IL'
        assert row['phone_mobile'] == '555-123-4567'

    def test_defaults_applied(self, profile_db):
        """Default values are set correctly on creation."""
        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id) VALUES (?)
        """, ('INV-001',))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT * FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        row = cursor.fetchone()
        assert row['home_country'] == 'US'
        assert row['mailing_same_as_home'] == 1
        assert row['num_dependents'] == 0
        assert row['citizenship'] == 'US'
        assert row['is_accredited'] == 0
        assert row['communication_preference'] == 'email'
        assert row['statement_delivery'] == 'electronic'
        assert row['profile_completed'] == 0


# ============================================================
# ENCRYPTED FIELD STORAGE
# ============================================================

class TestEncryptedFieldStorage:
    """Tests for storing and retrieving encrypted PII fields."""

    def test_ssn_encrypt_store_decrypt(self, profile_db, encryptor):
        """SSN round-trip: encrypt → store → retrieve → decrypt."""
        ssn = "123-45-6789"
        encrypted_ssn = encryptor.encrypt(ssn)

        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id, ssn_encrypted)
            VALUES (?, ?)
        """, ('INV-001', encrypted_ssn))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT ssn_encrypted FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        stored = cursor.fetchone()['ssn_encrypted']

        # Stored value should look encrypted
        assert stored != ssn
        assert FieldEncryptor.is_encrypted(stored)

        # Decrypt should recover original
        assert encryptor.decrypt(stored) == ssn

    def test_bank_details_encrypt_store_decrypt(self, profile_db, encryptor):
        """Bank routing and account numbers round-trip encryption."""
        routing = "021000021"
        account = "1234567890"

        enc_routing = encryptor.encrypt(routing)
        enc_account = encryptor.encrypt(account)

        profile_db.execute("""
            INSERT INTO investor_profiles
                (investor_id, bank_routing_encrypted, bank_account_encrypted, bank_name)
            VALUES (?, ?, ?, ?)
        """, ('INV-001', enc_routing, enc_account, 'Test Bank'))
        profile_db.commit()

        cursor = profile_db.execute(
            """SELECT bank_routing_encrypted, bank_account_encrypted, bank_name
               FROM investor_profiles WHERE investor_id = ?""",
            ('INV-001',)
        )
        row = cursor.fetchone()

        assert encryptor.decrypt(row['bank_routing_encrypted']) == routing
        assert encryptor.decrypt(row['bank_account_encrypted']) == account
        # Bank name is plain text (not sensitive alone)
        assert row['bank_name'] == 'Test Bank'

    def test_encrypted_fields_not_readable_plain(self, profile_db, encryptor):
        """Encrypted values stored in DB should not contain the plaintext."""
        ssn = "987-65-4321"
        encrypted_ssn = encryptor.encrypt(ssn)

        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id, ssn_encrypted)
            VALUES (?, ?)
        """, ('INV-001', encrypted_ssn))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT ssn_encrypted FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        stored = cursor.fetchone()['ssn_encrypted']

        # The plaintext SSN should NOT appear anywhere in the stored value
        assert ssn not in stored
        assert '987' not in stored
        assert '4321' not in stored

    def test_null_encrypted_fields(self, profile_db, encryptor):
        """Encrypted fields can be NULL (not all investors provide them)."""
        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id) VALUES (?)
        """, ('INV-001',))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT ssn_encrypted, bank_routing_encrypted FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        row = cursor.fetchone()
        assert row['ssn_encrypted'] is None
        assert row['bank_routing_encrypted'] is None

        # decrypt_or_none should handle this gracefully
        assert encryptor.decrypt_or_none(row['ssn_encrypted']) is None

    def test_wrong_key_cannot_decrypt_stored_data(self, profile_db):
        """Data encrypted with one key cannot be decrypted with another."""
        key1 = Fernet.generate_key().decode('utf-8')
        key2 = Fernet.generate_key().decode('utf-8')
        enc1 = FieldEncryptor(key=key1)
        enc2 = FieldEncryptor(key=key2)

        ssn = "111-22-3333"
        encrypted = enc1.encrypt(ssn)

        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id, ssn_encrypted)
            VALUES (?, ?)
        """, ('INV-001', encrypted))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT ssn_encrypted FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        stored = cursor.fetchone()['ssn_encrypted']

        # Wrong key should fail
        with pytest.raises(ValueError, match="Decryption failed"):
            enc2.decrypt(stored)

        # Right key should succeed
        assert enc1.decrypt(stored) == ssn


# ============================================================
# PROFILE COMPLETION
# ============================================================

class TestProfileCompletion:
    """Tests for profile completion tracking."""

    def test_incomplete_profile(self, profile_db):
        """A profile with only investor_id is incomplete."""
        profile_db.execute("""
            INSERT INTO investor_profiles (investor_id) VALUES (?)
        """, ('INV-001',))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT profile_completed FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        assert cursor.fetchone()['profile_completed'] == 0

    def test_mark_profile_completed(self, profile_db):
        """Profile can be marked as completed."""
        profile_db.execute("""
            INSERT INTO investor_profiles (
                investor_id, full_legal_name, home_address_line1,
                home_city, home_state, home_zip, email_primary,
                phone_mobile, date_of_birth, citizenship,
                profile_completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('INV-001', 'Test Name', '123 Main St',
              'Springfield', 'IL', '62701', 'test@test.com',
              '555-123-4567', 'encrypted_dob_value', 'US', 1))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT profile_completed FROM investor_profiles WHERE investor_id = ?",
            ('INV-001',)
        )
        assert cursor.fetchone()['profile_completed'] == 1

    def test_accreditation_fields(self, profile_db):
        """Accreditation fields can be set and retrieved."""
        profile_db.execute("""
            INSERT INTO investor_profiles (
                investor_id, is_accredited, accreditation_method,
                accreditation_verified_date, accreditation_expires_date,
                accreditation_docs_on_file
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ('INV-001', 1, 'income', '2026-01-15', '2027-01-15', 1))
        profile_db.commit()

        cursor = profile_db.execute(
            """SELECT is_accredited, accreditation_method,
                      accreditation_verified_date, accreditation_expires_date,
                      accreditation_docs_on_file
               FROM investor_profiles WHERE investor_id = ?""",
            ('INV-001',)
        )
        row = cursor.fetchone()
        assert row['is_accredited'] == 1
        assert row['accreditation_method'] == 'income'
        assert row['accreditation_verified_date'] == '2026-01-15'
        assert row['accreditation_expires_date'] == '2027-01-15'
        assert row['accreditation_docs_on_file'] == 1


# ============================================================
# REFERRAL CODE MANAGEMENT
# ============================================================

class TestReferralCodeGeneration:
    """Tests for referral code generation and uniqueness."""

    def test_create_referral(self, profile_db):
        """Basic referral creation stores all fields correctly."""
        profile_db.execute("""
            INSERT INTO referrals (
                referrer_investor_id, referral_code, referred_name,
                referred_email, referred_date, status
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ('INV-001', 'TOVITO-A1B2C3', 'Referred Person',
              'referred@test.com', '2026-03-01', 'pending'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT * FROM referrals WHERE referrer_investor_id = ?",
            ('INV-001',)
        )
        row = cursor.fetchone()
        assert row['referral_code'] == 'TOVITO-A1B2C3'
        assert row['referred_name'] == 'Referred Person'
        assert row['status'] == 'pending'

    def test_referral_code_unique(self, profile_db):
        """Referral codes must be unique."""
        profile_db.execute("""
            INSERT INTO referrals (referrer_investor_id, referral_code, referred_date)
            VALUES (?, ?, ?)
        """, ('INV-001', 'TOVITO-UNIQUE', '2026-03-01'))
        profile_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            profile_db.execute("""
                INSERT INTO referrals (referrer_investor_id, referral_code, referred_date)
                VALUES (?, ?, ?)
            """, ('INV-002', 'TOVITO-UNIQUE', '2026-03-15'))

    def test_multiple_referrals_per_investor(self, profile_db):
        """An investor can have multiple referral codes."""
        profile_db.execute("""
            INSERT INTO referrals (referrer_investor_id, referral_code, referred_date)
            VALUES (?, ?, ?)
        """, ('INV-001', 'TOVITO-CODE01', '2026-03-01'))
        profile_db.execute("""
            INSERT INTO referrals (referrer_investor_id, referral_code, referred_date)
            VALUES (?, ?, ?)
        """, ('INV-001', 'TOVITO-CODE02', '2026-03-15'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_investor_id = ?",
            ('INV-001',)
        )
        assert cursor.fetchone()['cnt'] == 2

    def test_referral_code_format(self, profile_db):
        """Referral codes follow TOVITO-XXXXXX pattern."""
        import re
        import secrets
        import string

        chars = string.ascii_uppercase + string.digits
        code = 'TOVITO-' + ''.join(secrets.choice(chars) for _ in range(6))

        # Verify format
        assert re.match(r'^TOVITO-[A-Z0-9]{6}$', code)

        # Store and retrieve
        profile_db.execute("""
            INSERT INTO referrals (referrer_investor_id, referral_code, referred_date)
            VALUES (?, ?, ?)
        """, ('INV-001', code, '2026-03-01'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT referral_code FROM referrals WHERE referrer_investor_id = ?",
            ('INV-001',)
        )
        assert cursor.fetchone()['referral_code'] == code


# ============================================================
# REFERRAL LIFECYCLE
# ============================================================

class TestReferralLifecycle:
    """Tests for referral status transitions and conversion tracking."""

    def test_status_transition_to_contacted(self, profile_db):
        """Referral can transition from pending to contacted."""
        profile_db.execute("""
            INSERT INTO referrals (referrer_investor_id, referral_code,
                                   referred_date, status)
            VALUES (?, ?, ?, 'pending')
        """, ('INV-001', 'TOVITO-LIFE01', '2026-03-01'))
        profile_db.commit()

        profile_db.execute("""
            UPDATE referrals SET status = 'contacted', updated_at = datetime('now')
            WHERE referral_code = ?
        """, ('TOVITO-LIFE01',))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT status FROM referrals WHERE referral_code = ?",
            ('TOVITO-LIFE01',)
        )
        assert cursor.fetchone()['status'] == 'contacted'

    def test_referral_conversion(self, profile_db):
        """Converted referral tracks the new investor ID and date."""
        profile_db.execute("""
            INSERT INTO referrals (
                referrer_investor_id, referral_code, referred_name,
                referred_date, status
            ) VALUES (?, ?, ?, ?, 'contacted')
        """, ('INV-001', 'TOVITO-CONV01', 'New Person', '2026-03-01'))
        profile_db.commit()

        # Convert the referral
        profile_db.execute("""
            UPDATE referrals
            SET status = 'onboarded',
                converted_investor_id = ?,
                converted_date = ?,
                updated_at = datetime('now')
            WHERE referral_code = ?
        """, ('INV-003', '2026-03-15', 'TOVITO-CONV01'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT * FROM referrals WHERE referral_code = ?",
            ('TOVITO-CONV01',)
        )
        row = cursor.fetchone()
        assert row['status'] == 'onboarded'
        assert row['converted_investor_id'] == 'INV-003'
        assert row['converted_date'] == '2026-03-15'

    def test_referral_incentive_tracking(self, profile_db):
        """Incentive can be recorded and marked as paid."""
        profile_db.execute("""
            INSERT INTO referrals (
                referrer_investor_id, referral_code, referred_date,
                status, incentive_type, incentive_amount
            ) VALUES (?, ?, ?, 'onboarded', 'fee_reduction', 500.00)
        """, ('INV-001', 'TOVITO-INCEN', '2026-03-01'))
        profile_db.commit()

        # Mark incentive as paid
        profile_db.execute("""
            UPDATE referrals
            SET incentive_paid = 1,
                incentive_paid_date = ?,
                updated_at = datetime('now')
            WHERE referral_code = ?
        """, ('2026-04-01', 'TOVITO-INCEN'))
        profile_db.commit()

        cursor = profile_db.execute(
            "SELECT * FROM referrals WHERE referral_code = ?",
            ('TOVITO-INCEN',)
        )
        row = cursor.fetchone()
        assert row['incentive_type'] == 'fee_reduction'
        assert row['incentive_amount'] == 500.00
        assert row['incentive_paid'] == 1
        assert row['incentive_paid_date'] == '2026-04-01'

    def test_referral_status_check_constraint(self, profile_db):
        """Referral status must be one of the valid values."""
        with pytest.raises(sqlite3.IntegrityError):
            profile_db.execute("""
                INSERT INTO referrals (
                    referrer_investor_id, referral_code, referred_date, status
                ) VALUES (?, ?, ?, 'invalid_status')
            """, ('INV-001', 'TOVITO-BADST', '2026-03-01'))

    def test_aggregate_referral_stats(self, profile_db):
        """Can calculate referral stats per investor."""
        # Insert multiple referrals with different statuses
        referrals = [
            ('INV-001', 'TOVITO-REF01', '2026-03-01', 'onboarded', 500.0, 1),
            ('INV-001', 'TOVITO-REF02', '2026-03-15', 'onboarded', 300.0, 0),
            ('INV-001', 'TOVITO-REF03', '2026-04-01', 'pending', None, 0),
            ('INV-001', 'TOVITO-REF04', '2026-04-15', 'declined', None, 0),
        ]
        for ref in referrals:
            profile_db.execute("""
                INSERT INTO referrals (
                    referrer_investor_id, referral_code, referred_date,
                    status, incentive_amount, incentive_paid
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, ref)
        profile_db.commit()

        # Total referrals
        cursor = profile_db.execute(
            "SELECT COUNT(*) as total FROM referrals WHERE referrer_investor_id = ?",
            ('INV-001',)
        )
        assert cursor.fetchone()['total'] == 4

        # Converted
        cursor = profile_db.execute(
            "SELECT COUNT(*) as converted FROM referrals WHERE referrer_investor_id = ? AND status = 'onboarded'",
            ('INV-001',)
        )
        assert cursor.fetchone()['converted'] == 2

        # Total incentive earned
        cursor = profile_db.execute(
            "SELECT COALESCE(SUM(incentive_amount), 0) as total_earned FROM referrals WHERE referrer_investor_id = ?",
            ('INV-001',)
        )
        assert cursor.fetchone()['total_earned'] == 800.0

        # Total incentive paid
        cursor = profile_db.execute(
            "SELECT COALESCE(SUM(incentive_amount), 0) as total_paid FROM referrals WHERE referrer_investor_id = ? AND incentive_paid = 1",
            ('INV-001',)
        )
        assert cursor.fetchone()['total_paid'] == 500.0
