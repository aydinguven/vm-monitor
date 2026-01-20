#!/bin/bash
# setup.sh - Interactive VM Agent Installer for Linux
# Usage: ./setup.sh                    (interactive mode)
#        ./setup.sh --batch [options]  (non-interactive mode)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Defaults
SERVER_URL=""
API_KEY=""
INTERVAL=30
INSTALL_DIR="/opt/vm-agent"
BATCH_MODE=false

# Feature flags (all enabled by default)
FEATURE_CONTAINERS=true
FEATURE_PODS=true
FEATURE_COMMANDS=true
FEATURE_AUTO_UPDATE=true

# Parse command line arguments for batch mode
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --batch) BATCH_MODE=true ;;
        --server) SERVER_URL="$2"; shift ;;
        --key) API_KEY="$2"; shift ;;
        --interval) INTERVAL="$2"; shift ;;
        --no-containers) FEATURE_CONTAINERS=false ;;
        --no-pods) FEATURE_PODS=false ;;
        --no-commands) FEATURE_COMMANDS=false ;;
        --no-auto-update) FEATURE_AUTO_UPDATE=false ;;
        --help)
            echo "VM Agent Setup - Interactive installer"
            echo ""
            echo "Usage:"
            echo "  ./setup.sh                    Interactive mode"
            echo "  ./setup.sh --batch [options]  Non-interactive mode"
            echo ""
            echo "Options (batch mode):"
            echo "  --server URL        Dashboard server URL (required)"
            echo "  --key KEY           API key (required)"
            echo "  --interval SECONDS  Collection interval (default: 30)"
            echo "  --no-containers     Disable container discovery"
            echo "  --no-pods           Disable Kubernetes pod discovery"
            echo "  --no-commands       Disable remote command execution"
            echo "  --no-auto-update    Disable automatic agent updates"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║           VM Monitoring Agent - Setup Wizard              ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Functions for prompts
prompt_text() {
    local prompt="$1"
    local default="$2"
    local result=""
    
    if [ -n "$default" ]; then
        read -p "$(echo -e ${BLUE}$prompt ${YELLOW}[$default]${NC}: )" result
        result="${result:-$default}"
    else
        while [ -z "$result" ]; do
            read -p "$(echo -e ${BLUE}$prompt${NC}: )" result
            if [ -z "$result" ]; then
                echo -e "${RED}This field is required.${NC}"
            fi
        done
    fi
    echo "$result"
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"  # y or n
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
    
    echo -e "${GREEN}Step 1: Dashboard Connection${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    SERVER_URL=$(prompt_text "Dashboard URL (e.g., http://monitor.example.com:5000)" "")
    API_KEY=$(prompt_text "API Key" "")
    INTERVAL=$(prompt_text "Collection interval (seconds)" "30")
    
    echo ""
    echo -e "${GREEN}Step 2: Feature Configuration${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}Enable or disable optional features:${NC}"
    echo ""
    
    FEATURE_CONTAINERS=$(prompt_yes_no "Enable container discovery (Docker/Podman)?" "y")
    FEATURE_PODS=$(prompt_yes_no "Enable Kubernetes pod discovery?" "y")
    FEATURE_COMMANDS=$(prompt_yes_no "Enable remote command execution?" "y")
    FEATURE_AUTO_UPDATE=$(prompt_yes_no "Enable automatic agent updates?" "y")
    
    echo ""
    echo -e "${GREEN}Step 3: Confirm Settings${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  Server:       ${CYAN}$SERVER_URL${NC}"
    echo -e "  API Key:      ${CYAN}${API_KEY:0:4}****${NC}"
    echo -e "  Interval:     ${CYAN}${INTERVAL}s${NC}"
    echo -e "  Containers:   $([ "$FEATURE_CONTAINERS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  K8s Pods:     $([ "$FEATURE_PODS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  Commands:     $([ "$FEATURE_COMMANDS" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo -e "  Auto-Update:  $([ "$FEATURE_AUTO_UPDATE" = "true" ] && echo -e "${GREEN}✓ Enabled${NC}" || echo -e "${RED}✗ Disabled${NC}")"
    echo ""
    
    local confirm=$(prompt_yes_no "Proceed with installation?" "y")
    if [ "$confirm" != "true" ]; then
        echo -e "${YELLOW}Installation cancelled.${NC}"
        exit 0
    fi
}

# Validation
validate_inputs() {
    if [ -z "$SERVER_URL" ]; then
        echo -e "${RED}Error: Server URL is required${NC}"
        exit 1
    fi
    if [ -z "$API_KEY" ]; then
        echo -e "${RED}Error: API key is required${NC}"
        exit 1
    fi
}

# Main installation
install_agent() {
    echo ""
    echo -e "${GREEN}🚀 Installing VM Agent...${NC}"
    
    # 1. Install system dependencies
    echo -e "${BLUE}[1/6] Installing system dependencies...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3-venv python3-pip curl
    elif command -v yum &> /dev/null; then
        sudo yum install -y -q python3 python3-pip curl
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y -q python3 python3-pip curl
    fi
    
    # 2. Setup directories
    echo -e "${BLUE}[2/6] Setting up directories...${NC}"
    sudo mkdir -p "$INSTALL_DIR"
    sudo mkdir -p /etc/vm-agent/kubeconfigs
    
    # 3. Discover kubeconfigs (if pods enabled)
    if [ "$FEATURE_PODS" = "true" ]; then
        echo -e "${BLUE}[3/6] Discovering kubeconfigs...${NC}"
        for cfg in /etc/kubernetes/admin.conf /etc/rancher/k3s/k3s.yaml; do
            if [ -f "$cfg" ]; then
                name=$(basename "$cfg")
                sudo cp "$cfg" "/etc/vm-agent/kubeconfigs/$name"
                echo "  Found: $cfg"
            fi
        done
        for user_home in /home/*; do
            if [ -d "$user_home/.kube" ] && [ -f "$user_home/.kube/config" ]; then
                user=$(basename "$user_home")
                sudo cp "$user_home/.kube/config" "/etc/vm-agent/kubeconfigs/${user}.kubeconfig"
                echo "  Found: $user_home/.kube/config"
            fi
        done
        sudo chmod 600 /etc/vm-agent/kubeconfigs/* 2>/dev/null || true
    else
        echo -e "${BLUE}[3/6] Skipping kubeconfig discovery (pods disabled)${NC}"
    fi
    
    # 4. Copy agent code
    echo -e "${BLUE}[4/6] Installing agent code...${NC}"
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"
    
    if [ -d "$SOURCE_ROOT/agent" ]; then
        sudo cp -r "$SOURCE_ROOT/agent/"* "$INSTALL_DIR/"
    else
        echo -e "${RED}Error: Cannot find agent source. Run this script from the vm-monitor directory.${NC}"
        exit 1
    fi
    
    # 5. Setup Python venv and install deps
    echo -e "${BLUE}[5/6] Setting up Python environment...${NC}"
    cd "$INSTALL_DIR"
    
    if sudo python3 -m venv venv 2>/dev/null; then
        PYTHON="$INSTALL_DIR/venv/bin/python"
        PIP="$INSTALL_DIR/venv/bin/pip"
        sudo "$PIP" install --upgrade pip -q 2>/dev/null || true
    else
        PYTHON="python3"
        PIP="pip3"
    fi
    
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        sudo "$PIP" install -r "$INSTALL_DIR/requirements.txt" -q --break-system-packages 2>/dev/null || \
        sudo "$PIP" install -r "$INSTALL_DIR/requirements.txt" -q 2>/dev/null || \
        sudo pip3 install psutil requests distro packaging -q --break-system-packages 2>/dev/null || \
        sudo pip3 install psutil requests distro packaging -q
    fi
    
    # 6. Create configuration (JSON)
    echo -e "${BLUE}[6/6] Generating configuration...${NC}"
    sudo bash -c "cat > $INSTALL_DIR/agent_config.json" <<EOF
{
  "server_url": "$SERVER_URL",
  "api_key": "$API_KEY",
  "interval": $INTERVAL,
  "hostname": "$(hostname)",
  "auto_update": $FEATURE_AUTO_UPDATE,
  "features": {
    "containers": $FEATURE_CONTAINERS,
    "pods": $FEATURE_PODS,
    "commands": $FEATURE_COMMANDS
  }
}
EOF
    sudo chmod 600 "$INSTALL_DIR/agent_config.json"
    
    # Setup systemd service
    if [ -f "$INSTALL_DIR/venv/bin/python" ]; then
        SERVICE_PYTHON="$INSTALL_DIR/venv/bin/python"
    else
        SERVICE_PYTHON="/usr/bin/python3"
    fi
    
    sudo bash -c "cat > /etc/systemd/system/vm-agent.service" <<EOF
[Unit]
Description=VM Monitoring Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$SERVICE_PYTHON $INSTALL_DIR/agent.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable vm-agent
    sudo systemctl restart vm-agent
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✅ Agent installed successfully!             ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Config:   ${CYAN}$INSTALL_DIR/agent_config.json${NC}"
    echo -e "  Service:  ${CYAN}sudo systemctl status vm-agent${NC}"
    echo -e "  Logs:     ${CYAN}sudo journalctl -u vm-agent -f${NC}"
    echo ""
}

# Main
if [ "$BATCH_MODE" = true ]; then
    validate_inputs
else
    run_interactive
fi

install_agent
