import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

from models.acat import ACATRecord, ACATRequest, ACATStatus


class AuditEntry(BaseModel):
    id: str
    action: str
    entity_type: str  # "acat" or "user"
    entity_id: str
    details: Dict
    performed_by: str
    performed_at: datetime


class AuditLog:
    """Simple in-memory audit log for tracking all system changes."""
    
    def __init__(self):
        self._entries: List[AuditEntry] = []
    
    def log_action(self, action: str, entity_type: str, entity_id: str, details: Dict, performed_by: str):
        """Log an action to the audit trail."""
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            performed_by=performed_by,
            performed_at=datetime.utcnow()
        )
        self._entries.append(entry)
    
    def get_entries(self) -> List[AuditEntry]:
        """Get all audit entries sorted by timestamp (newest first)."""
        return sorted(self._entries, key=lambda x: x.performed_at, reverse=True)


class InMemoryACATStore:
    """A simple in-memory store to track ACATs and their DTCC-related statuses."""

    def __init__(self, audit_log: Optional[AuditLog] = None) -> None:
        self._records: Dict[str, ACATRecord] = {}
        self.audit_log = audit_log

    def create(self, acat_request: ACATRequest, created_by: str = "system") -> ACATRecord:
        record_id = str(uuid.uuid4())
        record = ACATRecord(id=record_id, acat_data=acat_request)
        self._records[record_id] = record
        
        # Log audit entry
        if self.audit_log:
            self.audit_log.log_action(
                action="create",
                entity_type="acat",
                entity_id=record_id,
                details={
                    "delivering_account": acat_request.delivering_account,
                    "receiving_account": acat_request.receiving_account,
                    "contra_firm": acat_request.contra_firm,
                    "transfer_type": acat_request.transfer_type
                },
                performed_by=created_by
            )
        
        return record

    def list(self) -> List[ACATRecord]:
        return list(self._records.values())
    
    def list_all(self) -> List[ACATRecord]:
        """Alias for list() for consistency with audit log."""
        return self.list()

    def get(self, record_id: str) -> ACATRecord:
        return self._records[record_id]

    def update_status(self, record_id: str, new_status: ACATStatus, reason: str, updated_by: str, learning_service=None) -> ACATRecord:
        record = self._records[record_id]
        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.utcnow()
        
        # Add to status history
        record.status_history.append({
            "from_status": old_status,
            "to_status": new_status,
            "reason": reason,
            "updated_by": updated_by,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # Log audit entry
        if self.audit_log:
            self.audit_log.log_action(
                action="status_change",
                entity_type="acat",
                entity_id=record_id,
                details={
                    "from_status": old_status,
                    "to_status": new_status,
                    "reason": reason,
                    "delivering_account": record.acat_data.delivering_account,
                    "receiving_account": record.acat_data.receiving_account
                },
                performed_by=updated_by
            )
        
        # Record status change for learning
        if learning_service:
            learning_service.record_status_change(record.acat_data.contra_firm, old_status, new_status, reason)
        
        self._records[record_id] = record
        return record

    def delete(self, record_id: str) -> None:
        if record_id in self._records:
            del self._records[record_id]


