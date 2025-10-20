from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum

class TransferType(str, Enum):
    FULL = "full"
    PARTIAL = "partial"

class AssetType(str, Enum):
    EQUITY = "equity"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    OPTION = "option"
    CASH = "cash"

class Security(BaseModel):
    cusip: str = Field(..., min_length=9, max_length=9, description="9-character CUSIP identifier")
    symbol: Optional[str] = Field(None, max_length=10, description="Trading symbol")
    description: str = Field(..., max_length=50, description="Security description")
    quantity: int = Field(..., gt=0, description="Number of shares/units")
    asset_type: AssetType = Field(..., description="Type of asset")
    
    @validator('cusip')
    def validate_cusip(cls, v):
        if not v.isalnum():
            raise ValueError('CUSIP must contain only alphanumeric characters')
        return v.upper()

class CustomerInfo(BaseModel):
    first_name: str = Field(..., max_length=50, description="Customer first name")
    last_name: str = Field(..., max_length=50, description="Customer last name")
    ssn: Optional[str] = Field(None, regex=r'^\d{3}-\d{2}-\d{4}$', description="Social Security Number")
    tax_id: Optional[str] = Field(None, max_length=20, description="Tax identification number")
    date_of_birth: Optional[datetime] = Field(None, description="Customer date of birth")

class ACATRequest(BaseModel):
    # Account Information
    delivering_account: str = Field(..., min_length=1, max_length=20, description="Delivering firm account number")
    receiving_account: str = Field(..., min_length=1, max_length=20, description="Receiving firm account number")
    contra_firm: str = Field(..., min_length=4, max_length=4, description="4-digit DTCC participant number")
    
    # Transfer Details
    transfer_type: TransferType = Field(..., description="Type of transfer (full or partial)")
    transfer_date: datetime = Field(default_factory=datetime.now, description="Requested transfer date")
    
    # Securities
    securities: List[Security] = Field(..., min_items=1, description="List of securities to transfer")
    
    # Customer Information
    customer: CustomerInfo = Field(..., description="Customer information")
    
    # Special Instructions
    special_instructions: Optional[str] = Field(None, max_length=500, description="Special handling instructions")
    account_type: Optional[str] = Field(None, max_length=20, description="Account type (individual, joint, etc.)")
    
    # Validation
    @validator('contra_firm')
    def validate_contra_firm(cls, v):
        if not v.isdigit():
            raise ValueError('Contra firm must be a 4-digit number')
        return v
    
    @validator('delivering_account', 'receiving_account')
    def validate_account_numbers(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Account numbers must be alphanumeric')
        return v

class CorrectionSuggestion(BaseModel):
    field: str = Field(..., description="Field that needs correction")
    current_value: str = Field(..., description="Current value")
    suggested_value: str = Field(..., description="Suggested corrected value")
    reason: str = Field(..., description="Explanation for the correction")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    severity: Literal["low", "medium", "high"] = Field(..., description="Severity of the issue")

class ACATValidationResponse(BaseModel):
    is_valid: bool = Field(..., description="Whether the ACAT data is valid")
    suggestions: List[CorrectionSuggestion] = Field(default_factory=list, description="List of correction suggestions")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    success_probability: float = Field(..., ge=0.0, le=1.0, description="Estimated success probability")
    ai_analysis: str = Field(..., description="AI analysis summary")

class ACATSubmissionRequest(BaseModel):
    acat_data: ACATRequest = Field(..., description="ACAT data to submit")
    accepted_suggestions: List[str] = Field(default_factory=list, description="List of accepted suggestion field names")
    custom_modifications: dict = Field(default_factory=dict, description="Custom field modifications")


class ACATStatus(str, Enum):
    NEW = "new"
    SUBMITTED = "submitted"
    PENDING_REVIEW = "pending_review"
    PENDING_CLIENT = "pending_client"
    PENDING_DELIVERING = "pending_delivering"
    PENDING_RECEIVING = "pending_receiving"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ACATRecord(BaseModel):
    id: str = Field(..., description="Unique ACAT tracking identifier")
    status: ACATStatus = Field(default=ACATStatus.NEW, description="Current DTCC-related status")
    acat_data: ACATRequest = Field(..., description="Underlying ACAT request payload")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status_history: List[dict] = Field(default_factory=list, description="History of status changes with reasons")


class UserRole(str, Enum):
    READ_ONLY = "read_only"
    FULL = "full"
    OWNER = "owner"


class User(BaseModel):
    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password_hash: str = Field(..., description="Hashed password")
    first_name: str = Field(..., min_length=1, max_length=50, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User's last name")
    email: str = Field(..., description="User email address")
    phone_number: Optional[str] = Field(None, description="User phone number")
    role: UserRole = Field(..., description="User role/permissions")
    is_approved: bool = Field(default=False, description="Whether account is approved by owner")
    is_onboarded: bool = Field(default=False, description="Whether user has completed onboarding")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    approved_by: Optional[str] = Field(None, description="Username of owner who approved account")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    first_name: str = Field(..., min_length=1, max_length=50, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User's last name")
    email: str = Field(..., description="User email address")
    phone_number: Optional[str] = Field(None, description="User phone number")
    role: UserRole = Field(..., description="User role/permissions")


class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    USER_CREATION = "user_creation"
    ROLE_SELECTION = "role_selection"
    SETUP_COMPLETE = "setup_complete"


class StatusUpdateRequest(BaseModel):
    status: ACATStatus = Field(..., description="New status")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for status change")
    updated_by: str = Field(..., description="User who made the change")
