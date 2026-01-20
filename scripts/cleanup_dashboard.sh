#!/bin/bash
# cleanup_dashboard.sh - Remove VM Dashboard from the system
# Usage: ./cleanup_dashboard.sh [--force]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

FORCE=false

# Parse args
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --force) FORCE=true ;;
        --help)
            echo "VM Dashboard Cleanup Script"
            echo "Usage: ./cleanup_dashboard.sh [--force]"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║            VM Dashboard - Cleanup Script                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$FORCE" != true ]; then
    echo -n -e "${RED}This will completely remove VM Dashboard. Proceed? [y/N]: ${NC}"
    read confirm
    if [[ ! "$confirm" =~ ^[Yy] ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo ""
echo -e "${GREEN}🧹 Removing VM Dashboard...${NC}"

# Stop and disable service
echo -e "  ${CYAN}Stopping service...${NC}"
if systemctl is-active --quiet vm-agent-dashboard 2>/dev/null; then
    sudo systemctl stop vm-agent-dashboard
fi
if systemctl is-enabled --quiet vm-agent-dashboard 2>/dev/null; then
    sudo systemctl disable vm-agent-dashboard
fi

# Kill any remaining gunicorn processes
sudo pkill -9 -f "gunicorn.*app:app" 2>/dev/null || true

# Remove service file
if [ -f "/etc/systemd/system/vm-agent-dashboard.service" ]; then
    echo -e "  ${CYAN}Removing service file...${NC}"
    sudo rm -f /etc/systemd/system/vm-agent-dashboard.service
fi

# Remove application files
echo -e "  ${CYAN}Removing application files...${NC}"
sudo rm -rf /opt/vm-agent-dashboard
sudo rm -f /etc/vm-dashboard.env

# Remove user
if id "vm-agent" &>/dev/null; then
    echo -e "  ${CYAN}Removing vm-agent user...${NC}"
    sudo userdel vm-agent 2>/dev/null || true
fi
if getent group vm-agent >/dev/null; then
    sudo groupdel vm-agent 2>/dev/null || true
fi

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Cleanup complete!                     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
