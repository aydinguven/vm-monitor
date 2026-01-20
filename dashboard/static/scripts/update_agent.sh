#!/bin/bash
# update_agent.sh - Force update VM agent on read-only systems

echo "Force updating VM Agent..."

# 1. Remount /opt as RW if possible
echo "Attempting to remount /opt as RW..."
if mount | grep -q "/opt"; then
    mount -o remount,rw /opt || echo "Warning: Remount failed, trying chattr..."
fi

# 2. Handle immutable files
if [ -f "/opt/vm-agent/agent.py" ]; then
    echo "Checking for immutable attributes..."
    chattr -i /opt/vm-agent/agent.py || true
fi

# 3. Download latest agent to temp
echo "Downloading latest agent v1.12+..."
mkdir -p /tmp/vm-agent-update
curl -sL https://your-update-server.com/agent/agent.py -o /tmp/vm-agent-update/agent.py
curl -sL https://your-update-server.com/agent/requirements.txt -o /tmp/vm-agent-update/requirements.txt

# Verify download
if [ ! -s "/tmp/vm-agent-update/agent.py" ]; then
    echo "Error: Download failed."
    exit 1
fi

# 4. Install requirements
echo "Installing requirements..."
PIP_CMD="pip3"
if [ -f "/opt/vm-agent/venv/bin/pip" ]; then
    PIP_CMD="/opt/vm-agent/venv/bin/pip"
fi
$PIP_CMD install -r /tmp/vm-agent-update/requirements.txt

# 5. Move files
echo "Updating files..."
cp /tmp/vm-agent-update/agent.py /opt/vm-agent/agent.py
cp /tmp/vm-agent-update/requirements.txt /opt/vm-agent/requirements.txt

# 6. Restart Service
echo "Restarting service..."
systemctl restart vm-agent

echo "Done! Agent updated successfully."
