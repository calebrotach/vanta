import uuid
import hashlib
from datetime import datetime
from typing import Dict, Optional
from models.acat import User, UserRole

class SimpleAuthService:
    """Simple in-memory authentication service with password support."""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, str] = {}  # session_id -> user_id
        self._create_default_users()
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a hash."""
        return self._hash_password(password) == password_hash
    
    def _create_default_users(self):
        """Create default users for testing."""
        default_password = self._hash_password("test")
        
        # Owner user
        owner_user = User(
            id=str(uuid.uuid4()),
            username="owner",
            password_hash=default_password,
            first_name="System",
            last_name="Owner",
            email="owner@vanta.com",
            phone_number="+1-555-0000",
            role=UserRole.OWNER,
            is_approved=True
        )
        self._users[owner_user.id] = owner_user
        
        # Full access user
        full_user = User(
            id=str(uuid.uuid4()),
            username="admin",
            password_hash=default_password,
            first_name="System",
            last_name="Administrator",
            email="admin@vanta.com",
            phone_number="+1-555-0001",
            role=UserRole.FULL,
            is_approved=True
        )
        self._users[full_user.id] = full_user
        
        # Read-only user
        read_user = User(
            id=str(uuid.uuid4()),
            username="viewer",
            password_hash=default_password,
            first_name="Read",
            last_name="Only",
            email="viewer@vanta.com",
            phone_number="+1-555-0002",
            role=UserRole.READ_ONLY,
            is_approved=True
        )
        self._users[read_user.id] = read_user
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        for user in self._users.values():
            if user.username == username:
                # Verify password
                if not self._verify_password(password, user.password_hash):
                    return None
                # Check if user is approved
                if not user.is_approved:
                    return None
                # Update last login
                user.last_login = datetime.utcnow()
                return user
        return None
    
    def create_user(self, username: str, password: str, first_name: str, last_name: str, email: str, phone_number: str = None, role: UserRole = UserRole.READ_ONLY) -> Optional[User]:
        """Create a new user."""
        # Check if username already exists
        for user in self._users.values():
            if user.username == username:
                return None
        
        # Owner accounts are auto-approved, others need approval
        is_approved = (role == UserRole.OWNER)
        
        new_user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=self._hash_password(password),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            role=role,
            is_approved=is_approved,
            is_onboarded=False
        )
        self._users[new_user.id] = new_user
        return new_user
    
    def update_user_onboarding(self, user_id: str, is_onboarded: bool = True) -> bool:
        """Update user onboarding status."""
        if user_id in self._users:
            self._users[user_id].is_onboarded = is_onboarded
            return True
        return False
    
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
    
    def get_pending_users(self) -> list[User]:
        """Get all users pending approval."""
        return [user for user in self._users.values() if not user.is_approved and user.role != UserRole.OWNER]
    
    def approve_user(self, user_id: str, approver_username: str) -> bool:
        """Approve a user account (owner only)."""
        if user_id in self._users:
            self._users[user_id].is_approved = True
            self._users[user_id].approved_by = approver_username
            return True
        return False
    
    def reject_user(self, user_id: str) -> bool:
        """Reject and delete a user account (owner only)."""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False
