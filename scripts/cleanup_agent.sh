#!/bin/bash
# cleanup_agent.sh - Remove VM Agent from the system
# Usage: ./cleanup_agent.sh [--force]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

export NC

# Reset terminal on exit (Fix formatting issues)
cleanup_term() {
    echo -e "${NC}"
}
trap cleanup_term EXIT

FORCE=false

# Parse args
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --force) FORCE=true ;;
        --help)
            echo "VM Agent Cleanup Script"
            echo "Usage: ./cleanup_agent.sh [--force]"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              VM Agent - Cleanup Script                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$FORCE" != true ]; then
    echo -n -e "${RED}This will completely remove VM Agent. Proceed? [y/N]: ${NC}"
    read confirm
    if [[ ! "$confirm" =~ ^[Yy] ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo ""
echo -e "${GREEN}🧹 Removing VM Agent...${NC}"

# Stop and disable service
echo -e "  ${CYAN}Stopping service...${NC}"
if systemctl is-active --quiet vm-agent 2>/dev/null; then
    sudo systemctl stop vm-agent
fi
if systemctl is-enabled --quiet vm-agent 2>/dev/null; then
    sudo systemctl disable vm-agent
fi

# Kill any remaining processes
sudo pkill -9 -f "agent.py" 2>/dev/null || true

# Remove service file
if [ -f "/etc/systemd/system/vm-agent.service" ]; then
    echo -e "  ${CYAN}Removing service file...${NC}"
    sudo rm -f /etc/systemd/system/vm-agent.service
fi

# Remove application files
echo -e "  ${CYAN}Removing application files...${NC}"
sudo rm -rf /opt/vm-agent
sudo rm -f /etc/vm-agent.conf
sudo rm -rf /etc/vm-agent

# Remove Users, Groups, Sudoers (v1.44)
echo -e "  ${CYAN}Removing user and permissions...${NC}"
sudo rm -f /etc/sudoers.d/vm-agent
sudo rm -f /usr/local/bin/vm-agent-sysupdate
if id "vm-agent" &>/dev/null; then
    sudo userdel vm-agent 2>/dev/null || true
fi
if getent group vm-agent >/dev/null; then
    sudo groupdel vm-agent 2>/dev/null || true
fi

# Remove temp files
sudo rm -rf /tmp/vm-agent* 2>/dev/null || true

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Cleanup complete!                     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
