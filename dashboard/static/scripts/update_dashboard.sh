#!/bin/bash
# update_dashboard.sh - Update VM Dashboard (Preserving Data)
# Usage: ./update_dashboard.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

INSTALL_DIR="/opt/vm-agent-dashboard"
SERVICE_NAME="vm-agent-dashboard"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo ./update_dashboard.sh)${NC}"
    exit 1
fi

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

# Verify installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Error: Dashboard installation not found at $INSTALL_DIR${NC}"
    echo "Please run ./setup_dashboard.sh for fresh installation."
    exit 1
fi

echo -e "${GREEN}🔄 Updating VM Dashboard...${NC}"

# Find source directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"
if [ ! -d "$SOURCE_ROOT/dashboard" ]; then
    echo -e "${RED}Error: Dashboard source code not found in $SOURCE_ROOT/dashboard${NC}"
    exit 1
fi

# 1. Stop Service
print_step "Stopping service..."
if systemctl is-active --quiet $SERVICE_NAME; then
    systemctl stop $SERVICE_NAME
else
    echo "Service already stopped or not running."
fi

# 2. Backup Instance Data (DB & Configs)
print_step "Backing up data..."
BACKUP_DIR=$(mktemp -d)
if [ -d "$INSTALL_DIR/instance" ]; then
    cp -r "$INSTALL_DIR/instance" "$BACKUP_DIR/"
    echo "Backed up instance data to temp: $BACKUP_DIR"
else
    echo -e "${YELLOW}Warning: No instance/ directory found!${NC}"
fi

# 3. Update Code
print_step "Updating code..."
# Remove old code to ensure no stale files (but keep venv)
find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -not -name "venv" -not -name "instance" -exec rm -rf {} +
# Copy new code
cp -r "$SOURCE_ROOT/dashboard/"* "$INSTALL_DIR/"

# 4. Restore Instance Data
print_step "Restoring data..."
if [ -d "$BACKUP_DIR/instance" ]; then
    mkdir -p "$INSTALL_DIR/instance"
    cp -r "$BACKUP_DIR/instance/"* "$INSTALL_DIR/instance/" 2>/dev/null || true
    # Ensure keys are preserved if for some reason they were overwritten? 
    # (Actual restore happened above by overwriting anything we just copied)
fi
rm -rf "$BACKUP_DIR"

# 5. Fix Permissions
print_step "Fixing permissions..."
chown -R vm-agent:vm-agent "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
# Secure config files
[ -f "$INSTALL_DIR/instance/sms_config.json" ] && chmod 600 "$INSTALL_DIR/instance/sms_config.json"
[ -f "/etc/vm-dashboard.env" ] && chmod 600 "/etc/vm-dashboard.env"

# 6. Update Dependencies
print_step "Updating python dependencies..."
cd "$INSTALL_DIR"

# Ensure venv exists (in case of recovery)
if [ ! -d "venv" ]; then
    print_step "Creating virtual environment..."
    python3 -m venv venv
    chown -R vm-agent:vm-agent venv
fi

./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
./venv/bin/pip install gunicorn requests -q

# 7. Migrate Database
print_step "Running database migrations..."
# Using the same logic as setup - create_all() is idempotent for checking tables
# If we had real migrations (alembic), we'd run upgrade here.
# For now, just ensuring tables exist is enough.
export $(grep -v '^#' /etc/vm-dashboard.env | xargs)
sudo -E -u vm-agent ./venv/bin/python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('  Database schema verified')
"

# 8. Start Service
print_step "Restarting service..."
systemctl daemon-reload
systemctl start $SERVICE_NAME
systemctl status $SERVICE_NAME --no-pager | head -n 5

echo ""
echo -e "${GREEN}✅ Dashboard updated successfully!${NC}"
