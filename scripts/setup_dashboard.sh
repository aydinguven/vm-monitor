#!/bin/bash
# setup_dashboard.sh - Interactive VM Dashboard Installer
# Usage: ./setup_dashboard.sh                    (interactive mode)
#        ./setup_dashboard.sh --batch [options]  (non-interactive mode)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Defaults
INSTALL_DIR="/opt/vm-agent-dashboard"
PORT=5000
API_KEY=""
SECRET_KEY=""
BATCH_MODE=false

# Feature flags (all enabled by default)
FEATURE_COMMANDS=true
FEATURE_SMS=false
FEATURE_ALERTS=true
FEATURE_CONTAINERS=true
FEATURE_PODS=true

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --batch) BATCH_MODE=true ;;
        --port) PORT="$2"; shift ;;
        --api-key) API_KEY="$2"; shift ;;
        --secret-key) SECRET_KEY="$2"; shift ;;
        --no-commands) FEATURE_COMMANDS=false ;;
        --no-sms) FEATURE_SMS=false ;;
        --enable-sms) FEATURE_SMS=true ;;
        --no-alerts) FEATURE_ALERTS=false ;;
        --no-containers) FEATURE_CONTAINERS=false ;;
        --no-pods) FEATURE_PODS=false ;;
        --help)
            echo "VM Dashboard Setup - Interactive installer"
            echo ""
            echo "Usage:"
            echo "  ./setup_dashboard.sh                    Interactive mode"
            echo "  ./setup_dashboard.sh --batch [options]  Non-interactive mode"
            echo ""
            echo "Options (batch mode):"
            echo "  --port PORT           Dashboard port (default: 5000)"
            echo "  --api-key KEY         API key for agents (auto-generated if not set)"
            echo "  --secret-key KEY      Flask secret key (auto-generated if not set)"
            echo "  --no-commands         Disable remote command execution"
            echo "  --enable-sms          Enable SMS alerts"
            echo "  --no-alerts           Disable alert thresholds"
            echo "  --no-containers       Disable container display"
            echo "  --no-pods             Disable Kubernetes pod display"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Generate secure random key
generate_key() {
    openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
}

# Banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║          VM Monitoring Dashboard - Setup Wizard           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Prompt functions
prompt_text() {
    local prompt="$1"
    local default="$2"
    local result=""
    
    if [ -n "$default" ]; then
        read -p "$(echo -e ${BLUE}$prompt ${YELLOW}[$default]${NC}: )" result
        result="${result:-$default}"
    else
        read -p "$(echo -e ${BLUE}$prompt${NC}: )" result
    fi
    echo "$result"
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local result=""
    
    local hint="[y/N]"
    [ "$default" = "y" ] && hint="[Y/n]"
    
    read -p "$(echo -e ${BLUE}$prompt ${YELLOW}$hint${NC}: )" result
    result="${result:-$default}"
    
    [[ "$result" =~ ^[Yy] ]] && echo "true" || echo "false"
}

# Interactive mode
run_interactive() {
    print_banner
    
    echo -e "${GREEN}Step 1: Basic Configuration${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    PORT=$(prompt_text "Dashboard port" "5000")
    
    local default_api_key=$(generate_key)
    echo -e "${YELLOW}Auto-generated API Key: ${default_api_key}${NC}"
    API_KEY=$(prompt_text "API Key (press Enter to use generated key)" "$default_api_key")
    
    local default_secret=$(generate_key)
    SECRET_KEY=$(prompt_text "Flask Secret Key (press Enter to auto-generate)" "$default_secret")
    
    echo ""
    echo -e "${GREEN}Step 2: Feature Configuration${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}Enable or disable dashboard features:${NC}"
    echo ""
    
    FEATURE_COMMANDS=$(prompt_yes_no "Enable remote command execution?" "y")
    FEATURE_SMS=$(prompt_yes_no "Enable SMS alerts (requires provider config)?" "n")
    FEATURE_ALERTS=$(prompt_yes_no "Enable resource alerts (CPU/RAM/Disk thresholds)?" "y")
    FEATURE_CONTAINERS=$(prompt_yes_no "Display container information?" "y")
    FEATURE_PODS=$(prompt_yes_no "Display Kubernetes pod information?" "y")
    
    echo ""
    echo -e "${GREEN}Step 3: Confirm Settings${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  Port:         ${CYAN}$PORT${NC}"
    echo -e "  API Key:      ${CYAN}${API_KEY:0:8}...${NC}"
    echo -e "  Commands:     $([ "$FEATURE_COMMANDS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  SMS Alerts:   $([ "$FEATURE_SMS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  Alerts:       $([ "$FEATURE_ALERTS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  Containers:   $([ "$FEATURE_CONTAINERS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  K8s Pods:     $([ "$FEATURE_PODS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo ""
    
    local confirm=$(prompt_yes_no "Proceed with installation?" "y")
    if [ "$confirm" != "true" ]; then
        echo -e "${YELLOW}Installation cancelled.${NC}"
        exit 0
    fi
}

# Main installation
install_dashboard() {
    echo ""
    echo -e "${GREEN}🚀 Installing VM Dashboard...${NC}"
    
    # 1. Install dependencies
    echo -e "${BLUE}[1/6] Installing system dependencies...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3-venv python3-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y -q python3 python3-pip
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y -q python3 python3-pip
    fi
    
    # 2. Create user
    echo -e "${BLUE}[2/6] Creating vm-agent user...${NC}"
    if ! getent group vm-agent >/dev/null; then
        sudo groupadd -r vm-agent
    fi
    if ! id "vm-agent" &>/dev/null; then
        sudo useradd -r -g vm-agent -d "$INSTALL_DIR" -s /sbin/nologin vm-agent
    fi
    
    # 3. Setup directories
    echo -e "${BLUE}[3/6] Setting up directories...${NC}"
    sudo mkdir -p "$INSTALL_DIR/instance"
    
    # 4. Copy dashboard code
    echo -e "${BLUE}[4/6] Installing dashboard code...${NC}"
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"
    
    if [ -d "$SOURCE_ROOT/dashboard" ]; then
        sudo cp -r "$SOURCE_ROOT/dashboard/"* "$INSTALL_DIR/"
    else
        echo -e "${RED}Error: Cannot find dashboard source. Run from vm-monitor directory.${NC}"
        exit 1
    fi
    
    # 5. Setup Python environment
    echo -e "${BLUE}[5/6] Setting up Python environment...${NC}"
    cd "$INSTALL_DIR"
    sudo python3 -m venv venv
    sudo ./venv/bin/pip install --upgrade pip
    sudo ./venv/bin/pip install -r requirements.txt
    sudo ./venv/bin/pip install gunicorn requests
    
    # Create instance directory and features.json
    sudo mkdir -p "$INSTALL_DIR/instance"
    sudo bash -c "cat > $INSTALL_DIR/instance/features.json" <<EOF
{
    "commands": $FEATURE_COMMANDS,
    "sms": $FEATURE_SMS,
    "alerts": $FEATURE_ALERTS,
    "containers": $FEATURE_CONTAINERS,
    "pods": $FEATURE_PODS,
    "auto_update": true,
    "latency": false
}
EOF
    
    # Create main configuration (config.json)
    sudo bash -c "cat > $INSTALL_DIR/instance/config.json" <<EOF
{
  "secret_key": "$SECRET_KEY",
  "api_key": "$API_KEY",
  "timezone": "Europe/Istanbul"
}
EOF
    sudo chmod 600 "$INSTALL_DIR/instance/config.json"
    
    # 6. Initialize database
    echo -e "${BLUE}[6/7] Initializing database...${NC}"
    cd "$INSTALL_DIR"
    
    # (Environment variables no longer needed as config.json is present)
    
    # Initialize database using Flask shell
    sudo -E ./venv/bin/python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('  Database tables created')
"
    
    # Set ownership
    # Set ownership and permissions (Hardened)
    sudo chown -R vm-agent:vm-agent "$INSTALL_DIR"
    
    # 750: User rwx, Group rx, Other -
    # 640: User rw, Group r, Other -
    # Exclude venv from file permission changes to avoid breaking binaries/libs
    sudo find "$INSTALL_DIR" -type d -not -path "$INSTALL_DIR/venv*" -exec chmod 750 {} \;
    sudo find "$INSTALL_DIR" -type f -not -path "$INSTALL_DIR/venv*" -exec chmod 640 {} \;
    
    # Ensure venv executables are correct (pip usually handles this, but just in case)
    # sudo chmod -R 755 "$INSTALL_DIR/venv/bin" # Leave venv permissions as is from creation
    
    # Secrets (600)
    sudo chmod 600 "$INSTALL_DIR/instance/config.json"
    
    # 7. Setup systemd service
    echo -e "${BLUE}[7/7] Configuring systemd service...${NC}"
    sudo bash -c "cat > /etc/systemd/system/vm-agent-dashboard.service" <<EOF
[Unit]
Description=VM Monitoring Dashboard
After=network.target

[Service]
Type=simple
User=vm-agent
Group=vm-agent
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:$PORT app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable vm-agent-dashboard
    sudo systemctl restart vm-agent-dashboard
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            ✅ Dashboard installed successfully!           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Dashboard:  ${CYAN}http://$(hostname -I | awk '{print $1}'):$PORT${NC}"
    echo -e "  API Key:    ${CYAN}$API_KEY${NC}"
    echo -e "  Features:   ${CYAN}$INSTALL_DIR/instance/features.json${NC}"
    echo ""
    echo -e "${YELLOW}Use this API Key when setting up agents!${NC}"
    echo ""
    echo -e "  Service:    ${CYAN}sudo systemctl status vm-agent-dashboard${NC}"
    echo -e "  Logs:       ${CYAN}sudo journalctl -u vm-agent-dashboard -f${NC}"
    echo ""
}

# Main
if [ "$BATCH_MODE" = true ]; then
    # Generate keys if not provided
    [ -z "$API_KEY" ] && API_KEY=$(generate_key)
    [ -z "$SECRET_KEY" ] && SECRET_KEY=$(generate_key)
else
    run_interactive
fi

install_dashboard
