#!/bin/bash
# cleanup.sh - Remove VM Agent and/or Dashboard from the system
# Usage: ./cleanup.sh           (removes both)
#        ./cleanup.sh --agent   (removes agent only)
#        ./cleanup.sh --dashboard (removes dashboard only)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Parse args
REMOVE_AGENT=false
REMOVE_DASHBOARD=false

if [ $# -eq 0 ]; then
    REMOVE_AGENT=true
    REMOVE_DASHBOARD=true
else
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --agent) REMOVE_AGENT=true ;;
            --dashboard) REMOVE_DASHBOARD=true ;;
            --all) REMOVE_AGENT=true; REMOVE_DASHBOARD=true ;;
            --force) FORCE=true ;;
            --help)
                echo "VM Monitor Cleanup Script"
                echo ""
                echo "Usage:"
                echo "  ./cleanup.sh             Remove both agent and dashboard"
                echo "  ./cleanup.sh --agent     Remove agent only"
                echo "  ./cleanup.sh --dashboard Remove dashboard only"
                echo "  ./cleanup.sh --all       Remove both (same as no args)"
                echo "  ./cleanup.sh --force     Skip confirmation prompt"
                exit 0
                ;;
            *) echo "Unknown parameter: $1"; exit 1 ;;
        esac
        shift
    done
fi

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              VM Monitor - Cleanup Script                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$REMOVE_AGENT" = true ]; then
    echo -e "${YELLOW}Will remove: Agent${NC}"
fi
if [ "$REMOVE_DASHBOARD" = true ]; then
    echo -e "${YELLOW}Will remove: Dashboard${NC}"
fi
echo ""

if [ "$FORCE" != true ]; then
    echo -n -e "${RED}Are you sure you want to proceed? [y/N]: ${NC}"
    read confirm
    if [[ ! "$confirm" =~ ^[Yy] ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo ""

# ============================================================================
# Agent Cleanup
# ============================================================================
if [ "$REMOVE_AGENT" = true ]; then
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
    
    # Remove temp files
    sudo rm -rf /tmp/vm-agent* 2>/dev/null || true
    
    echo -e "  ${GREEN}✓ Agent removed${NC}"
fi

# ============================================================================
# Dashboard Cleanup
# ============================================================================
if [ "$REMOVE_DASHBOARD" = true ]; then
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
    
    echo -e "  ${GREEN}✓ Dashboard removed${NC}"
fi

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Cleanup complete!                     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
