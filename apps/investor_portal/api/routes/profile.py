"""
Investor Profile API Routes
=============================

Endpoints for viewing and updating investor profile data.
Sensitive fields (SSN, bank info) are NEVER returned via API —
only "on file" / "not on file" status is shown.

Endpoints:
    GET  /profile             — View investor profile
    PUT  /profile/contact     — Update contact information
    PUT  /profile/personal    — Update personal information
    PUT  /profile/employment  — Update employment information
    GET  /profile/completion  — Check profile completeness
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..dependencies import get_current_user, CurrentUser
from ..models.database import get_connection

router = APIRouter()


# ============================================================
# MODELS
# ============================================================

class ContactInfo(BaseModel):
    """Contact information for update."""
    full_legal_name: Optional[str] = None
    home_address_line1: Optional[str] = None
    home_address_line2: Optional[str] = None
    home_city: Optional[str] = None
    home_state: Optional[str] = None
    home_zip: Optional[str] = None
    home_country: Optional[str] = None
    email_primary: Optional[str] = None
    phone_mobile: Optional[str] = None
    phone_home: Optional[str] = None
    phone_work: Optional[str] = None


class PersonalInfo(BaseModel):
    """Personal information for update."""
    marital_status: Optional[str] = None
    num_dependents: Optional[int] = None
    citizenship: Optional[str] = None


class EmploymentInfo(BaseModel):
    """Employment information for update."""
    employment_status: Optional[str] = None
    occupation: Optional[str] = None
    job_title: Optional[str] = None
    employer_name: Optional[str] = None
    employer_address: Optional[str] = None


class ProfileResponse(BaseModel):
    """Profile data returned to the investor."""
    investor_id: str
    # Contact
    full_legal_name: Optional[str] = None
    home_address_line1: Optional[str] = None
    home_address_line2: Optional[str] = None
    home_city: Optional[str] = None
    home_state: Optional[str] = None
    home_zip: Optional[str] = None
    home_country: Optional[str] = None
    email_primary: Optional[str] = None
    phone_mobile: Optional[str] = None
    phone_home: Optional[str] = None
    phone_work: Optional[str] = None
    # Personal
    marital_status: Optional[str] = None
    num_dependents: Optional[int] = None
    citizenship: Optional[str] = None
    # Employment
    employment_status: Optional[str] = None
    occupation: Optional[str] = None
    job_title: Optional[str] = None
    employer_name: Optional[str] = None
    employer_address: Optional[str] = None
    # Sensitive fields: only show if on file (never the actual value)
    ssn_on_file: bool = False
    bank_on_file: bool = False
    # Accreditation
    is_accredited: bool = False
    accreditation_method: Optional[str] = None
    # Preferences
    communication_preference: str = "email"
    statement_delivery: str = "electronic"
    # Completion
    profile_completed: bool = False


class CompletionResponse(BaseModel):
    """Profile completion status."""
    percent: float
    filled: int
    total: int
    missing: list


# ============================================================
# HELPERS
# ============================================================

REQUIRED_FIELDS = [
    'full_legal_name', 'home_address_line1', 'home_city',
    'home_state', 'home_zip', 'email_primary', 'phone_mobile',
    'citizenship',
]


def get_or_create_profile(investor_id: str) -> dict:
    """Get profile or create a stub."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM investor_profiles WHERE investor_id = ?",
            (investor_id,)
        )
        row = cursor.fetchone()

        if row:
            return dict(row)

        conn.execute(
            "INSERT INTO investor_profiles (investor_id) VALUES (?)",
            (investor_id,)
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT * FROM investor_profiles WHERE investor_id = ?",
            (investor_id,)
        )
        return dict(cursor.fetchone())
    finally:
        conn.close()


def update_profile_fields(investor_id: str, fields: dict):
    """Update specified fields in investor_profiles."""
    if not fields:
        return

    conn = get_connection()
    try:
        # Filter out None values (only update provided fields)
        updates = {k: v for k, v in fields.items() if v is not None}
        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [investor_id]

        conn.execute(
            f"UPDATE investor_profiles SET {set_clause}, "
            f"updated_at = datetime('now') WHERE investor_id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("", response_model=ProfileResponse)
async def get_profile(user: CurrentUser = Depends(get_current_user)):
    """
    Get the authenticated investor's profile.

    Sensitive fields (SSN, bank details) are never returned —
    only whether they are on file.
    """
    profile = get_or_create_profile(user.investor_id)

    return ProfileResponse(
        investor_id=user.investor_id,
        full_legal_name=profile.get('full_legal_name'),
        home_address_line1=profile.get('home_address_line1'),
        home_address_line2=profile.get('home_address_line2'),
        home_city=profile.get('home_city'),
        home_state=profile.get('home_state'),
        home_zip=profile.get('home_zip'),
        home_country=profile.get('home_country'),
        email_primary=profile.get('email_primary'),
        phone_mobile=profile.get('phone_mobile'),
        phone_home=profile.get('phone_home'),
        phone_work=profile.get('phone_work'),
        marital_status=profile.get('marital_status'),
        num_dependents=profile.get('num_dependents'),
        citizenship=profile.get('citizenship'),
        employment_status=profile.get('employment_status'),
        occupation=profile.get('occupation'),
        job_title=profile.get('job_title'),
        employer_name=profile.get('employer_name'),
        employer_address=profile.get('employer_address'),
        ssn_on_file=bool(profile.get('ssn_encrypted')),
        bank_on_file=bool(profile.get('bank_account_encrypted')),
        is_accredited=bool(profile.get('is_accredited')),
        accreditation_method=profile.get('accreditation_method'),
        communication_preference=profile.get('communication_preference') or 'email',
        statement_delivery=profile.get('statement_delivery') or 'electronic',
        profile_completed=bool(profile.get('profile_completed')),
    )


@router.put("/contact")
async def update_contact(
    data: ContactInfo,
    user: CurrentUser = Depends(get_current_user),
):
    """Update contact information section of the profile."""
    update_profile_fields(user.investor_id, data.model_dump(exclude_none=True))
    return {"message": "Contact information updated"}


@router.put("/personal")
async def update_personal(
    data: PersonalInfo,
    user: CurrentUser = Depends(get_current_user),
):
    """Update personal information section of the profile."""
    # Validate enums
    valid_marital = {'single', 'married', 'divorced', 'widowed', 'domestic_partnership'}
    if data.marital_status and data.marital_status not in valid_marital:
        raise HTTPException(
            status_code=400,
            detail=f"marital_status must be one of: {', '.join(valid_marital)}"
        )

    update_profile_fields(user.investor_id, data.model_dump(exclude_none=True))
    return {"message": "Personal information updated"}


@router.put("/employment")
async def update_employment(
    data: EmploymentInfo,
    user: CurrentUser = Depends(get_current_user),
):
    """Update employment information section of the profile."""
    valid_statuses = {'employed', 'self_employed', 'retired', 'unemployed', 'student'}
    if data.employment_status and data.employment_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"employment_status must be one of: {', '.join(valid_statuses)}"
        )

    update_profile_fields(user.investor_id, data.model_dump(exclude_none=True))
    return {"message": "Employment information updated"}


@router.get("/completion", response_model=CompletionResponse)
async def get_completion(user: CurrentUser = Depends(get_current_user)):
    """Check profile completeness and identify missing fields."""
    profile = get_or_create_profile(user.investor_id)

    filled = sum(1 for f in REQUIRED_FIELDS if profile.get(f))
    total = len(REQUIRED_FIELDS)
    pct = (filled / total * 100) if total > 0 else 0
    missing = [
        f.replace('_', ' ').title()
        for f in REQUIRED_FIELDS
        if not profile.get(f)
    ]

    return CompletionResponse(
        percent=round(pct, 1),
        filled=filled,
        total=total,
        missing=missing,
    )
