import uuid
from datetime import datetime
from typing import Dict, List

from models.acat import ACATRecord, ACATRequest, ACATStatus


class InMemoryACATStore:
    """A simple in-memory store to track ACATs and their DTCC-related statuses."""

    def __init__(self) -> None:
        self._records: Dict[str, ACATRecord] = {}

    def create(self, acat_request: ACATRequest) -> ACATRecord:
        record_id = str(uuid.uuid4())
        record = ACATRecord(id=record_id, acat_data=acat_request)
        self._records[record_id] = record
        return record

    def list(self) -> List[ACATRecord]:
        return list(self._records.values())

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
        
        # Record status change for learning
        if learning_service:
            learning_service.record_status_change(record.acat_data.contra_firm, old_status, new_status, reason)
        
        self._records[record_id] = record
        return record

    def delete(self, record_id: str) -> None:
        if record_id in self._records:
            del self._records[record_id]


