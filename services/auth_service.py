import uuid
from datetime import datetime
from typing import Dict, Optional
from models.acat import User, UserRole

class SimpleAuthService:
    """Simple in-memory authentication service with two user types."""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, str] = {}  # session_id -> user_id
        self._create_default_users()
    
    def _create_default_users(self):
        """Create default users for testing."""
        # Full access user
        full_user = User(
            id=str(uuid.uuid4()),
            username="admin",
            role=UserRole.FULL
        )
        self._users[full_user.id] = full_user
        
        # Read-only user
        read_user = User(
            id=str(uuid.uuid4()),
            username="viewer",
            role=UserRole.READ_ONLY
        )
        self._users[read_user.id] = read_user
    
    def authenticate(self, username: str) -> Optional[User]:
        """Simple authentication by username (no password for demo)."""
        for user in self._users.values():
            if user.username == username:
                return user
        return None
    
    def create_session(self, user: User) -> str:
        """Create a session for the user."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = user.id
        return session_id
    
    def get_user_from_session(self, session_id: str) -> Optional[User]:
        """Get user from session ID."""
        user_id = self._sessions.get(session_id)
        if user_id:
            return self._users.get(user_id)
        return None
    
    def has_permission(self, user: User, action: str) -> bool:
        """Check if user has permission for an action."""
        if user.role == UserRole.FULL:
            return True
        elif user.role == UserRole.READ_ONLY:
            return action in ["read", "view"]
        return False
    
    def get_all_users(self) -> list[User]:
        """Get all users (for admin purposes)."""
        return list(self._users.values())
