from typing import List, Optional, Dict
from datetime import datetime
from models.acat import ACATRecord, ACATStatus, RejectionType, QueueItem
from services.tracking_service import InMemoryACATStore

class SoftRejectionQueueService:
    """Service for managing the soft rejection queue"""
    
    def __init__(self, tracking_store: InMemoryACATStore):
        self.tracking_store = tracking_store
    
    def get_queue_items(self, claimed_by: Optional[str] = None, unclaimed_only: bool = False) -> List[QueueItem]:
        """Get all items in the soft rejection queue"""
        all_records = self.tracking_store.list()
        queue_items = []
        
        for record in all_records:
            # Only include soft rejections that are in the queue
            if (record.status == ACATStatus.REJECTED and 
                record.rejection_type == RejectionType.SOFT and 
                record.in_queue):
                
                # Filter by claimed status if requested
                if unclaimed_only and record.queue_claimed_by:
                    continue
                if claimed_by and record.queue_claimed_by != claimed_by:
                    continue
                
                # Find rejection reason from status history
                rejection_reason = "Rejected"
                rejection_date = record.updated_at
                
                for status_entry in reversed(record.status_history):
                    if status_entry.get("to_status") == ACATStatus.REJECTED:
                        rejection_reason = status_entry.get("reason", "Rejected")
                        rejection_date_str = status_entry.get("updated_at")
                        if rejection_date_str:
                            try:
                                # Handle ISO format with or without timezone
                                if 'Z' in rejection_date_str:
                                    rejection_date = datetime.fromisoformat(rejection_date_str.replace('Z', '+00:00'))
                                elif '+' in rejection_date_str or rejection_date_str.endswith('-00:00'):
                                    rejection_date = datetime.fromisoformat(rejection_date_str)
                                else:
                                    rejection_date = datetime.fromisoformat(rejection_date_str)
                            except (ValueError, AttributeError):
                                # If parsing fails, use the record's updated_at
                                rejection_date = record.updated_at
                        break
                
                queue_item = QueueItem(
                    acat_record=record,
                    rejection_reason=rejection_reason,
                    rejection_date=rejection_date,
                    claimed_by=record.queue_claimed_by,
                    claimed_at=record.queue_claimed_at,
                    priority=self._calculate_priority(record, rejection_date)
                )
                queue_items.append(queue_item)
        
        # Sort by priority (highest first), then by rejection date (oldest first)
        queue_items.sort(key=lambda x: (-x.priority, x.rejection_date))
        return queue_items
    
    def add_to_queue(self, record_id: str, rejection_type: RejectionType = RejectionType.SOFT) -> bool:
        """Add an ACAT record to the soft rejection queue"""
        try:
            record = self.tracking_store.get(record_id)
            
            # Only add if it's a rejected status
            if record.status != ACATStatus.REJECTED:
                return False
            
            # Update record to be in queue
            record.in_queue = True
            record.rejection_type = rejection_type
            self.tracking_store._records[record_id] = record
            return True
        except KeyError:
            return False
    
    def claim_item(self, record_id: str, username: str) -> bool:
        """Claim an item from the queue for a user"""
        try:
            record = self.tracking_store.get(record_id)
            
            # Check if item is in queue and not already claimed
            if not record.in_queue:
                return False
            
            if record.queue_claimed_by and record.queue_claimed_by != username:
                return False  # Already claimed by someone else
            
            # Claim the item
            record.queue_claimed_by = username
            record.queue_claimed_at = datetime.utcnow()
            self.tracking_store._records[record_id] = record
            return True
        except KeyError:
            return False
    
    def unclaim_item(self, record_id: str, username: str) -> bool:
        """Unclaim an item from the queue (return it to unclaimed state)"""
        try:
            record = self.tracking_store.get(record_id)
            
            # Check if item is claimed by this user
            if record.queue_claimed_by != username:
                return False
            
            # Unclaim the item
            record.queue_claimed_by = None
            record.queue_claimed_at = None
            self.tracking_store._records[record_id] = record
            return True
        except KeyError:
            return False
    
    def remove_from_queue(self, record_id: str) -> bool:
        """Remove an item from the queue (e.g., after fixing and resubmitting)"""
        try:
            record = self.tracking_store.get(record_id)
            record.in_queue = False
            record.queue_claimed_by = None
            record.queue_claimed_at = None
            self.tracking_store._records[record_id] = record
            return True
        except KeyError:
            return False
    
    def update_acat_in_queue(self, record_id: str, updated_acat_data, notes: Optional[str] = None) -> ACATRecord:
        """Update the ACAT data for an item in the queue"""
        record = self.tracking_store.get(record_id)
        
        # Update the ACAT data
        record.acat_data = updated_acat_data
        record.updated_at = datetime.utcnow()
        
        # Add note to status history if provided
        if notes:
            record.status_history.append({
                "from_status": record.status,
                "to_status": record.status,
                "reason": f"Queue update: {notes}",
                "updated_by": record.queue_claimed_by or "system",
                "updated_at": datetime.utcnow().isoformat()
            })
        
        self.tracking_store._records[record_id] = record
        return record
    
    def get_queue_stats(self) -> Dict:
        """Get statistics about the queue"""
        all_items = self.get_queue_items()
        unclaimed = [item for item in all_items if not item.claimed_by]
        claimed = [item for item in all_items if item.claimed_by]
        
        return {
            "total": len(all_items),
            "unclaimed": len(unclaimed),
            "claimed": len(claimed),
            "high_priority": len([item for item in all_items if item.priority >= 5]),
            "oldest_rejection": min([item.rejection_date for item in all_items]).isoformat() if all_items else None
        }
    
    def _calculate_priority(self, record: ACATRecord, rejection_date: datetime) -> int:
        """Calculate priority score for a queue item"""
        priority = 0
        
        # Increase priority based on age (older = higher priority)
        days_old = (datetime.utcnow() - rejection_date).days
        priority += min(days_old, 10)  # Max 10 points for age
        
        # Increase priority if it's been in queue for a while
        if record.in_queue:
            if record.queue_claimed_at:
                # If claimed, check how long it's been claimed
                days_claimed = (datetime.utcnow() - record.queue_claimed_at).days
                if days_claimed > 3:
                    priority += 5  # Urgent if claimed for more than 3 days
            else:
                # Unclaimed items get priority boost
                priority += 2
        
        # Check rejection reason for urgency indicators
        for status_entry in record.status_history:
            reason = status_entry.get("reason", "").lower()
            if any(keyword in reason for keyword in ["urgent", "rush", "client", "time-sensitive"]):
                priority += 3
        
        return priority

