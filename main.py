import os
import random
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

from models.acat import ACATRequest, ACATValidationResponse, ACATSubmissionRequest, Position, DTCCAccountType
from services.claude_service import ClaudeACATService
from services.validation_service import ACATValidationService
from services.tracking_service import InMemoryACATStore, AuditLog
from services.auth_service import SimpleAuthService
from services.learning_service import ContraFirmLearningService
from services.queue_service import SoftRejectionQueueService
from models.acat import ACATRecord, ACATStatus, StatusUpdateRequest, UserRole, UserCreateRequest, OnboardingStep, RejectionType, QueueItem, QueueClaimRequest, QueueUpdateRequest

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="ACAT Correction Service",
    description="AI-powered ACAT validation and correction service using Claude",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
claude_service = ClaudeACATService()
validation_service = ACATValidationService()
audit_log = AuditLog()
tracking_store = InMemoryACATStore(audit_log)
auth_service = SimpleAuthService()
learning_service = ContraFirmLearningService()
queue_service = SoftRejectionQueueService(tracking_store)

# Seed dummy data
def seed_dummy_data():
    from models.acat import ACATRequest, TransferType, Position, AssetType, CustomerInfo, DTCCAccountType, RejectionType
    from datetime import datetime, timedelta
    
    # Sample data for generating realistic ACATs
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Lisa", "Robert", "Emily", "James", "Jessica", 
                   "William", "Ashley", "Richard", "Amanda", "Joseph", "Jennifer", "Thomas", "Michelle", "Christopher", "Kimberly"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                  "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    companies = ["Apple Inc.", "Microsoft Corporation", "Amazon.com Inc.", "Alphabet Inc.", "Tesla Inc.", "Meta Platforms Inc.",
                 "NVIDIA Corporation", "Berkshire Hathaway", "Johnson & Johnson", "JPMorgan Chase & Co."]
    symbols = ["AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "NVDA", "BRK.A", "JNJ", "JPM"]
    cusips = ["037833100", "594918104", "023135106", "02079K305", "88160R101", "30303M102", "67066G104", "084670702", "478160104", "46625H100"]
    contra_firms = ["1234", "5678", "9012", "3456", "7890", "2345", "6789", "0123", "4567", "8901"]
    
    # Create 25 diverse ACAT records
    for i in range(25):
        # Random data selection
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        company = random.choice(companies)
        symbol = random.choice(symbols)
        cusip = random.choice(cusips)
        contra_firm = random.choice(contra_firms)
        
        # Create ACAT request
        acat_request = ACATRequest(
            delivering_account=f"DEL{random.randint(100000, 999999)}",
            receiving_account=f"REC{random.randint(100000, 999999)}",
            user_account_number=f"U{random.randint(100000, 999999)}",
            contra_firm=contra_firm,
            transfer_type=random.choice([TransferType.FULL, TransferType.PARTIAL]),
            transfer_date=datetime.now() - timedelta(days=random.randint(0, 90)),
            positions=[
                Position(
                    cusip=cusip,
                    symbol=symbol,
                    description=f"{company} Common Stock",
                    quantity=random.randint(10, 1000),
                    asset_type=random.choice([AssetType.EQUITY, AssetType.MUTUAL_FUND, AssetType.BOND])
                )
            ],
            customer=CustomerInfo(
                first_name=first_name,
                last_name=last_name,
                ssn=f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}",
                tax_id=f"{random.randint(100000000, 999999999)}" if random.random() > 0.3 else None
            ),
            account_type=random.choice([
                DTCCAccountType.INDIVIDUAL,
                DTCCAccountType.JOINT,
                DTCCAccountType.TRADITIONAL_IRA,
                DTCCAccountType.ROTH_IRA,
                DTCCAccountType.K401,
                DTCCAccountType.TRUST
            ]),
            special_instructions=random.choice([
                "Standard transfer",
                "Rush processing requested",
                "Hold for client approval",
                "Special handling required",
                "Standard processing",
                None
            ])
        )
        
        # Create tracking record
        record = tracking_store.create(acat_request)
        
        # Randomize created_at date (within last 90 days)
        days_ago = random.randint(0, 90)
        record.created_at = datetime.now() - timedelta(days=days_ago)
        
        # Assign realistic statuses with varying outcomes
        status_weights = {
            ACATStatus.COMPLETED: 0.4,      # 40% successful
            ACATStatus.REJECTED: 0.15,      # 15% rejected
            ACATStatus.PENDING_REVIEW: 0.15, # 15% pending review
            ACATStatus.PENDING_CLIENT: 0.1,  # 10% pending client
            ACATStatus.PENDING_DELIVERING: 0.1, # 10% pending delivering
            ACATStatus.PENDING_RECEIVING: 0.05, # 5% pending receiving
            ACATStatus.CANCELLED: 0.05      # 5% cancelled
        }
        
        # Weighted random selection
        status = random.choices(list(status_weights.keys()), weights=list(status_weights.values()))[0]
        
        # Create realistic status history
        status_history = []
        current_status = ACATStatus.NEW
        status_date = record.created_at
        
        # Simulate status progression
        if status == ACATStatus.COMPLETED:
            status_sequence = [ACATStatus.SUBMITTED, ACATStatus.PENDING_REVIEW, ACATStatus.COMPLETED]
        elif status == ACATStatus.REJECTED:
            status_sequence = [ACATStatus.SUBMITTED, ACATStatus.PENDING_REVIEW, ACATStatus.REJECTED]
        elif status == ACATStatus.CANCELLED:
            status_sequence = [ACATStatus.SUBMITTED, ACATStatus.CANCELLED]
        else:
            status_sequence = [ACATStatus.SUBMITTED, status]
        
        for i, next_status in enumerate(status_sequence):
            if i > 0:  # Skip first status (already NEW)
                status_date += timedelta(hours=random.randint(1, 72))
                reason = get_status_reason(current_status, next_status)
                updated_by = random.choice(["admin", "system", "operator"])
                
                status_history.append({
                    "from_status": current_status,
                    "to_status": next_status,
                    "reason": reason,
                    "updated_by": updated_by,
                    "updated_at": status_date.isoformat()
                })
                current_status = next_status
        
        # Update record with final status and history
        record.status = current_status
        record.updated_at = status_date
        record.status_history = status_history
        
        # If rejected, determine if it's a soft or hard rejection and add to queue if soft
        if current_status == ACATStatus.REJECTED:
            # 70% chance of soft rejection (can be fixed), 30% hard rejection
            rejection_type = RejectionType.SOFT if random.random() < 0.7 else RejectionType.HARD
            record.rejection_type = rejection_type
            if rejection_type == RejectionType.SOFT:
                record.in_queue = True
        
        tracking_store._records[record.id] = record
        
        # Record learning data based on outcome
        was_successful = current_status == ACATStatus.COMPLETED
        learning_data = {
            "suggestions": generate_fake_suggestions(contra_firm, was_successful),
            "is_valid": was_successful or current_status not in [ACATStatus.REJECTED, ACATStatus.CANCELLED],
            "success_probability": random.uniform(0.6, 0.95) if was_successful else random.uniform(0.1, 0.6)
        }
        learning_service.record_validation_result(contra_firm, learning_data, was_successful)

def get_status_reason(from_status, to_status):
    """Generate realistic reasons for status changes."""
    reasons = {
        (ACATStatus.NEW, ACATStatus.SUBMITTED): "Initial submission to DTCC",
        (ACATStatus.SUBMITTED, ACATStatus.PENDING_REVIEW): "Under review by DTCC",
        (ACATStatus.PENDING_REVIEW, ACATStatus.COMPLETED): "Transfer completed successfully",
        (ACATStatus.PENDING_REVIEW, ACATStatus.REJECTED): "Rejected due to invalid CUSIP",
        (ACATStatus.SUBMITTED, ACATStatus.CANCELLED): "Cancelled by client request",
        (ACATStatus.SUBMITTED, ACATStatus.PENDING_CLIENT): "Awaiting client approval",
        (ACATStatus.SUBMITTED, ACATStatus.PENDING_DELIVERING): "Awaiting delivering firm response",
        (ACATStatus.SUBMITTED, ACATStatus.PENDING_RECEIVING): "Awaiting receiving firm confirmation"
    }
    return reasons.get((from_status, to_status), f"Status changed from {from_status} to {to_status}")

def generate_fake_suggestions(contra_firm, was_successful):
    """Generate fake suggestions based on contra firm and success."""
    suggestions = []
    
    if not was_successful:
        # Add some rejection-related suggestions
        common_issues = [
            {"field": "cusip", "current": "123456789", "suggested": "123456780", "reason": "Invalid CUSIP format"},
            {"field": "account_number", "current": "DEL123", "suggested": "DEL123456", "reason": "Account number too short"},
            {"field": "customer_name", "current": "John D", "suggested": "John Doe", "reason": "Incomplete customer name"}
        ]
        
        for issue in random.sample(common_issues, random.randint(1, 3)):
            suggestions.append({
                "field": issue["field"],
                "current_value": issue["current"],
                "suggested_value": issue["suggested"],
                "reason": issue["reason"],
                "confidence": random.uniform(0.7, 0.95),
                "severity": random.choice(["medium", "high"])
            })
    
    return suggestions

def generate_daily_acats():
    """Generate 5-15 new ACATs with today's date to simulate ongoing activity."""
    from models.acat import ACATRequest, TransferType, Position, AssetType, CustomerInfo, DTCCAccountType
    from datetime import datetime, timedelta
    
    # Sample data
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Lisa", "Robert", "Emily", "James", "Jessica"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    companies = ["Apple Inc.", "Microsoft Corporation", "Amazon.com Inc.", "Alphabet Inc.", "Tesla Inc."]
    symbols = ["AAPL", "MSFT", "AMZN", "GOOGL", "TSLA"]
    cusips = ["037833100", "594918104", "023135106", "02079K305", "88160R101"]
    contra_firms = ["1234", "5678", "9012", "3456", "7890"]
    
    # Generate random number of ACATs (5-15)
    num_acats = random.randint(5, 15)
    
    for i in range(num_acats):
        acat_request = ACATRequest(
            delivering_account=f"DEL{random.randint(100000, 999999)}",
            receiving_account=f"REC{random.randint(100000, 999999)}",
            user_account_number=f"U{random.randint(100000, 999999)}",
            contra_firm=random.choice(contra_firms),
            transfer_type=random.choice([TransferType.FULL, TransferType.PARTIAL]),
            transfer_date=datetime.now(),
            positions=[
                Position(
                    cusip=random.choice(cusips),
                    symbol=random.choice(symbols),
                    description=f"{random.choice(companies)} Common Stock",
                    quantity=random.randint(10, 1000),
                    asset_type=random.choice([AssetType.EQUITY, AssetType.MUTUAL_FUND, AssetType.BOND])
                )
            ],
            customer=CustomerInfo(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                ssn=f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}",
                tax_id=None
            ),
            account_type=random.choice([
                DTCCAccountType.INDIVIDUAL,
                DTCCAccountType.JOINT,
                DTCCAccountType.TRADITIONAL_IRA,
                DTCCAccountType.ROTH_IRA
            ]),
            special_instructions="Auto-generated daily ACAT"
        )
        
        # Create with today's date
        record = tracking_store.create(acat_request)
        record.created_at = datetime.now()
        record.status = ACATStatus.NEW
        tracking_store._records[record.id] = record
    
    print(f"Generated {num_acats} new ACATs for today")

def generate_test_batch():
    """Generate 100 test ACATs with today's date, with 1/3 in soft reject state and in queue."""
    from models.acat import ACATRequest, TransferType, Position, AssetType, CustomerInfo, DTCCAccountType, RejectionType
    from datetime import datetime, timedelta
    
    # Sample data
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Lisa", "Robert", "Emily", "James", "Jessica",
                   "William", "Ashley", "Richard", "Amanda", "Joseph", "Jennifer", "Thomas", "Michelle", "Christopher", "Kimberly",
                   "Daniel", "Patricia", "Matthew", "Linda", "Anthony", "Barbara", "Mark", "Elizabeth", "Donald", "Susan",
                   "Steven", "Jessica", "Paul", "Sarah", "Andrew", "Karen", "Joshua", "Nancy", "Kenneth", "Betty"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                  "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
                  "Lee", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
                  "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green"]
    companies = ["Apple Inc.", "Microsoft Corporation", "Amazon.com Inc.", "Alphabet Inc.", "Tesla Inc.", "Meta Platforms Inc.",
                 "NVIDIA Corporation", "Berkshire Hathaway", "Johnson & Johnson", "JPMorgan Chase & Co.",
                 "Visa Inc.", "Walmart Inc.", "Mastercard Inc.", "Procter & Gamble", "UnitedHealth Group",
                 "Home Depot", "Bank of America", "Coca-Cola", "PepsiCo", "Intel Corporation"]
    symbols = ["AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "NVDA", "BRK.A", "JNJ", "JPM",
               "V", "WMT", "MA", "PG", "UNH", "HD", "BAC", "KO", "PEP", "INTC"]
    cusips = ["037833100", "594918104", "023135106", "02079K305", "88160R101", "30303M102", "67066G104", "084670702", "478160104", "46625H100",
              "92826C839", "931142103", "57636Q104", "742718109", "91324P102", "437076102", "060505104", "191216100", "713448108", "458140100"]
    contra_firms = ["1234", "5678", "9012", "3456", "7890", "2345", "6789", "0123", "4567", "8901"]
    
    num_acats = 100
    num_soft_rejects = 33  # 1/3 of 100
    
    soft_reject_reasons = [
        "Invalid CUSIP format - needs correction",
        "Account number mismatch - verify with delivering firm",
        "Customer information incomplete - missing required fields",
        "Position quantity exceeds account balance",
        "Invalid account type for transfer type",
        "Contra firm validation failed - verify participant number",
        "Transfer date in the past - update to future date",
        "Missing required position information",
        "Customer SSN format incorrect",
        "Special instructions contain invalid characters"
    ]
    
    for i in range(num_acats):
        # Random data selection
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        company = random.choice(companies)
        symbol = random.choice(symbols)
        cusip = random.choice(cusips)
        contra_firm = random.choice(contra_firms)
        
        # Create ACAT request
        acat_request = ACATRequest(
            delivering_account=f"DEL{random.randint(100000, 999999)}",
            receiving_account=f"REC{random.randint(100000, 999999)}",
            user_account_number=f"U{random.randint(100000, 999999)}",
            contra_firm=contra_firm,
            transfer_type=random.choice([TransferType.FULL, TransferType.PARTIAL]),
            transfer_date=datetime.now(),
            positions=[
                Position(
                    cusip=cusip,
                    symbol=symbol,
                    description=f"{company} Common Stock",
                    quantity=random.randint(10, 1000),
                    asset_type=random.choice([AssetType.EQUITY, AssetType.MUTUAL_FUND, AssetType.BOND])
                )
            ],
            customer=CustomerInfo(
                first_name=first_name,
                last_name=last_name,
                ssn=f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}",
                tax_id=f"{random.randint(100000000, 999999999)}" if random.random() > 0.3 else None
            ),
            account_type=random.choice([
                DTCCAccountType.INDIVIDUAL,
                DTCCAccountType.JOINT,
                DTCCAccountType.TRADITIONAL_IRA,
                DTCCAccountType.ROTH_IRA,
                DTCCAccountType.K401,
                DTCCAccountType.TRUST
            ]),
            special_instructions=random.choice([
                "Standard transfer",
                "Rush processing requested",
                "Hold for client approval",
                "Special handling required",
                "Standard processing",
                None
            ])
        )
        
        # Create tracking record
        record = tracking_store.create(acat_request)
        record.created_at = datetime.now()
        
        # Determine if this should be a soft reject (first 33 will be soft rejects)
        if i < num_soft_rejects:
            # Set up soft rejection
            record.status = ACATStatus.REJECTED
            record.rejection_type = RejectionType.SOFT
            record.in_queue = True
            
            # Create status history for rejection
            record.status_history = [
                {
                    "from_status": ACATStatus.NEW,
                    "to_status": ACATStatus.SUBMITTED,
                    "reason": "Initial submission to DTCC",
                    "updated_by": "system",
                    "updated_at": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat()
                },
                {
                    "from_status": ACATStatus.SUBMITTED,
                    "to_status": ACATStatus.PENDING_REVIEW,
                    "reason": "Under review by DTCC",
                    "updated_by": "system",
                    "updated_at": (datetime.now() - timedelta(hours=random.randint(1, 12))).isoformat()
                },
                {
                    "from_status": ACATStatus.PENDING_REVIEW,
                    "to_status": ACATStatus.REJECTED,
                    "reason": random.choice(soft_reject_reasons),
                    "updated_by": "system",
                    "updated_at": datetime.now().isoformat()
                }
            ]
            record.updated_at = datetime.now()
        else:
            # Other statuses - mix of NEW, SUBMITTED, PENDING_REVIEW
            status_weights = {
                ACATStatus.NEW: 0.4,
                ACATStatus.SUBMITTED: 0.3,
                ACATStatus.PENDING_REVIEW: 0.3
            }
            status = random.choices(list(status_weights.keys()), weights=list(status_weights.values()))[0]
            record.status = status
            
            if status != ACATStatus.NEW:
                record.status_history = [
                    {
                        "from_status": ACATStatus.NEW,
                        "to_status": ACATStatus.SUBMITTED,
                        "reason": "Initial submission to DTCC",
                        "updated_by": "system",
                        "updated_at": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat()
                    }
                ]
                if status == ACATStatus.PENDING_REVIEW:
                    record.status_history.append({
                        "from_status": ACATStatus.SUBMITTED,
                        "to_status": ACATStatus.PENDING_REVIEW,
                        "reason": "Under review by DTCC",
                        "updated_by": "system",
                        "updated_at": datetime.now().isoformat()
                    })
        
        tracking_store._records[record.id] = record
    
    print(f"Generated {num_acats} test ACATs with today's date ({num_soft_rejects} in soft reject state and queue)")

# Seed data on startup
seed_dummy_data()

# Generate today's ACATs
generate_daily_acats()

# Generate test batch of 100 ACATs
generate_test_batch()

# Auto-approve all pending users on startup
def auto_approve_all_users():
    """Auto-approve all pending users on startup."""
    pending_users = auth_service.get_pending_users()
    if pending_users:
        count = auth_service.approve_all_pending_users("system")
        print(f"Auto-approved {count} pending user(s) on startup")
        # Log audit entries
        for user in pending_users:
            audit_log.log_action(
                action="approve_user",
                entity_type="user",
                entity_id=user.id,
                details={
                    "approved_by": "system",
                    "username": user.username,
                    "auto_approved_on_startup": True
                },
                performed_by="system"
            )

auto_approve_all_users()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard."""
    try:
        with open("static/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found. Please check static files.</h1>")

@app.post("/api/validate-acat", response_model=ACATValidationResponse)
async def validate_acat(acat_request: ACATRequest):
    """Validate ACAT data and get AI-powered correction suggestions."""
    try:
        # First run basic validation
        basic_validation = await validation_service.validate_acat_basic(acat_request)
        
        # If basic validation found issues, return those
        if not basic_validation.is_valid or basic_validation.suggestions:
            return basic_validation
        
        # If basic validation passed, use Claude for deeper analysis
        claude_validation = await claude_service.analyze_acat(acat_request)
        
        # Record validation result for learning
        validation_data = {
            "suggestions": claude_validation.suggestions,
            "is_valid": claude_validation.is_valid,
            "success_probability": claude_validation.success_probability
        }
        learning_service.record_validation_result(acat_request.contra_firm, validation_data)
        
        # Combine results (Claude analysis takes precedence)
        return ACATValidationResponse(
            is_valid=claude_validation.is_valid,
            suggestions=claude_validation.suggestions,
            warnings=basic_validation.warnings + claude_validation.warnings,
            success_probability=claude_validation.success_probability,
            ai_analysis=claude_validation.ai_analysis
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@app.post("/api/submit-acat")
async def submit_acat(submission_request: ACATSubmissionRequest):
    """Submit corrected ACAT data (placeholder for actual DTCC submission)."""
    try:
        # In a real implementation, this would submit to DTCC
        # For now, we'll just return a success response
        
        acat_data = submission_request.acat_data
        accepted_suggestions = submission_request.accepted_suggestions
        custom_modifications = submission_request.custom_modifications
        
        # Log the submission (in production, this would go to a database)
        print(f"ACAT Submission:")
        print(f"  Delivering Account: {acat_data.delivering_account}")
        print(f"  Receiving Account: {acat_data.receiving_account}")
        print(f"  Contra Firm: {acat_data.contra_firm}")
        print(f"  Accepted Suggestions: {accepted_suggestions}")
        print(f"  Custom Modifications: {custom_modifications}")
        
        # Record learning data for this submission
        learning_data = {
            "accepted_suggestions": accepted_suggestions,
            "custom_modifications": custom_modifications
        }
        learning_service.record_validation_result(acat_data.contra_firm, learning_data, was_accepted=True)
        
        submission_response = {
            "status": "success",
            "message": "ACAT data submitted successfully",
            "submission_id": f"ACAT_{acat_data.delivering_account}_{acat_data.receiving_account}",
            "accepted_suggestions": accepted_suggestions,
            "custom_modifications": custom_modifications
        }

        # Create tracking record on submission
        tracking_record = tracking_store.create(acat_data, created_by="system")
        tracking_store.update_status(tracking_record.id, ACATStatus.SUBMITTED, "Initial submission", "system")
        submission_response["tracking_id"] = tracking_record.id
        submission_response["tracking_status"] = tracking_record.status
        return submission_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ACAT Correction Service",
        "version": "1.0.0"
    }


# --- ACAT tracking endpoints ---

@app.post("/api/tracking", response_model=ACATRecord)
async def create_tracking_record(acat_request: ACATRequest):
    return tracking_store.create(acat_request)


@app.get("/api/tracking", response_model=list[ACATRecord])
async def list_tracking_records():
    return tracking_store.list()


@app.get("/api/tracking/{record_id}", response_model=ACATRecord)
async def get_tracking_record(record_id: str):
    try:
        return tracking_store.get(record_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Tracking record not found")


@app.post("/api/auth/verify-password")
async def verify_password(session_id: str, password: str):
    """Verify user's password for sensitive operations."""
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if not auth_service.verify_password(password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid password")
    
    return {"verified": True}


@app.patch("/api/tracking/{record_id}/status", response_model=ACATRecord)
async def update_tracking_status(record_id: str, update_request: StatusUpdateRequest):
    try:
        # Verify password for status changes
        if update_request.password:
            user = auth_service.get_user_from_session(update_request.session_id)
            if not user or not auth_service.verify_password(update_request.password, user.password_hash):
                raise HTTPException(status_code=403, detail="Invalid password")
        
        record = tracking_store.update_status(record_id, update_request.status, update_request.reason, update_request.updated_by, learning_service)
        
        # If rejection type is provided, update it
        if update_request.rejection_type:
            record.rejection_type = update_request.rejection_type
            tracking_store._records[record_id] = record
        
        # If status is REJECTED and it's a soft rejection, add to queue
        if update_request.status == ACATStatus.REJECTED:
            rejection_type = update_request.rejection_type or RejectionType.SOFT  # Default to soft
            record.rejection_type = rejection_type
            if rejection_type == RejectionType.SOFT:
                queue_service.add_to_queue(record_id, rejection_type)
            tracking_store._records[record_id] = record
        
        return record
    except KeyError:
        raise HTTPException(status_code=404, detail="Tracking record not found")


@app.delete("/api/tracking/{record_id}")
async def delete_tracking_record(record_id: str):
    tracking_store.delete(record_id)
    return {"status": "deleted"}


# --- Authentication endpoints ---

@app.post("/api/auth/login")
async def login(username: str, password: str):
    user = auth_service.authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password, or account pending approval")
    
    session_id = auth_service.create_session(user)
    return {
        "session_id": session_id,
        "user": {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "role": user.role
        }
    }


@app.get("/api/auth/me")
async def get_current_user(session_id: str):
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "is_onboarded": user.is_onboarded,
        "last_login": user.last_login
    }


@app.post("/api/auth/logout")
async def logout(session_id: str):
    """Logout and invalidate session."""
    success = auth_service.delete_session(session_id)
    if not success:
        # Session might not exist, but that's okay
        pass
    return {"message": "Logged out successfully"}


@app.post("/api/auth/register")
async def register_user(user_data: UserCreateRequest):
    """Register a new user."""
    user = auth_service.create_user(
        username=user_data.username,
        password=user_data.password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        phone_number=user_data.phone_number,
        role=user_data.role
    )
    
    if not user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_onboarded": user.is_onboarded
    }


@app.post("/api/auth/complete-onboarding")
async def complete_onboarding(session_id: str):
    """Mark user as having completed onboarding."""
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    success = auth_service.update_user_onboarding(user.id, True)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update onboarding status")
    
    return {"message": "Onboarding completed successfully"}


@app.get("/api/onboarding/status")
async def get_onboarding_status():
    """Get onboarding status for the application."""
    users = auth_service.get_all_users()
    has_users = len(users) > 0
    has_onboarded_users = any(user.is_onboarded for user in users)
    
    return {
        "has_users": has_users,
        "has_onboarded_users": has_onboarded_users,
        "needs_onboarding": not has_onboarded_users,
        "user_count": len(users)
    }

@app.get("/api/contra-firms")
async def get_contra_firms():
    """Get list of common contra firms."""
    return validation_service.common_contra_firms


# --- Learning and Analytics endpoints ---

@app.get("/api/learning/firm/{contra_firm}")
async def get_firm_learning(contra_firm: str):
    """Get learning data for a specific contra firm."""
    return {
        "contra_firm": contra_firm,
        "preferences": learning_service.get_firm_preferences(contra_firm),
        "common_issues": learning_service.get_common_issues_for_firm(contra_firm),
        "success_rate": learning_service.get_firm_success_rate(contra_firm)
    }


@app.get("/api/learning/insights")
async def get_learning_insights():
    """Get overall learning insights across all firms."""
    return learning_service.get_learning_insights()


@app.get("/api/learning/export")
async def export_learning_data():
    """Export all learning data for analysis."""
    return learning_service.export_learning_data()


# --- User Management endpoints (Owner only) ---

@app.get("/api/admin/pending-users")
async def get_pending_users(session_id: str):
    """Get all users pending approval (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    pending = auth_service.get_pending_users()
    return [{
        "id": u.id,
        "username": u.username,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "email": u.email,
        "phone_number": u.phone_number,
        "role": u.role,
        "created_at": u.created_at
    } for u in pending]


@app.post("/api/admin/approve-user/{user_id}")
async def approve_user(user_id: str, session_id: str):
    """Approve a user account (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    success = auth_service.approve_user(user_id, user.username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Log audit entry
    audit_log.log_action(
        action="approve_user",
        entity_type="user",
        entity_id=user_id,
        details={"approved_by": user.username},
        performed_by=user.username
    )
    
    return {"message": "User approved successfully"}


@app.post("/api/admin/reject-user/{user_id}")
async def reject_user(user_id: str, session_id: str):
    """Reject a user account (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    success = auth_service.reject_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Log audit entry
    audit_log.log_action(
        action="reject_user",
        entity_type="user",
        entity_id=user_id,
        details={"rejected_by": user.username},
        performed_by=user.username
    )
    
    return {"message": "User rejected successfully"}


# --- User Management Tool endpoints ---

@app.get("/api/admin/users")
async def get_all_users(session_id: str):
    """Get all users (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    users = auth_service.get_all_users()
    user_list = []
    for u in users:
        user_info = {
            'id': u.id,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
            'phone_number': u.phone_number,
            'role': u.role.value,
            'is_approved': u.is_approved,
            'is_onboarded': u.is_onboarded,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'approved_by': getattr(u, 'approved_by', None)
        }
        user_list.append(user_info)
    
    return {"users": user_list}


@app.get("/api/admin/users/pending")
async def get_pending_users(session_id: str):
    """Get pending users (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    pending_users = auth_service.get_pending_users()
    user_list = []
    for u in pending_users:
        user_info = {
            'id': u.id,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
            'phone_number': u.phone_number,
            'role': u.role.value,
            'is_approved': u.is_approved,
            'is_onboarded': u.is_onboarded,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'approved_by': getattr(u, 'approved_by', None)
        }
        user_list.append(user_info)
    
    return {"pending_users": user_list}


@app.post("/api/admin/users/approve-by-username")
async def approve_user_by_username(username: str, session_id: str):
    """Approve a user by username (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    # Find user by username
    target_user = None
    for u in auth_service.get_all_users():
        if u.username == username:
            target_user = u
            break
    
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    
    if target_user.is_approved:
        return {"message": f"User '{username}' is already approved"}
    
    # Approve the user
    success = auth_service.approve_user(target_user.id, user.username)
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to approve user '{username}'")
    
    # Log audit entry
    audit_log.log_action(
        action="approve_user",
        entity_type="user",
        entity_id=target_user.id,
        details={"approved_by": user.username, "username": username},
        performed_by=user.username
    )
    
    return {"message": f"User '{username}' has been approved"}


@app.post("/api/admin/users/bulk-approve")
async def bulk_approve_users(usernames: List[str], session_id: str):
    """Approve multiple users at once (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    results = {
        "successful": [],
        "failed": [],
        "summary": {}
    }
    
    for username in usernames:
        try:
            # Find user by username
            target_user = None
            for u in auth_service.get_all_users():
                if u.username == username:
                    target_user = u
                    break
            
            if not target_user:
                results["failed"].append({"username": username, "error": "User not found"})
                continue
            
            if target_user.is_approved:
                results["successful"].append({"username": username, "message": "Already approved"})
                continue
            
            # Approve the user
            success = auth_service.approve_user(target_user.id, user.username)
            
            if success:
                results["successful"].append({"username": username, "message": "Approved successfully"})
                
                # Log audit entry
                audit_log.log_action(
                    action="approve_user",
                    entity_type="user",
                    entity_id=target_user.id,
                    details={"approved_by": user.username, "username": username, "bulk_operation": True},
                    performed_by=user.username
                )
            else:
                results["failed"].append({"username": username, "error": "Approval failed"})
        
        except Exception as e:
            results["failed"].append({"username": username, "error": str(e)})
    
    results["summary"] = {
        "total": len(usernames),
        "successful": len(results["successful"]),
        "failed": len(results["failed"])
    }
    
    return results


@app.post("/api/admin/users/approve-all")
async def approve_all_users(session_id: str):
    """Approve all pending users (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    # Get pending users before approval
    pending_before = auth_service.get_pending_users()
    pending_usernames = [u.username for u in pending_before]
    
    # Approve all pending users
    count = auth_service.approve_all_pending_users(user.username)
    
    # Log audit entries for each approved user
    for pending_user in pending_before:
        audit_log.log_action(
            action="approve_user",
            entity_type="user",
            entity_id=pending_user.id,
            details={
                "approved_by": user.username,
                "username": pending_user.username,
                "bulk_approve_all": True
            },
            performed_by=user.username
        )
    
    return {
        "message": f"Approved {count} user(s) successfully",
        "approved_count": count,
        "approved_usernames": pending_usernames
    }


@app.get("/api/admin/users/stats")
async def get_user_stats(session_id: str):
    """Get user statistics (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    users = auth_service.get_all_users()
    pending_users = auth_service.get_pending_users()
    
    stats = {
        "total_users": len(users),
        "approved_users": len([u for u in users if u.is_approved]),
        "pending_users": len(pending_users),
        "owner_users": len([u for u in users if u.role == UserRole.OWNER]),
        "full_users": len([u for u in users if u.role == UserRole.FULL]),
        "read_only_users": len([u for u in users if u.role == UserRole.READ_ONLY]),
        "onboarded_users": len([u for u in users if u.is_onboarded]),
        "last_updated": datetime.utcnow().isoformat()
    }
    
    return stats


@app.post("/api/admin/users/create")
async def create_user_admin(username: str, password: str, first_name: str, 
                          last_name: str, email: str, role: str = "read_only", 
                          phone_number: str = None, auto_approve: bool = False, 
                          session_id: str = None):
    """Create a new user (owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner access required")
    
    # Validate role
    try:
        user_role = UserRole(role.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role '{role}'. Valid roles: {[r.value for r in UserRole]}")
    
    # Create user
    new_user = auth_service.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        role=user_role
    )
    
    if not new_user:
        raise HTTPException(status_code=400, detail=f"Failed to create user '{username}'. Username may already exist.")
    
    result = {
        "message": f"User '{username}' created successfully",
        "user_id": new_user.id,
        "role": new_user.role.value,
        "is_approved": new_user.is_approved,
        "auto_approved": False
    }
    
    # Auto-approve if requested
    if auto_approve and not new_user.is_approved:
        approval_result = auth_service.approve_user(new_user.id, user.username)
        if approval_result:
            result["auto_approved"] = True
            result["approved_at"] = datetime.utcnow().isoformat()
            
            # Log audit entry
            audit_log.log_action(
                action="approve_user",
                entity_type="user",
                entity_id=new_user.id,
                details={"approved_by": user.username, "username": username, "auto_approved": True},
                performed_by=user.username
            )
    
    # Log user creation
    audit_log.log_action(
        action="create_user",
        entity_type="user",
        entity_id=new_user.id,
        details={"created_by": user.username, "username": username, "role": user_role.value},
        performed_by=user.username
    )
    
    return result


# --- Audit Log endpoints ---

@app.get("/api/audit/changes")
async def get_audit_log(session_id: str):
    """Get audit log of all system changes (admin/owner only)."""
    user = auth_service.get_user_from_session(session_id)
    if not user or user.role == UserRole.READ_ONLY:
        raise HTTPException(status_code=403, detail="Admin or Owner access required")
    
    # Get all audit entries from the audit log
    entries = audit_log.get_entries()
    
    # Convert to response format
    audit_entries = []
    for entry in entries:
        audit_entries.append({
            "id": entry.id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "details": entry.details,
            "performed_by": entry.performed_by,
            "performed_at": entry.performed_at.isoformat()
        })
    
    return audit_entries


# --- Soft Rejection Queue endpoints ---

@app.get("/api/queue", response_model=List[QueueItem])
async def get_queue(session_id: str, unclaimed_only: bool = False, claimed_by: Optional[str] = None):
    """Get items in the soft rejection queue."""
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # If claimed_by is not specified, use current user
    if claimed_by is None and not unclaimed_only:
        claimed_by = user.username
    
    items = queue_service.get_queue_items(claimed_by=claimed_by, unclaimed_only=unclaimed_only)
    return items


@app.get("/api/queue/stats")
async def get_queue_stats(session_id: str):
    """Get statistics about the soft rejection queue."""
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return queue_service.get_queue_stats()


@app.post("/api/queue/claim")
async def claim_queue_item(claim_request: QueueClaimRequest):
    """Claim an item from the queue for the current user."""
    user = auth_service.get_user_from_session(claim_request.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    success = queue_service.claim_item(claim_request.record_id, user.username)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to claim item. It may already be claimed or not in queue.")
    
    # Log audit entry
    audit_log.log_action(
        action="claim_queue_item",
        entity_type="acat",
        entity_id=claim_request.record_id,
        details={"claimed_by": user.username},
        performed_by=user.username
    )
    
    return {"message": "Item claimed successfully", "record_id": claim_request.record_id}


@app.post("/api/queue/unclaim")
async def unclaim_queue_item(claim_request: QueueClaimRequest):
    """Unclaim an item from the queue (return it to unclaimed state)."""
    user = auth_service.get_user_from_session(claim_request.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    success = queue_service.unclaim_item(claim_request.record_id, user.username)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to unclaim item. You may not be the owner.")
    
    # Log audit entry
    audit_log.log_action(
        action="unclaim_queue_item",
        entity_type="acat",
        entity_id=claim_request.record_id,
        details={"unclaimed_by": user.username},
        performed_by=user.username
    )
    
    return {"message": "Item unclaimed successfully", "record_id": claim_request.record_id}


@app.post("/api/queue/update")
async def update_queue_item(update_request: QueueUpdateRequest):
    """Update an ACAT in the queue with corrected data."""
    user = auth_service.get_user_from_session(update_request.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Verify the item is claimed by this user
    try:
        record = tracking_store.get(update_request.record_id)
        if record.queue_claimed_by != user.username:
            raise HTTPException(status_code=403, detail="You must claim this item before updating it")
    except KeyError:
        raise HTTPException(status_code=404, detail="ACAT record not found")
    
    # Update the ACAT data
    updated_record = queue_service.update_acat_in_queue(
        update_request.record_id,
        update_request.updated_acat_data,
        update_request.notes
    )
    
    # Log audit entry
    audit_log.log_action(
        action="update_queue_item",
        entity_type="acat",
        entity_id=update_request.record_id,
        details={
            "updated_by": user.username,
            "notes": update_request.notes
        },
        performed_by=user.username
    )
    
    return updated_record


@app.post("/api/queue/{record_id}/resubmit")
async def resubmit_from_queue(record_id: str, session_id: str):
    """Resubmit an ACAT from the queue after fixing it."""
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        record = tracking_store.get(record_id)
        
        # Verify the item is claimed by this user
        if record.queue_claimed_by != user.username:
            raise HTTPException(status_code=403, detail="You must claim this item before resubmitting it")
        
        # Remove from queue
        queue_service.remove_from_queue(record_id)
        
        # Update status to SUBMITTED
        updated_record = tracking_store.update_status(
            record_id,
            ACATStatus.SUBMITTED,
            "Resubmitted after fixing soft rejection",
            user.username,
            learning_service
        )
        
        # Log audit entry
        audit_log.log_action(
            action="resubmit_from_queue",
            entity_type="acat",
            entity_id=record_id,
            details={"resubmitted_by": user.username},
            performed_by=user.username
        )
        
        return {
            "message": "ACAT resubmitted successfully",
            "record": updated_record
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="ACAT record not found")


@app.delete("/api/queue/{record_id}")
async def remove_from_queue(record_id: str, session_id: str):
    """Remove an item from the queue (e.g., if it's a hard rejection or no longer needs fixing)."""
    user = auth_service.get_user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Only owners/admins can remove items
    if user.role == UserRole.READ_ONLY:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    success = queue_service.remove_from_queue(record_id)
    if not success:
        raise HTTPException(status_code=404, detail="ACAT record not found or not in queue")
    
    # Log audit entry
    audit_log.log_action(
        action="remove_from_queue",
        entity_type="acat",
        entity_id=record_id,
        details={"removed_by": user.username},
        performed_by=user.username
    )
    
    return {"message": "Item removed from queue successfully"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    )
