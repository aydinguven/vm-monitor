#!/usr/bin/env python3
"""
Database Migration Script for VM Dashboard

Safely migrates the SQLite database schema while preserving data.
Creates timestamped backups before making any changes.

Usage:
    python migrate_db.py [--dry-run]
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Schema definition - must match models.py
# Format: (column_name, sqlite_type, default_value)
EXPECTED_SCHEMA = {
    "vms": [
        ("id", "INTEGER PRIMARY KEY", None),
        ("hostname", "VARCHAR(255) NOT NULL UNIQUE", None),
        ("cloud_provider", "VARCHAR(50)", "'unknown'"),
        ("first_seen", "DATETIME", None),
        ("last_seen", "DATETIME", None),
        ("cpu_avg", "FLOAT", "0"),
        ("cpu_instant", "FLOAT", "0"),
        ("cpu_count", "INTEGER", "1"),
        ("ram_total_gb", "FLOAT", "0"),
        ("ram_used_gb", "FLOAT", "0"),
        ("ram_percent", "FLOAT", "0"),
        ("disk_usage", "JSON", None),
        ("os_name", "VARCHAR(100)", None),
        ("kernel", "VARCHAR(100)", None),
        ("arch", "VARCHAR(20)", None),
        ("ip_internal", "VARCHAR(45)", None),
        ("ip_external", "VARCHAR(45)", None),
        ("uptime_seconds", "INTEGER", None),
        ("agent_version", "VARCHAR(20)", None),
        ("containers", "JSON", None),
        ("pods", "JSON", None),
        ("swap_percent", "FLOAT", "0"),
        ("network_bytes_sent", "BIGINT", "0"),
        ("network_bytes_recv", "BIGINT", "0"),
        ("pending_updates", "INTEGER", "0"),
        ("open_ports", "JSON", None),
        ("ssh_failed_attempts", "INTEGER", "0"),
        ("top_processes", "JSON", None),
    ],
    "metrics": [
        ("id", "INTEGER PRIMARY KEY", None),
        ("vm_id", "INTEGER NOT NULL", None),
        ("timestamp", "DATETIME", None),
        ("cpu_avg", "FLOAT", None),
        ("cpu_instant", "FLOAT", None),
        ("ram_percent", "FLOAT", None),
        ("disk_usage", "JSON", None),
    ],
    "commands": [
        ("id", "INTEGER PRIMARY KEY", None),
        ("vm_id", "INTEGER NOT NULL", None),
        ("command", "VARCHAR(50)", None),
        ("args", "VARCHAR(255)", None),
        ("status", "VARCHAR(20)", "'pending'"),
        ("output", "TEXT", None),
        ("created_at", "DATETIME", None),
        ("executed_at", "DATETIME", None),
    ],
}


def get_db_path():
    """Get absolute path to the database."""
    script_dir = Path(__file__).parent.absolute()
    return script_dir / "instance" / "vm_metrics.db"


def get_backup_dir():
    """Get path to backup directory."""
    script_dir = Path(__file__).parent.absolute()
    return script_dir / "instance" / "backups"


def backup_database(db_path: Path, dry_run: bool = False) -> Path:
    """Create a timestamped backup of the database."""
    backup_dir = get_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"vm_metrics_{timestamp}.db"
    
    if dry_run:
        print(f"[DRY-RUN] Would backup {db_path} to {backup_path}")
        return backup_path
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_path)
    print(f"✅ Backup created: {backup_path}")
    
    # Keep only last 5 backups
    backups = sorted(backup_dir.glob("vm_metrics_*.db"), reverse=True)
    for old_backup in backups[5:]:
        old_backup.unlink()
        print(f"🗑️  Removed old backup: {old_backup.name}")
    
    return backup_path


def get_existing_columns(cursor, table_name: str) -> dict:
    """Get existing columns in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1]: row[2] for row in cursor.fetchall()}  # name: type


def migrate_table(cursor, table_name: str, expected_columns: list, dry_run: bool = False):
    """Add missing columns to a table."""
    existing = get_existing_columns(cursor, table_name)
    
    for col_name, col_type, default in expected_columns:
        # Skip primary key and already existing columns
        if col_name in existing:
            continue
        
        # Build ALTER statement
        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type.split()[0]}"
        if default is not None:
            sql += f" DEFAULT {default}"
        
        if dry_run:
            print(f"[DRY-RUN] Would execute: {sql}")
        else:
            print(f"  Adding column: {col_name}...")
            cursor.execute(sql)


def table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def ensure_tables_exist(cursor, dry_run: bool = False):
    """Create tables if they don't exist."""
    tables_to_create = []
    
    if not table_exists(cursor, 'vms'):
        tables_to_create.append('vms')
    if not table_exists(cursor, 'metrics'):
        tables_to_create.append('metrics')
    if not table_exists(cursor, 'commands'):
        tables_to_create.append('commands')
    
    if not tables_to_create:
        return  # All tables exist
    
    if dry_run:
        print(f"[DRY-RUN] Would create tables: {', '.join(tables_to_create)}")
        return
    
    print(f"Creating tables: {', '.join(tables_to_create)}...")
    
    if 'vms' in tables_to_create:
        cursor.execute("""
            CREATE TABLE vms (
                id INTEGER PRIMARY KEY,
                hostname VARCHAR(255) NOT NULL UNIQUE,
                cloud_provider VARCHAR(50) DEFAULT 'unknown',
                first_seen DATETIME,
                last_seen DATETIME,
                cpu_avg FLOAT DEFAULT 0,
                cpu_instant FLOAT DEFAULT 0,
                cpu_count INTEGER DEFAULT 1,
                ram_total_gb FLOAT DEFAULT 0,
                ram_used_gb FLOAT DEFAULT 0,
                ram_percent FLOAT DEFAULT 0,
                disk_usage JSON
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_vms_hostname ON vms(hostname)")
    
    if 'metrics' in tables_to_create:
        cursor.execute("""
            CREATE TABLE metrics (
                id INTEGER PRIMARY KEY,
                vm_id INTEGER NOT NULL,
                timestamp DATETIME,
                cpu_avg FLOAT,
                cpu_instant FLOAT,
                ram_percent FLOAT,
                disk_usage JSON,
                FOREIGN KEY (vm_id) REFERENCES vms(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_metrics_vm_id ON metrics(vm_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_metrics_timestamp ON metrics(timestamp)")
    
    if 'commands' in tables_to_create:
        cursor.execute("""
            CREATE TABLE commands (
                id INTEGER PRIMARY KEY,
                vm_id INTEGER NOT NULL,
                command VARCHAR(50),
                args VARCHAR(255),
                status VARCHAR(20) DEFAULT 'pending',
                output TEXT,
                created_at DATETIME,
                executed_at DATETIME,
                FOREIGN KEY (vm_id) REFERENCES vms(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_commands_vm_id ON commands(vm_id)")
    
    print("  ✅ Tables created")


def validate_data(cursor, dry_run: bool = False) -> bool:
    """Validate data integrity after migration."""
    try:
        # In dry-run mode, just check tables that exist
        vm_count = 0
        metric_count = 0
        cmd_count = 0
        
        if table_exists(cursor, 'vms'):
            cursor.execute("SELECT COUNT(*) FROM vms")
            vm_count = cursor.fetchone()[0]
        elif not dry_run:
            raise Exception("vms table does not exist")
        
        if table_exists(cursor, 'metrics'):
            cursor.execute("SELECT COUNT(*) FROM metrics")
            metric_count = cursor.fetchone()[0]
        elif not dry_run:
            raise Exception("metrics table does not exist")
        
        if table_exists(cursor, 'commands'):
            cursor.execute("SELECT COUNT(*) FROM commands")
            cmd_count = cursor.fetchone()[0]
        elif not dry_run:
            raise Exception("commands table does not exist")
        
        print(f"✅ Validation passed: {vm_count} VMs, {metric_count} metrics, {cmd_count} commands")
        return True
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


def restore_backup(backup_path: Path, db_path: Path):
    """Restore database from backup."""
    print(f"🔄 Restoring from backup: {backup_path}")
    shutil.copy2(backup_path, db_path)
    print("✅ Database restored")


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=" * 50)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 50)
    
    db_path = get_db_path()
    
    # Check if database exists
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Creating new database with schema...")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        ensure_tables_exist(cursor, dry_run)
        for table_name, columns in EXPECTED_SCHEMA.items():
            migrate_table(cursor, table_name, columns, dry_run)
        conn.commit()
        conn.close()
        print("✅ New database created successfully")
        return 0
    
    # Backup existing database
    backup_path = backup_database(db_path, dry_run)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure tables exist
        ensure_tables_exist(cursor, dry_run)
        
        # Migrate each table
        print("\n📊 Checking schema...")
        for table_name, columns in EXPECTED_SCHEMA.items():
            print(f"\nTable: {table_name}")
            migrate_table(cursor, table_name, columns, dry_run)
        
        if not dry_run:
            conn.commit()
        
        # Validate
        print("\n🔍 Validating data...")
        if not validate_data(cursor, dry_run):
            raise Exception("Data validation failed")
        
        conn.close()
        print("\n✅ Migration completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        if not dry_run and backup_path.exists():
            restore_backup(backup_path, db_path)
        return 1


if __name__ == "__main__":
    sys.exit(main())

