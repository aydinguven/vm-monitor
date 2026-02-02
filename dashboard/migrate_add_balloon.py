#!/usr/bin/env python3
"""
Migration Script: Add Balloon Detection Support
Usage: sudo /opt/vm-monitor/venv/bin/python /opt/vm-monitor/migrate_add_balloon.py

This script updates the database schema to support memory ballooning detection.
It adds the 'balloon_enabled' column to the 'vms' table.
"""

import sys
import os
import sqlite3

# Add current directory to path to find app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SQLALCHEMY_DATABASE_URI

def main():
    print("=" * 60)
    print("VM Monitor - Balloon Detection Migration")
    print("=" * 60)
    print()

    # Handle SQLite directly for reliability without loading half-migrated app context
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite:///"):
        db_path = SQLALCHEMY_DATABASE_URI.replace("sqlite:///", "")
        
        # Handle relative path (relative to instance folder usually)
        if not os.path.isabs(db_path):
             # Try instance folder first (default layout)
            instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", db_path)
            if os.path.exists(instance_path):
                db_path = instance_path
            else:
                # Try relative to current script
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        
        print(f"Target Database: {db_path}")
        
        if not os.path.exists(db_path):
            print(f"❌ Error: Database not found at {db_path}")
            return 1
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if column exists
            cursor.execute("PRAGMA table_info(vms)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "balloon_enabled" in columns:
                print("✓ Column 'balloon_enabled' already exists. No changes needed.")
            else:
                print("[1/1] Adding 'balloon_enabled' column...")
                cursor.execute("ALTER TABLE vms ADD COLUMN balloon_enabled BOOLEAN DEFAULT 0")
                conn.commit()
                print("✓ Column added successfully")
            
            conn.close()
            print()
            print("=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print("Please restart the dashboard service:")
            print("   sudo systemctl restart vm-monitor")
            print()
            return 0
            
        except Exception as e:
            print(f"\n❌ Migration Error: {e}")
            return 1
    else:
        # Non-SQLite databases (PostgreSQL/MySQL)
        print("⚠ This script is optimized for SQLite. For SQL/Postgres, please run manually:")
        print("ALTER TABLE vms ADD COLUMN balloon_enabled BOOLEAN DEFAULT FALSE;")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
