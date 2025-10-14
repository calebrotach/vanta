import os
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
from models.acat import ACATRecord, ACATStatus, StatusUpdateRequest, UserRole

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
    from datetime import datetime
    
    # Create sample ACAT records
    sample_acat1 = ACATRequest(
        delivering_account="DEL123456",
        receiving_account="REC789012",
        contra_firm="1234",
        transfer_type=TransferType.FULL,
        transfer_date=datetime.now(),
        securities=[
            Security(
                cusip="123456789",
                symbol="AAPL",
                description="Apple Inc. Common Stock",
                quantity=100,
                asset_type=AssetType.EQUITY
            )
        ],
        customer=CustomerInfo(
            first_name="John",
            last_name="Doe",
            ssn="123-45-6789"
        ),
        special_instructions="Standard transfer"
    )
    
    sample_acat2 = ACATRequest(
        delivering_account="DEL654321",
        receiving_account="REC210987",
        contra_firm="5678",
        transfer_type=TransferType.PARTIAL,
        transfer_date=datetime.now(),
        securities=[
            Security(
                cusip="987654321",
                symbol="MSFT",
                description="Microsoft Corporation Common Stock",
                quantity=50,
                asset_type=AssetType.EQUITY
            )
        ],
        customer=CustomerInfo(
            first_name="Jane",
            last_name="Smith",
            ssn="987-65-4321"
        )
    )
    
    # Create tracking records
    record1 = tracking_store.create(sample_acat1)
    record2 = tracking_store.create(sample_acat2)
    
    # Set different statuses
    tracking_store.update_status(record1.id, ACATStatus.SUBMITTED, "Initial submission", "admin")
    tracking_store.update_status(record2.id, ACATStatus.PENDING_REVIEW, "Under review", "admin")

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
        "role": user.role
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
