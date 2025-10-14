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

    def update_status(self, record_id: str, new_status: ACATStatus) -> ACATRecord:
        record = self._records[record_id]
        record.status = new_status
        record.updated_at = datetime.utcnow()
        self._records[record_id] = record
        return record

    def delete(self, record_id: str) -> None:
        if record_id in self._records:
            del self._records[record_id]


