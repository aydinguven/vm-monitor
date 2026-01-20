#!/bin/bash
# install_dashboard.sh - Install VM Monitoring Dashboard (Simplified)
# Usage: ./install_dashboard.sh

set -e

INSTALL_DIR="/opt/vm-agent-dashboard"
DB_PATH="$INSTALL_DIR/instance/vm_metrics.db"
UPDATE_URL="https://your-update-server.com"

echo "🚀 Installing VM Dashboard..."

# 1. Install Dependencies
echo "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-pip tar
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip tar
fi

# 2. Create User and Group
echo "Creating vm-agent user..."
if ! getent group vm-agent >/dev/null; then
    sudo groupadd -r vm-agent
fi
if ! id "vm-agent" &>/dev/null; then
    sudo useradd -r -g vm-agent -d "$INSTALL_DIR" -s /sbin/nologin vm-agent
fi

# 3. Setup Directories
echo "Setting up installation directory..."
sudo mkdir -p "$INSTALL_DIR"
# Keep existing DB if it exists
if [ -f "$DB_PATH" ]; then
    echo "Backing up existing database..."
    sudo cp "$DB_PATH" "$DB_PATH.bak"
fi

# 4. Install Code
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Installing dashboard code..."
if [ -d "$SOURCE_ROOT/dashboard" ]; then
    sudo cp -r "$SOURCE_ROOT/dashboard/"* "$INSTALL_DIR/"
else
    echo "Source not found locally. Downloading from $UPDATE_URL..."
    sudo curl -sL "$UPDATE_URL/dashboard.tar" -o "$INSTALL_DIR/dashboard.tar"
    
    if [ ! -s "$INSTALL_DIR/dashboard.tar" ]; then
        echo "Error: Failed to download dashboard code."
        exit 1
    fi
    
    echo "  Extracting..."
    sudo tar -xf "$INSTALL_DIR/dashboard.tar" -C "$INSTALL_DIR"
    sudo rm "$INSTALL_DIR/dashboard.tar"
fi

# 5. Setup Python Venv
echo "Setting up virtual environment..."
cd "$INSTALL_DIR"
sudo python3 -m venv venv
sudo ./venv/bin/pip install --upgrade pip
sudo ./venv/bin/pip install -r requirements.txt
sudo ./venv/bin/pip install gunicorn

# 6. Database - Always recreate to ensure correct schema
# (Agents will repopulate data within 30 seconds)
echo "Setting up database..."
sudo mkdir -p instance
if [ -f "$DB_PATH" ]; then
    echo "  Removing old database (will be recreated with correct schema)..."
    sudo rm -f "$DB_PATH"
fi

sudo chown -R vm-agent:vm-agent "$INSTALL_DIR"
sudo chmod -R 755 "$INSTALL_DIR"

# 7. Setup Service
echo "Configuring systemd service..."
sudo bash -c "cat > /etc/systemd/system/vm-agent-dashboard.service" <<EOF
[Unit]
Description=VM Monitoring Dashboard
After=network.target

[Service]
Type=simple
User=vm-agent
Group=vm-agent
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vm-agent-dashboard
sudo systemctl restart vm-agent-dashboard

echo "✅ Dashboard installed and running on port 5000!"
echo "If using Cloudflare, point your tunnel or DNS to this IP:5000."
