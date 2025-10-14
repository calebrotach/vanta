import json
import os
from typing import List, Dict, Any
from anthropic import Anthropic
from models.acat import ACATRequest, CorrectionSuggestion, ACATValidationResponse

class ClaudeACATService:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def analyze_acat(self, acat_request: ACATRequest) -> ACATValidationResponse:
        """Analyze ACAT data and provide correction suggestions using Claude AI."""
        
        # Convert ACAT data to a readable format for Claude
        acat_data = self._format_acat_for_analysis(acat_request)
        
        # Create the prompt for Claude
        prompt = self._create_analysis_prompt(acat_data)
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse Claude's response
            analysis_result = self._parse_claude_response(response.content[0].text)
            
            return ACATValidationResponse(
                is_valid=analysis_result.get("is_valid", False),
                suggestions=analysis_result.get("suggestions", []),
                warnings=analysis_result.get("warnings", []),
                success_probability=analysis_result.get("success_probability", 0.0),
                ai_analysis=analysis_result.get("ai_analysis", "")
            )
            
        except Exception as e:
            # Fallback response if Claude fails
            return ACATValidationResponse(
                is_valid=False,
                suggestions=[],
                warnings=[f"AI analysis failed: {str(e)}"],
                success_probability=0.0,
                ai_analysis=f"Error analyzing ACAT data: {str(e)}"
            )
    
    def _format_acat_for_analysis(self, acat_request: ACATRequest) -> Dict[str, Any]:
        """Format ACAT request data for Claude analysis."""
        return {
            "delivering_account": acat_request.delivering_account,
            "receiving_account": acat_request.receiving_account,
            "contra_firm": acat_request.contra_firm,
            "transfer_type": acat_request.transfer_type,
            "transfer_date": acat_request.transfer_date.isoformat(),
            "securities": [
                {
                    "cusip": sec.cusip,
                    "symbol": sec.symbol,
                    "description": sec.description,
                    "quantity": sec.quantity,
                    "asset_type": sec.asset_type
                } for sec in acat_request.securities
            ],
            "customer": {
                "first_name": acat_request.customer.first_name,
                "last_name": acat_request.customer.last_name,
                "ssn": acat_request.customer.ssn,
                "tax_id": acat_request.customer.tax_id,
                "date_of_birth": acat_request.customer.date_of_birth.isoformat() if acat_request.customer.date_of_birth else None
            },
            "special_instructions": acat_request.special_instructions,
            "account_type": acat_request.account_type
        }
    
    def _create_analysis_prompt(self, acat_data: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for Claude to analyze ACAT data."""
        return f"""
You are an expert in DTCC ACATS (Automated Customer Account Transfer Service) operations. 
Analyze the following ACAT transfer request and identify potential issues that could lead to rejection.

ACAT Data:
{json.dumps(acat_data, indent=2)}

Please analyze this data and provide:
1. A validation assessment (is_valid: true/false)
2. Specific correction suggestions for any issues found
3. Warnings for potential problems
4. An estimated success probability (0.0 to 1.0)
5. A summary analysis

Common DTCC ACATS rejection reasons include:
- Invalid CUSIP codes
- Incorrect contra firm numbers
- Mismatched account numbers
- Invalid transfer types
- Missing required fields
- Format errors in customer information
- Invalid security quantities
- Account type mismatches

For each suggestion, provide:
- field: the field name that needs correction
- current_value: the current value
- suggested_value: the corrected value
- reason: detailed explanation
- confidence: confidence score (0.0-1.0)
- severity: low/medium/high

Respond in JSON format:
{{
    "is_valid": boolean,
    "suggestions": [
        {{
            "field": "string",
            "current_value": "string", 
            "suggested_value": "string",
            "reason": "string",
            "confidence": 0.0-1.0,
            "severity": "low|medium|high"
        }}
    ],
    "warnings": ["string"],
    "success_probability": 0.0-1.0,
    "ai_analysis": "string"
}}
"""
    
    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response and extract structured data."""
        try:
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback if no JSON found
                return {
                    "is_valid": False,
                    "suggestions": [],
                    "warnings": ["Could not parse AI response"],
                    "success_probability": 0.0,
                    "ai_analysis": response_text
                }
        except json.JSONDecodeError:
            return {
                "is_valid": False,
                "suggestions": [],
                "warnings": ["Invalid JSON response from AI"],
                "success_probability": 0.0,
                "ai_analysis": response_text
            }
