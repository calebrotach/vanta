#!/usr/bin/env python3
"""
Quick User Management Tool for Testing

This is a simplified version of the user management tool for quick testing.
"""

import sys
import os
sys.path.append('.')

from services.auth_service import SimpleAuthService

def main():
    print("🔧 Quick User Management Tool")
    print("=" * 40)
    
    auth_service = SimpleAuthService()
    
    while True:
        print("\nOptions:")
        print("1. List all users")
        print("2. List pending users")
        print("3. Approve user by username")
        print("4. Create new user")
        print("5. Show user stats")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == "1":
            users = auth_service.get_all_users()
            print(f"\n📋 All Users ({len(users)} total):")
            print("-" * 50)
            for user in users:
                status = "✅ Approved" if user.is_approved else "⏳ Pending"
                print(f"{user.username:<15} | {user.first_name} {user.last_name:<20} | {user.role:<10} | {status}")
        
        elif choice == "2":
            pending_users = auth_service.get_pending_users()
            print(f"\n⏳ Pending Users ({len(pending_users)} total):")
            print("-" * 50)
            for user in pending_users:
                print(f"{user.username:<15} | {user.first_name} {user.last_name:<20} | {user.role:<10} | {user.email}")
        
        elif choice == "3":
            username = input("Enter username to approve: ").strip()
            if not username:
                print("❌ Username cannot be empty")
                continue
            
            # Find user
            user = None
            for u in auth_service.get_all_users():
                if u.username == username:
                    user = u
                    break
            
            if not user:
                print(f"❌ User '{username}' not found")
                continue
            
            if user.is_approved:
                print(f"✅ User '{username}' is already approved")
                continue
            
            # Approve user
            success = auth_service.approve_user(user.id, "admin")
            if success:
                print(f"✅ User '{username}' has been approved")
            else:
                print(f"❌ Failed to approve user '{username}'")
        
        elif choice == "4":
            print("\n📝 Create New User:")
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            first_name = input("First Name: ").strip()
            last_name = input("Last Name: ").strip()
            email = input("Email: ").strip()
            phone = input("Phone (optional): ").strip()
            
            print("\nRole options:")
            print("1. read_only")
            print("2. full")
            print("3. owner")
            role_choice = input("Select role (1-3): ").strip()
            
            role_map = {"1": "read_only", "2": "full", "3": "owner"}
            role = role_map.get(role_choice, "read_only")
            
            auto_approve = input("Auto-approve? (y/n): ").strip().lower() == 'y'
            
            if not all([username, password, first_name, last_name, email]):
                print("❌ All fields except phone are required")
                continue
            
            # Create user
            user = auth_service.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone if phone else None,
                role=role
            )
            
            if user:
                print(f"✅ User '{username}' created successfully")
                if auto_approve:
                    success = auth_service.approve_user(user.id, "admin")
                    if success:
                        print(f"✅ User '{username}' auto-approved")
                    else:
                        print(f"⚠️ User created but auto-approval failed")
            else:
                print(f"❌ Failed to create user '{username}' (username may already exist)")
        
        elif choice == "5":
            users = auth_service.get_all_users()
            pending_users = auth_service.get_pending_users()
            
            print(f"\n📊 User Statistics:")
            print("-" * 30)
            print(f"Total Users: {len(users)}")
            print(f"Approved: {len([u for u in users if u.is_approved])}")
            print(f"Pending: {len(pending_users)}")
            print(f"Owners: {len([u for u in users if u.role.value == 'owner'])}")
            print(f"Full Access: {len([u for u in users if u.role.value == 'full'])}")
            print(f"Read Only: {len([u for u in users if u.role.value == 'read_only'])}")
        
        elif choice == "6":
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please enter 1-6.")

if __name__ == "__main__":
    main()



