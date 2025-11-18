from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Literal, Union
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

class DTCCAccountType(str, Enum):
    """DTCC account type definitions for ACAT transfers"""
    INDIVIDUAL = "individual"
    JOINT = "joint"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    SEP_IRA = "sep_ira"
    SIMPLE_IRA = "simple_ira"
    ROLLOVER_IRA = "rollover_ira"
    K401 = "401k"
    CORPORATE = "corporate"
    TRUST = "trust"
    CUSTODIAL = "custodial"
    PARTNERSHIP = "partnership"
    MEDICAL_SAVINGS_ACCOUNT = "medical_savings_account"
    DIRECT_ROLLOVER = "direct_rollover"
    MARGIN = "margin"
    CASH = "cash"

class Security(BaseModel):
    """Legacy class - use Position instead"""
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

class Position(BaseModel):
    """Position in an account - represents a security holding"""
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
    user_account_number: str = Field(..., min_length=1, max_length=20, description="User account number assigned by the delivering firm")
    contra_firm: str = Field(..., min_length=4, max_length=4, description="4-digit DTCC participant number")
    
    # Transfer Details
    transfer_type: TransferType = Field(..., description="Type of transfer (full or partial)")
    transfer_date: datetime = Field(default_factory=datetime.now, description="Requested transfer date")
    
    # Positions (list of positions to transfer)
    positions: Optional[List[Position]] = Field(None, min_items=1, description="List of positions to transfer")
    
    # Legacy support - securities field for backward compatibility
    securities: Optional[List[Security]] = Field(None, description="Legacy field - use positions instead")
    
    # Customer Information
    customer: CustomerInfo = Field(..., description="Customer information")
    
    # Account Type (DTCC definitions)
    account_type: DTCCAccountType = Field(..., description="DTCC account type")
    
    # Special Instructions
    special_instructions: Optional[str] = Field(None, max_length=500, description="Special handling instructions")
    
    # Validation
    @validator('contra_firm')
    def validate_contra_firm(cls, v):
        if not v.isdigit():
            raise ValueError('Contra firm must be a 4-digit number')
        return v
    
    @validator('delivering_account', 'receiving_account', 'user_account_number')
    def validate_account_numbers(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Account numbers must be alphanumeric')
        return v
    
    @root_validator
    def ensure_positions_or_securities(cls, values):
        """Ensure either positions or securities is provided, and convert securities to positions if needed"""
        positions = values.get('positions')
        securities = values.get('securities')
        
        # Check if we have any positions or securities
        has_positions = positions and len(positions) > 0
        has_securities = securities and len(securities) > 0
        
        if not has_positions and not has_securities:
            raise ValueError('Either positions or securities must be provided with at least one item')
        
        # If positions is not provided but securities is, convert securities to positions
        if not has_positions and has_securities:
            converted_positions = []
            for sec in securities:
                if isinstance(sec, Security):
                    converted_positions.append(Position(
                        cusip=sec.cusip,
                        symbol=sec.symbol,
                        description=sec.description,
                        quantity=sec.quantity,
                        asset_type=sec.asset_type
                    ))
                elif isinstance(sec, dict):
                    converted_positions.append(Position(
                        cusip=sec['cusip'],
                        symbol=sec.get('symbol'),
                        description=sec['description'],
                        quantity=sec['quantity'],
                        asset_type=AssetType(sec['asset_type'])
                    ))
            values['positions'] = converted_positions
        
        return values

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

class RejectionType(str, Enum):
    """Type of rejection - soft rejections can be fixed and resubmitted"""
    SOFT = "soft"  # Can be fixed and resubmitted
    HARD = "hard"  # Permanent rejection, cannot be resubmitted


class ACATRecord(BaseModel):
    id: str = Field(..., description="Unique ACAT tracking identifier")
    status: ACATStatus = Field(default=ACATStatus.NEW, description="Current DTCC-related status")
    acat_data: ACATRequest = Field(..., description="Underlying ACAT request payload")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status_history: List[dict] = Field(default_factory=list, description="History of status changes with reasons")
    rejection_type: Optional[RejectionType] = Field(None, description="Type of rejection if status is REJECTED")
    in_queue: bool = Field(default=False, description="Whether this ACAT is in the soft rejection queue")
    queue_claimed_by: Optional[str] = Field(None, description="Username of user who claimed this item from queue")
    queue_claimed_at: Optional[datetime] = Field(None, description="When this item was claimed from queue")


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
    password: Optional[str] = Field(None, description="User password for verification")
    session_id: Optional[str] = Field(None, description="User session ID")
    rejection_type: Optional[RejectionType] = Field(None, description="Type of rejection if status is REJECTED")

class QueueItem(BaseModel):
    """Represents an item in the soft rejection queue"""
    acat_record: ACATRecord = Field(..., description="The ACAT record in the queue")
    rejection_reason: str = Field(..., description="Reason for rejection")
    rejection_date: datetime = Field(..., description="When the rejection occurred")
    claimed_by: Optional[str] = Field(None, description="Username of user who claimed this item")
    claimed_at: Optional[datetime] = Field(None, description="When this item was claimed")
    priority: int = Field(default=0, description="Priority level (higher = more urgent)")

class QueueClaimRequest(BaseModel):
    """Request to claim an item from the queue"""
    record_id: str = Field(..., description="ACAT record ID to claim")
    session_id: str = Field(..., description="User session ID")

class QueueUpdateRequest(BaseModel):
    """Request to update an ACAT in the queue"""
    record_id: str = Field(..., description="ACAT record ID")
    updated_acat_data: ACATRequest = Field(..., description="Updated ACAT data")
    session_id: str = Field(..., description="User session ID")
    notes: Optional[str] = Field(None, max_length=1000, description="Notes about the update")
