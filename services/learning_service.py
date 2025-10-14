from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import json

class ContraFirmLearningService:
    """Service to learn contra firm preferences from past rejections and corrections."""
    
    def __init__(self):
        self._firm_preferences: Dict[str, Dict] = defaultdict(lambda: {
            "common_rejections": defaultdict(int),
            "accepted_suggestions": defaultdict(int),
            "field_patterns": defaultdict(lambda: defaultdict(int)),
            "success_rate": 0.0,
            "total_submissions": 0,
            "successful_submissions": 0,
            "last_updated": None
        })
    
    def record_validation_result(self, contra_firm: str, validation_result: dict, was_accepted: bool = None):
        """Record a validation result for learning purposes."""
        firm_data = self._firm_preferences[contra_firm]
        
        # Update submission counts
        firm_data["total_submissions"] += 1
        if was_accepted is True:
            firm_data["successful_submissions"] += 1
        elif was_accepted is False:
            # Record specific rejection reasons
            for suggestion in validation_result.get("suggestions", []):
                if suggestion.get("severity") == "high":
                    firm_data["common_rejections"][suggestion.get("field", "unknown")] += 1
        
        # Record accepted suggestions
        if validation_result.get("accepted_suggestions"):
            for field in validation_result["accepted_suggestions"]:
                firm_data["accepted_suggestions"][field] += 1
        
        # Update success rate
        if firm_data["total_submissions"] > 0:
            firm_data["success_rate"] = firm_data["successful_submissions"] / firm_data["total_submissions"]
        
        firm_data["last_updated"] = datetime.utcnow().isoformat()
    
    def record_status_change(self, contra_firm: str, old_status: str, new_status: str, reason: str):
        """Record status changes that might indicate firm preferences."""
        firm_data = self._firm_preferences[contra_firm]
        
        # Track patterns in status changes
        status_key = f"{old_status}_to_{new_status}"
        firm_data["field_patterns"]["status_changes"][status_key] += 1
        
        # Analyze reason for patterns
        reason_lower = reason.lower()
        if "reject" in reason_lower or "invalid" in reason_lower:
            firm_data["common_rejections"]["status_change"] += 1
    
    def get_firm_preferences(self, contra_firm: str) -> Dict:
        """Get learned preferences for a specific contra firm."""
        return dict(self._firm_preferences[contra_firm])
    
    def get_common_issues_for_firm(self, contra_firm: str) -> List[Dict]:
        """Get the most common issues for a specific firm."""
        firm_data = self._firm_preferences[contra_firm]
        
        # Combine rejections and field patterns
        all_issues = []
        
        # Common rejection fields
        for field, count in firm_data["common_rejections"].items():
            all_issues.append({
                "type": "rejection",
                "field": field,
                "count": count,
                "severity": "high" if count > 5 else "medium" if count > 2 else "low"
            })
        
        # Sort by count (most common first)
        all_issues.sort(key=lambda x: x["count"], reverse=True)
        return all_issues[:10]  # Top 10 issues
    
    def get_firm_success_rate(self, contra_firm: str) -> float:
        """Get success rate for a specific firm."""
        return self._firm_preferences[contra_firm]["success_rate"]
    
    def get_learning_insights(self) -> Dict:
        """Get overall learning insights across all firms."""
        total_firms = len(self._firm_preferences)
        if total_firms == 0:
            return {"message": "No learning data available yet"}
        
        # Calculate overall statistics
        total_submissions = sum(firm["total_submissions"] for firm in self._firm_preferences.values())
        total_successful = sum(firm["successful_submissions"] for firm in self._firm_preferences.values())
        overall_success_rate = total_successful / total_submissions if total_submissions > 0 else 0
        
        # Find most problematic firms
        problematic_firms = [
            {
                "firm": firm_id,
                "success_rate": firm_data["success_rate"],
                "total_submissions": firm_data["total_submissions"]
            }
            for firm_id, firm_data in self._firm_preferences.items()
            if firm_data["total_submissions"] > 0 and firm_data["success_rate"] < 0.5
        ]
        problematic_firms.sort(key=lambda x: x["success_rate"])
        
        # Find most common rejection fields across all firms
        global_rejections = defaultdict(int)
        for firm_data in self._firm_preferences.values():
            for field, count in firm_data["common_rejections"].items():
                global_rejections[field] += count
        
        most_common_issues = sorted(global_rejections.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_firms": total_firms,
            "total_submissions": total_submissions,
            "overall_success_rate": overall_success_rate,
            "problematic_firms": problematic_firms[:5],
            "most_common_issues": most_common_issues,
            "learning_active": total_submissions > 0
        }
    
    def export_learning_data(self) -> Dict:
        """Export all learning data for analysis."""
        return {
            "firm_preferences": dict(self._firm_preferences),
            "exported_at": datetime.utcnow().isoformat(),
            "insights": self.get_learning_insights()
        }
