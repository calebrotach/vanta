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
        
        return {
            "status": "success",
            "message": "ACAT data submitted successfully",
            "submission_id": f"ACAT_{acat_data.delivering_account}_{acat_data.receiving_account}",
            "accepted_suggestions": accepted_suggestions,
            "custom_modifications": custom_modifications
        }
        
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

@app.get("/api/contra-firms")
async def get_contra_firms():
    """Get list of common contra firms."""
    return validation_service.common_contra_firms

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    )
