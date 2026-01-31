#!/usr/bin/env python3
"""
Migration Script: Add Authentication to Existing VM Monitor Installation
Usage: sudo /opt/vm-monitor/venv/bin/python /opt/vm-monitor/migrate_add_auth.py

This script adds authentication to an existing VM Monitor installation without
disrupting existing VM data and metrics.
"""

import sys
import os

# Add current directory to path to find app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User
import getpass

def main():
    print("=" * 60)
    print("VM Monitor - Add Authentication Migration")
    print("=" * 60)
    print()
    
    with app.app_context():
        try:
            # Create user table (won't affect existing tables)
            print("[1/3] Creating user authentication table...")
            db.create_all()
            print("✓ User table created successfully")
            print()
            
            # Check if admin user already exists
            existing_user = User.query.first()
            if existing_user:
                print("⚠ Warning: User account(s) already exist.")
                print(f"   Found: {existing_user.username}")
                response = input("Create another user? (y/N): ").strip().lower()
                if response != 'y':
                    print("\nMigration cancelled.")
                    return 0
            
            # Prompt for admin credentials
            print("[2/3] Setting up admin account...")
            while True:
                username = input("Admin username: ").strip()
                if not username:
                    print("Username cannot be empty.")
                    continue
                    
                # Check if username exists
                if User.query.filter_by(username=username).first():
                    print(f"Username '{username}' already exists. Choose another.")
                    continue
                break
            
            # Get password with confirmation
            while True:
                password = getpass.getpass("Admin password: ")
                if len(password) < 6:
                    print("Password must be at least 6 characters.")
                    continue
                    
                password_confirm = getpass.getpass("Confirm password: ")
                if password != password_confirm:
                    print("Passwords do not match. Try again.")
                    continue
                break
            
            # Create admin user
            print("\n[3/3] Creating admin user...")
            admin = User(username=username)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            
            print()
            print("=" * 60)
            print("✅ Authentication enabled successfully!")
            print("=" * 60)
            print()
            print(f"Admin user: {username}")
            print("Login URL:  http://your-server:5000/login")
            print()
            print("⚠ IMPORTANT: Restart the dashboard service:")
            print("   sudo systemctl restart vm-monitor")
            print()
            print("Note: Agents will continue to work normally with API keys.")
            print("      Only the web UI now requires login.")
            print()
            
            return 0
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("\nMigration failed. No changes were made to existing data.")
            return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
