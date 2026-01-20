#!/bin/bash
# cleanup.sh - Completely remove VM Agent and Dashboard from the system

echo "🧹 Starting cleanup..."

# --- 1. Stop and Disable Services ---
echo "Stopping services..."
for service in vm-agent vm-agent-dashboard; do
    if systemctl is-active --quiet $service; then
        echo "  Stopping $service..."
        sudo systemctl stop $service
    fi
    if systemctl is-enabled --quiet $service; then
        echo "  Disabling $service..."
        sudo systemctl disable $service
    fi
    # Force kill residue
    if [ "$service" == "vm-agent-dashboard" ]; then
        sudo pkill -9 -f gunicorn || true
    fi
    if [ "$service" == "vm-agent" ]; then
        sudo pkill -9 -f agent.py || true
    fi
    
    # Remove service file
    if [ -f "/etc/systemd/system/$service.service" ]; then
        echo "  Removing service file for $service..."
        sudo rm "/etc/systemd/system/$service.service"
    fi
done

sudo systemctl daemon-reload

# --- 2. Remove Files & Directories ---
echo "Removing application files..."
sudo rm -rf /opt/vm-agent
sudo rm -rf /opt/vm-agent-dashboard
sudo rm -f /etc/vm-agent.conf

# --- 3. Remove Users ---
echo "Removing users..."
if id "vm-agent" &>/dev/null; then
    sudo userdel vm-agent
    echo "  Removed user: vm-agent"
fi

# --- 4. Cleanup Temp Files ---
sudo rm -rf /tmp/vm-agent*

echo "✅ Cleanup complete! System is clean."
