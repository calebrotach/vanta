from typing import List, Dict, Any
from models.acat import ACATRequest, CorrectionSuggestion, ACATValidationResponse
import re

class ACATValidationService:
    """Service for basic ACAT data validation and common error detection."""
    
    def __init__(self):
        self.common_contra_firms = {
            "0001": "Fidelity Investments",
            "0002": "Charles Schwab", 
            "0003": "Merrill Lynch",
            "0004": "Morgan Stanley",
            "0005": "Goldman Sachs",
            "0006": "JP Morgan",
            "0007": "Bank of America",
            "0008": "Wells Fargo",
            "0009": "TD Ameritrade",
            "0010": "E*TRADE"
        }
    
    async def validate_acat_basic(self, acat_request: ACATRequest) -> ACATValidationResponse:
        """Perform basic validation on ACAT data."""
        suggestions = []
        warnings = []
        
        # Validate contra firm
        if acat_request.contra_firm not in self.common_contra_firms:
            suggestions.append(CorrectionSuggestion(
                field="contra_firm",
                current_value=acat_request.contra_firm,
                suggested_value="0001",  # Default to Fidelity
                reason="Contra firm not recognized in common DTCC participants",
                confidence=0.7,
                severity="medium"
            ))
            warnings.append(f"Contra firm {acat_request.contra_firm} not in common participants list")
        
        # Validate CUSIPs
        for i, security in enumerate(acat_request.securities):
            if not self._is_valid_cusip(security.cusip):
                suggestions.append(CorrectionSuggestion(
                    field=f"securities[{i}].cusip",
                    current_value=security.cusip,
                    suggested_value=self._suggest_cusip_correction(security.cusip),
                    reason="CUSIP format appears invalid",
                    confidence=0.8,
                    severity="high"
                ))
                warnings.append(f"Invalid CUSIP format: {security.cusip}")
        
        # Validate account numbers
        if not self._is_valid_account_number(acat_request.delivering_account):
            suggestions.append(CorrectionSuggestion(
                field="delivering_account",
                current_value=acat_request.delivering_account,
                suggested_value=acat_request.delivering_account.replace(" ", "").replace("-", ""),
                reason="Account number contains invalid characters",
                confidence=0.9,
                severity="high"
            ))
        
        if not self._is_valid_account_number(acat_request.receiving_account):
            suggestions.append(CorrectionSuggestion(
                field="receiving_account", 
                current_value=acat_request.receiving_account,
                suggested_value=acat_request.receiving_account.replace(" ", "").replace("-", ""),
                reason="Account number contains invalid characters",
                confidence=0.9,
                severity="high"
            ))
        
        # Validate customer SSN format
        if acat_request.customer.ssn and not self._is_valid_ssn(acat_request.customer.ssn):
            suggestions.append(CorrectionSuggestion(
                field="customer.ssn",
                current_value=acat_request.customer.ssn,
                suggested_value=self._format_ssn(acat_request.customer.ssn),
                reason="SSN format should be XXX-XX-XXXX",
                confidence=0.95,
                severity="medium"
            ))
        
        # Calculate success probability
        success_probability = self._calculate_success_probability(suggestions, warnings)
        
        return ACATValidationResponse(
            is_valid=len(suggestions) == 0,
            suggestions=suggestions,
            warnings=warnings,
            success_probability=success_probability,
            ai_analysis="Basic validation completed. Review suggestions for potential issues."
        )
    
    def _is_valid_cusip(self, cusip: str) -> bool:
        """Validate CUSIP format."""
        if len(cusip) != 9:
            return False
        if not cusip.isalnum():
            return False
        # Basic checksum validation could be added here
        return True
    
    def _suggest_cusip_correction(self, cusip: str) -> str:
        """Suggest CUSIP correction."""
        # Remove spaces and convert to uppercase
        corrected = cusip.replace(" ", "").replace("-", "").upper()
        # Pad with zeros if too short
        if len(corrected) < 9:
            corrected = corrected.ljust(9, "0")
        # Truncate if too long
        if len(corrected) > 9:
            corrected = corrected[:9]
        return corrected
    
    def _is_valid_account_number(self, account: str) -> bool:
        """Validate account number format."""
        # Remove common separators
        clean_account = account.replace("-", "").replace("_", "").replace(" ", "")
        return clean_account.isalnum() and len(clean_account) >= 1
    
    def _is_valid_ssn(self, ssn: str) -> bool:
        """Validate SSN format."""
        pattern = r'^\d{3}-\d{2}-\d{4}$'
        return bool(re.match(pattern, ssn))
    
    def _format_ssn(self, ssn: str) -> str:
        """Format SSN to XXX-XX-XXXX."""
        # Remove all non-digits
        digits = re.sub(r'\D', '', ssn)
        if len(digits) == 9:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return ssn
    
    def _calculate_success_probability(self, suggestions: List[CorrectionSuggestion], warnings: List[str]) -> float:
        """Calculate estimated success probability based on issues found."""
        base_probability = 1.0
        
        # Reduce probability based on severity of suggestions
        for suggestion in suggestions:
            if suggestion.severity == "high":
                base_probability -= 0.3
            elif suggestion.severity == "medium":
                base_probability -= 0.15
            elif suggestion.severity == "low":
                base_probability -= 0.05
        
        # Reduce probability based on number of warnings
        base_probability -= len(warnings) * 0.05
        
        return max(0.0, min(1.0, base_probability))
