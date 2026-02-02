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

INSTALL_DIR="/opt/vm-monitor"
SERVICE_NAME="vm-monitor"

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
cp "$SOURCE_ROOT/dashboard/migrate_add_balloon.py" "$INSTALL_DIR/" 2>/dev/null || true

# 3b. Copy Agent Files for Auto-Update (v1.46+)
print_step "Packaging agent for auto-update..."
mkdir -p "$INSTALL_DIR/static/downloads"
mkdir -p "$INSTALL_DIR/static/scripts"
# Copy agent files
cp "$SOURCE_ROOT/agent/agent.py" "$INSTALL_DIR/static/downloads/"
cp "$SOURCE_ROOT/agent/requirements.txt" "$INSTALL_DIR/static/downloads/" 2>/dev/null || true
# Copy installer scripts
cp "$SOURCE_ROOT/scripts/setup.sh" "$INSTALL_DIR/static/scripts/"
cp "$SOURCE_ROOT/agent/setup.ps1" "$INSTALL_DIR/static/scripts/" 2>/dev/null || true
echo "  Agent v$(grep 'AGENT_VERSION = ' "$SOURCE_ROOT/agent/agent.py" | cut -d'"' -f2) packaged."

# 4. Restore Instance Data
print_step "Restoring data..."
if [ -d "$BACKUP_DIR/instance" ]; then
    mkdir -p "$INSTALL_DIR/instance"
    cp -r "$BACKUP_DIR/instance/"* "$INSTALL_DIR/instance/" 2>/dev/null || true
fi
rm -rf "$BACKUP_DIR"

# 5. Migration (Env -> JSON)
if [ ! -f "$INSTALL_DIR/instance/config.json" ]; then
    ENV_FILE=""
    if [ -f "/etc/vm-dashboard.env" ]; then
        ENV_FILE="/etc/vm-dashboard.env"
    elif [ -f "/etc/vm-dashboard.env.bak" ]; then
        ENV_FILE="/etc/vm-dashboard.env.bak"
    fi

    if [ -n "$ENV_FILE" ]; then
        print_step "Migrating legacy .env ($ENV_FILE) to config.json..."
        # Source the env file
        set -a; source "$ENV_FILE"; set +a
        
        # Create config.json
        mkdir -p "$INSTALL_DIR/instance"
        cat > "$INSTALL_DIR/instance/config.json" <<EOF
{
  "secret_key": "$FLASK_SECRET_KEY",
  "api_key": "$VM_DASHBOARD_API_KEY",
  "timezone": "Europe/Istanbul"
}
EOF
        echo "Migration complete."
    fi
fi

# 6. Fix Permissions
print_step "Fixing permissions (Hardening)..."
chown -R vm-monitor:vm-monitor "$INSTALL_DIR"
# 750/640 for hardening, excluding venv
find "$INSTALL_DIR" -type d -not -path "$INSTALL_DIR/venv*" -exec chmod 750 {} \;
find "$INSTALL_DIR" -type f -not -path "$INSTALL_DIR/venv*" -exec chmod 640 {} \;

# Ensure venv executables
chmod -R 755 "$INSTALL_DIR/venv"

# Secrets
[ -f "$INSTALL_DIR/instance/config.json" ] && chmod 600 "$INSTALL_DIR/instance/config.json"

# 6. Update Dependencies
print_step "Updating python dependencies..."
cd "$INSTALL_DIR"

# Ensure venv exists (in case of recovery)
if [ ! -d "venv" ]; then
    print_step "Creating virtual environment..."
    python3 -m venv venv
    chown -R vm-monitor:vm-monitor venv
fi

./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
./venv/bin/pip install gunicorn requests -q

# 7. Migrate Database
print_step "Running database migrations..."
sudo -u vm-monitor ./venv/bin/python -c "
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
