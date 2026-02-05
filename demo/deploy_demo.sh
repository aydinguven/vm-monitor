#!/bin/bash
# Deploy VM Monitor Demo to production directory
# Usage: ./deploy_demo.sh [target_dir]
# Default: /opt/demo/vm-monitor-dashboard-demo

set -e

# Configuration
TARGET_DIR="${1:-/opt/demo/vm-monitor-dashboard-demo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 VM Monitor Demo Deployment"
echo "=============================="
echo "Source: $PROJECT_ROOT"
echo "Target: $TARGET_DIR"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Create target directory
echo "📁 Creating directory structure..."
sudo mkdir -p "$TARGET_DIR"
sudo chown $(whoami):$(whoami) "$TARGET_DIR"

# Copy dashboard files
echo "📋 Copying dashboard files..."
cp -r "$PROJECT_ROOT/dashboard" "$TARGET_DIR/"

# Copy demo files
echo "📋 Copying demo files..."
cp -r "$PROJECT_ROOT/demo" "$TARGET_DIR/"

# Create instance directory
mkdir -p "$TARGET_DIR/dashboard/instance"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv "$TARGET_DIR/venv"
source "$TARGET_DIR/venv/bin/activate"

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q flask flask-sqlalchemy flask-migrate gunicorn apscheduler requests pytz

# Generate demo data
echo "🔧 Generating demo data..."
cd "$TARGET_DIR/demo"
python generate_demo_data.py

# Copy config files to instance directory
cp "$TARGET_DIR/demo/config.json" "$TARGET_DIR/dashboard/instance/"
cp "$TARGET_DIR/demo/features.json" "$TARGET_DIR/dashboard/instance/"
cp "$TARGET_DIR/demo/sms_config.json" "$TARGET_DIR/dashboard/instance/"
cp "$TARGET_DIR/demo/demo_db.sqlite" "$TARGET_DIR/dashboard/instance/"

# Update config with absolute path
cat > "$TARGET_DIR/dashboard/instance/config.json" <<EOF
{
  "secret_key": "demo-secret-key-not-for-production",
  "api_key": "demo-api-key",
  "database_url": "sqlite:///$TARGET_DIR/dashboard/instance/demo_db.sqlite",
  "timezone": "UTC",
  "demo_mode": true,
  "metric_retention_hours": 168
}
EOF

# Create systemd service
echo "📝 Creating systemd service..."
sudo tee /etc/systemd/system/vm-monitor-demo.service > /dev/null <<EOF
[Unit]
Description=VM Monitor Demo Dashboard
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$TARGET_DIR/demo
Environment="PATH=$TARGET_DIR/venv/bin"
ExecStart=$TARGET_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:5011 demo_app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create data simulator service
sudo tee /etc/systemd/system/vm-monitor-demo-simulator.service > /dev/null <<EOF
[Unit]
Description=VM Monitor Demo Data Simulator
After=network.target vm-monitor-demo.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$TARGET_DIR/demo
Environment="PATH=$TARGET_DIR/venv/bin"
ExecStart=$TARGET_DIR/venv/bin/python $TARGET_DIR/demo/simulate_data.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload and start services
echo "🔄 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable vm-monitor-demo vm-monitor-demo-simulator
sudo systemctl restart vm-monitor-demo vm-monitor-demo-simulator

sleep 2

# Check status
if systemctl is-active --quiet vm-monitor-demo; then
    echo ""
    echo "✅ Demo deployed successfully!"
    echo ""
    echo "   📍 Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
    echo "   📁 Location:  $TARGET_DIR"
    echo ""
    echo "   Service commands:"
    echo "     sudo systemctl status vm-monitor-demo"
    echo "     sudo systemctl stop vm-monitor-demo vm-monitor-demo-simulator"
    echo "     sudo systemctl start vm-monitor-demo vm-monitor-demo-simulator"
    echo "     sudo journalctl -u vm-monitor-demo -f"
else
    echo ""
    echo "❌ Failed to start. Check logs:"
    echo "   sudo journalctl -u vm-monitor-demo -n 50"
fi
