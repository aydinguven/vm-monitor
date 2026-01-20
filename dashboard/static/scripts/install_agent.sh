#!/bin/bash
# install_agent.sh - Install VM Monitoring Agent
# Usage: ./install_agent.sh --server http://DASHBOARD_IP:5000 --key YOUR_API_KEY [--interval 30]

set -e

# Defaults
SERVER_URL=""
API_KEY=""
INTERVAL=30
INSTALL_DIR="/opt/vm-agent"
UPDATE_URL="https://your-update-server.com"

# Parse Args
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --server) SERVER_URL="$2"; shift ;;
        --key) API_KEY="$2"; shift ;;
        --interval) INTERVAL="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$SERVER_URL" ] || [ -z "$API_KEY" ]; then
    echo "Usage: $0 --server <URL> --key <KEY> [--interval <SECONDS>]"
    exit 1
fi

echo "🚀 Installing VM Agent..."

# 1. Install Dependencies
echo "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-pip
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip
fi

# 2. Setup Directories
echo "Setting up installation directory..."
sudo mkdir -p "$INSTALL_DIR"
sudo mkdir -p /etc/vm-agent/kubeconfigs

# 3. Discover and copy kubeconfigs
echo "Discovering kubeconfigs..."
# System-wide configs
for cfg in /etc/kubernetes/admin.conf /etc/rancher/k3s/k3s.yaml; do
    if [ -f "$cfg" ]; then
        name=$(basename "$cfg")
        sudo cp "$cfg" "/etc/vm-agent/kubeconfigs/$name"
        echo "  Found: $cfg"
    fi
done
# User configs
for user_home in /home/*; do
    if [ -d "$user_home/.kube" ] && [ -f "$user_home/.kube/config" ]; then
        user=$(basename "$user_home")
        sudo cp "$user_home/.kube/config" "/etc/vm-agent/kubeconfigs/${user}.kubeconfig"
        echo "  Found: $user_home/.kube/config"
    fi
done
sudo chmod 600 /etc/vm-agent/kubeconfigs/* 2>/dev/null || true

# 4. Copy Code (Assumes script is run from installer root)
# If run via curl, we need to download. If local, copy.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Installing agent code..."
if [ -d "$SOURCE_ROOT/agent" ]; then
    sudo cp -r "$SOURCE_ROOT/agent/"* "$INSTALL_DIR/"
else
    echo "Source not found locally. Downloading from $UPDATE_URL..."
    # Create temp dir for download to handle RO /opt issues cleanly (though we are installing so we expect write access)
    sudo mkdir -p "$INSTALL_DIR"
    
    echo "  Downloading agent.py..."
    sudo curl -sL "$UPDATE_URL/agent/agent.py" -o "$INSTALL_DIR/agent.py"
    
    echo "  Downloading requirements.txt..."
    sudo curl -sL "$UPDATE_URL/agent/requirements.txt" -o "$INSTALL_DIR/requirements.txt"
    
    if [ ! -s "$INSTALL_DIR/agent.py" ]; then
        echo "Error: Failed to download agent code."
        exit 1
    fi
fi

# 5. Setup Python Venv
echo "Setting up virtual environment..."
cd "$INSTALL_DIR"

# Try venv first, fall back to direct pip if venv fails
if sudo python3 -m venv venv 2>/dev/null; then
    echo "  Using virtual environment..."
    PYTHON="$INSTALL_DIR/venv/bin/python"
    PIP="$INSTALL_DIR/venv/bin/pip"
    sudo "$PIP" install --upgrade pip 2>/dev/null || true
else
    echo "  Warning: venv creation failed, using system Python..."
    PYTHON="python3"
    PIP="pip3"
    # Install to user site-packages or /opt
    sudo pip3 install --upgrade pip 2>/dev/null || true
fi

# Install requirements
echo "Installing Python dependencies..."
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    sudo "$PIP" install -r "$INSTALL_DIR/requirements.txt" --break-system-packages 2>/dev/null || \
    sudo "$PIP" install -r "$INSTALL_DIR/requirements.txt" 2>/dev/null || \
    sudo pip3 install psutil requests distro packaging --break-system-packages 2>/dev/null || \
    sudo pip3 install psutil requests distro packaging
else
    # Fallback: install known dependencies directly
    sudo "$PIP" install psutil requests distro packaging --break-system-packages 2>/dev/null || \
    sudo "$PIP" install psutil requests distro packaging 2>/dev/null || \
    sudo pip3 install psutil requests distro packaging --break-system-packages 2>/dev/null || \
    sudo pip3 install psutil requests distro packaging
fi


# 5. Configure
echo "Generating configuration..."
sudo bash -c "cat > /etc/vm-agent.conf" <<EOF
VM_AGENT_SERVER=$SERVER_URL
VM_AGENT_KEY=$API_KEY
VM_AGENT_INTERVAL=$INTERVAL
VM_AGENT_UPDATE_URL=$UPDATE_URL
EOF
sudo chmod 600 /etc/vm-agent.conf

# 6. Setup Service (runs as root for full container/k8s access)
echo "Configuring systemd service..."

# Determine which Python to use in service
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
EnvironmentFile=/etc/vm-agent.conf

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vm-agent
sudo systemctl restart vm-agent

echo "✅ Agent installed and started!"
