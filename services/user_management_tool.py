#!/usr/bin/env python3
"""
User Management Tool for Vanta ACAT System

This tool provides command-line and programmatic interfaces for managing users
without requiring email verification. Useful for testing and development.

Usage:
    python -m services.user_management_tool --help
    python -m services.user_management_tool list-users
    python -m services.user_management_tool approve-user <username>
    python -m services.user_management_tool create-user <username> <password> <role>
"""

import argparse
import sys
import json
from datetime import datetime
from typing import List, Dict, Optional
import uuid

# Add the parent directory to the path so we can import our modules
sys.path.append('.')

from services.auth_service import SimpleAuthService
from models.acat import User, UserRole

class UserManagementTool:
    """Tool for managing users without email verification."""
    
    def __init__(self):
        self.auth_service = SimpleAuthService()
    
    def list_users(self, show_pending_only: bool = False) -> List[Dict]:
        """List all users or pending users only."""
        users = self.auth_service.get_all_users()
        
        if show_pending_only:
            users = [user for user in users if not user.is_approved]
        
        user_list = []
        for user in users:
            user_info = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'role': user.role.value,
                'is_approved': user.is_approved,
                'is_onboarded': user.is_onboarded,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'approved_by': getattr(user, 'approved_by', None)
            }
            user_list.append(user_info)
        
        return user_list
    
    def approve_user(self, username: str, approver_username: str = "system") -> Dict:
        """Approve a user without email verification."""
        # Find user by username
        user = None
        for u in self.auth_service.get_all_users():
            if u.username == username:
                user = u
                break
        
        if not user:
            return {"error": f"User '{username}' not found"}
        
        if user.is_approved:
            return {"message": f"User '{username}' is already approved"}
        
        # Approve the user
        success = self.auth_service.approve_user(user.id, approver_username)
        
        if success:
            return {
                "message": f"User '{username}' has been approved",
                "user_id": user.id,
                "approved_by": approver_username,
                "approved_at": datetime.utcnow().isoformat()
            }
        else:
            return {"error": f"Failed to approve user '{username}'"}
    
    def create_user(self, username: str, password: str, first_name: str, 
                   last_name: str, email: str, role: str = "read_only", 
                   phone_number: str = None, auto_approve: bool = False) -> Dict:
        """Create a new user."""
        # Validate role
        try:
            user_role = UserRole(role.lower())
        except ValueError:
            return {"error": f"Invalid role '{role}'. Valid roles: {[r.value for r in UserRole]}"}
        
        # Create user
        user = self.auth_service.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            role=user_role
        )
        
        if not user:
            return {"error": f"Failed to create user '{username}'. Username may already exist."}
        
        result = {
            "message": f"User '{username}' created successfully",
            "user_id": user.id,
            "role": user.role.value,
            "is_approved": user.is_approved,
            "auto_approved": False
        }
        
        # Auto-approve if requested
        if auto_approve and not user.is_approved:
            approval_result = self.approve_user(username, "system")
            if "error" not in approval_result:
                result["auto_approved"] = True
                result["approved_at"] = approval_result["approved_at"]
        
        return result
    
    def reject_user(self, username: str) -> Dict:
        """Reject and delete a user."""
        # Find user by username
        user = None
        for u in self.auth_service.get_all_users():
            if u.username == username:
                user = u
                break
        
        if not user:
            return {"error": f"User '{username}' not found"}
        
        if user.role == UserRole.OWNER:
            return {"error": "Cannot reject owner accounts"}
        
        # Reject the user
        success = self.auth_service.reject_user(user.id)
        
        if success:
            return {
                "message": f"User '{username}' has been rejected and deleted",
                "user_id": user.id,
                "rejected_at": datetime.utcnow().isoformat()
            }
        else:
            return {"error": f"Failed to reject user '{username}'"}
    
    def get_user_stats(self) -> Dict:
        """Get user statistics."""
        users = self.auth_service.get_all_users()
        pending_users = self.auth_service.get_pending_users()
        
        stats = {
            "total_users": len(users),
            "approved_users": len([u for u in users if u.is_approved]),
            "pending_users": len(pending_users),
            "owner_users": len([u for u in users if u.role == UserRole.OWNER]),
            "full_users": len([u for u in users if u.role == UserRole.FULL]),
            "read_only_users": len([u for u in users if u.role == UserRole.READ_ONLY]),
            "onboarded_users": len([u for u in users if u.is_onboarded]),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        return stats
    
    def bulk_approve_users(self, usernames: List[str], approver_username: str = "system") -> Dict:
        """Approve multiple users at once."""
        results = {
            "successful": [],
            "failed": [],
            "summary": {}
        }
        
        for username in usernames:
            result = self.approve_user(username, approver_username)
            if "error" in result:
                results["failed"].append({"username": username, "error": result["error"]})
            else:
                results["successful"].append({"username": username, "message": result["message"]})
        
        results["summary"] = {
            "total": len(usernames),
            "successful": len(results["successful"]),
            "failed": len(results["failed"])
        }
        
        return results
    
    def export_users(self, include_passwords: bool = False) -> Dict:
        """Export user data for backup or analysis."""
        users = self.auth_service.get_all_users()
        
        export_data = {
            "exported_at": datetime.utcnow().isoformat(),
            "total_users": len(users),
            "users": []
        }
        
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": user.role.value,
                "is_approved": user.is_approved,
                "is_onboarded": user.is_onboarded,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "approved_by": getattr(user, 'approved_by', None)
            }
            
            if include_passwords:
                user_data["password_hash"] = user.password_hash
            
            export_data["users"].append(user_data)
        
        return export_data

def main():
    """Command-line interface for the user management tool."""
    parser = argparse.ArgumentParser(description="User Management Tool for Vanta ACAT System")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List users command
    list_parser = subparsers.add_parser('list-users', help='List all users')
    list_parser.add_argument('--pending-only', action='store_true', help='Show only pending users')
    list_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Approve user command
    approve_parser = subparsers.add_parser('approve-user', help='Approve a user')
    approve_parser.add_argument('username', help='Username to approve')
    approve_parser.add_argument('--approver', default='system', help='Username of approver')
    approve_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Create user command
    create_parser = subparsers.add_parser('create-user', help='Create a new user')
    create_parser.add_argument('username', help='Username')
    create_parser.add_argument('password', help='Password')
    create_parser.add_argument('first_name', help='First name')
    create_parser.add_argument('last_name', help='Last name')
    create_parser.add_argument('email', help='Email address')
    create_parser.add_argument('--role', default='read_only', choices=['owner', 'full', 'read_only'], help='User role')
    create_parser.add_argument('--phone', help='Phone number')
    create_parser.add_argument('--auto-approve', action='store_true', help='Auto-approve the user')
    create_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Reject user command
    reject_parser = subparsers.add_parser('reject-user', help='Reject a user')
    reject_parser.add_argument('username', help='Username to reject')
    reject_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show user statistics')
    stats_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Bulk approve command
    bulk_parser = subparsers.add_parser('bulk-approve', help='Approve multiple users')
    bulk_parser.add_argument('usernames', nargs='+', help='Usernames to approve')
    bulk_parser.add_argument('--approver', default='system', help='Username of approver')
    bulk_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export user data')
    export_parser.add_argument('--include-passwords', action='store_true', help='Include password hashes')
    export_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tool = UserManagementTool()
    
    try:
        if args.command == 'list-users':
            users = tool.list_users(show_pending_only=args.pending_only)
            if args.json:
                print(json.dumps(users, indent=2))
            else:
                print(f"\n{'Username':<20} {'Name':<25} {'Role':<12} {'Approved':<10} {'Onboarded':<12}")
                print("-" * 85)
                for user in users:
                    name = f"{user['first_name']} {user['last_name']}"
                    print(f"{user['username']:<20} {name:<25} {user['role']:<12} {str(user['is_approved']):<10} {str(user['is_onboarded']):<12}")
        
        elif args.command == 'approve-user':
            result = tool.approve_user(args.username, args.approver)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    print(f"Success: {result['message']}")
        
        elif args.command == 'create-user':
            result = tool.create_user(
                username=args.username,
                password=args.password,
                first_name=args.first_name,
                last_name=args.last_name,
                email=args.email,
                role=args.role,
                phone_number=args.phone,
                auto_approve=args.auto_approve
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    print(f"Success: {result['message']}")
                    if result.get('auto_approved'):
                        print("User was automatically approved")
        
        elif args.command == 'reject-user':
            result = tool.reject_user(args.username)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    print(f"Success: {result['message']}")
        
        elif args.command == 'stats':
            stats = tool.get_user_stats()
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("\nUser Statistics:")
                print("-" * 30)
                for key, value in stats.items():
                    if key != "last_updated":
                        print(f"{key.replace('_', ' ').title()}: {value}")
        
        elif args.command == 'bulk-approve':
            result = tool.bulk_approve_users(args.usernames, args.approver)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Bulk Approval Results:")
                print(f"Total: {result['summary']['total']}")
                print(f"Successful: {result['summary']['successful']}")
                print(f"Failed: {result['summary']['failed']}")
                
                if result['failed']:
                    print("\nFailed approvals:")
                    for failure in result['failed']:
                        print(f"  - {failure['username']}: {failure['error']}")
        
        elif args.command == 'export':
            result = tool.export_users(include_passwords=args.include_passwords)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Exported {result['total_users']} users")
                print(f"Export completed at: {result['exported_at']}")
    
    except Exception as e:
        error_result = {"error": str(e)}
        if hasattr(args, 'json') and args.json:
            print(json.dumps(error_result, indent=2))
        else:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()



