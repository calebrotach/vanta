import os
import random
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

from models.acat import ACATRequest, ACATValidationResponse, ACATSubmissionRequest
from services.claude_service import ClaudeACATService
from services.validation_service import ACATValidationService
from services.tracking_service import InMemoryACATStore
from services.auth_service import SimpleAuthService
from services.learning_service import ContraFirmLearningService
from models.acat import ACATRecord, ACATStatus, StatusUpdateRequest, UserRole, UserCreateRequest, OnboardingStep

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
tracking_store = InMemoryACATStore()
auth_service = SimpleAuthService()
learning_service = ContraFirmLearningService()

# Seed dummy data
def seed_dummy_data():
    from models.acat import ACATRequest, TransferType, Security, AssetType, CustomerInfo
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
            contra_firm=contra_firm,
            transfer_type=random.choice([TransferType.FULL, TransferType.PARTIAL]),
            transfer_date=datetime.now() - timedelta(days=random.randint(0, 30)),
            securities=[
                Security(
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

# Seed data on startup
seed_dummy_data()

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
        tracking_record = tracking_store.create(acat_data)
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


@app.patch("/api/tracking/{record_id}/status", response_model=ACATRecord)
async def update_tracking_status(record_id: str, update_request: StatusUpdateRequest):
    try:
        return tracking_store.update_status(record_id, update_request.status, update_request.reason, update_request.updated_by, learning_service)
    except KeyError:
        raise HTTPException(status_code=404, detail="Tracking record not found")


@app.delete("/api/tracking/{record_id}")
async def delete_tracking_record(record_id: str):
    tracking_store.delete(record_id)
    return {"status": "deleted"}


# --- Authentication endpoints ---

@app.post("/api/auth/login")
async def login(username: str):
    user = auth_service.authenticate(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username")
    
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


@app.post("/api/auth/register")
async def register_user(user_data: UserCreateRequest):
    """Register a new user."""
    user = auth_service.create_user(
        username=user_data.username,
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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    )
