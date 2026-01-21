#!/bin/bash
# Run VM Monitor Demo
# This creates a demo database and launches the dashboard with demo mode

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 VM Monitor Demo"
echo "=================="

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Create venv if needed
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate venv
source "$SCRIPT_DIR/venv/bin/activate"

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q flask flask-sqlalchemy flask-migrate gunicorn apscheduler requests pytz

# Generate demo data if needed
if [ ! -f "$SCRIPT_DIR/demo_db.sqlite" ]; then
    echo "🔧 Generating demo data..."
    python "$SCRIPT_DIR/generate_demo_data.py"
fi

# Copy config files to instance dir
mkdir -p "$PROJECT_ROOT/dashboard/instance"
cp "$SCRIPT_DIR/config.json" "$PROJECT_ROOT/dashboard/instance/"
cp "$SCRIPT_DIR/features.json" "$PROJECT_ROOT/dashboard/instance/"
cp "$SCRIPT_DIR/sms_config.json" "$PROJECT_ROOT/dashboard/instance/"

# Copy demo database with absolute path config
cp "$SCRIPT_DIR/demo_db.sqlite" "$PROJECT_ROOT/dashboard/instance/"

# Update database URL to absolute path
cat > "$PROJECT_ROOT/dashboard/instance/config.json" <<EOF
{
  "secret_key": "demo-secret-key-not-for-production",
  "api_key": "demo-api-key",
  "database_url": "sqlite:///$PROJECT_ROOT/dashboard/instance/demo_db.sqlite",
  "timezone": "UTC"
}
EOF

echo ""
echo "✅ Demo ready!"
echo ""

# Kill any existing demo processes
pkill -f "gunicorn.*demo_app" 2>/dev/null || true
pkill -f "simulate_data.py" 2>/dev/null || true
sleep 1

# Start data simulator in background
echo "🔄 Starting data simulator..."
python "$SCRIPT_DIR/simulate_data.py" > "$SCRIPT_DIR/simulator.log" 2>&1 &
SIMULATOR_PID=$!
echo $SIMULATOR_PID > "$SCRIPT_DIR/simulator.pid"

# Run demo app with gunicorn in background
echo "🌐 Starting demo dashboard..."
cd "$SCRIPT_DIR"
gunicorn -w 2 -b 0.0.0.0:5000 demo_app:app \
    --daemon \
    --pid "$SCRIPT_DIR/demo.pid" \
    --access-logfile "$SCRIPT_DIR/access.log" \
    --error-logfile "$SCRIPT_DIR/error.log"

sleep 2  # Wait for gunicorn to start

if [ -f "$SCRIPT_DIR/demo.pid" ]; then
    echo ""
    echo "📌 Dashboard running at: http://localhost:5000"
    echo ""
    echo "   Dashboard PID: $(cat $SCRIPT_DIR/demo.pid)"
    echo "   Simulator PID: $SIMULATOR_PID"
    echo ""
    echo "   Logs:"
    echo "     - $SCRIPT_DIR/access.log"
    echo "     - $SCRIPT_DIR/error.log"
    echo "     - $SCRIPT_DIR/simulator.log"
    echo ""
    echo "   To stop: $SCRIPT_DIR/stop_demo.sh"
else
    echo "❌ Failed to start. Check $SCRIPT_DIR/error.log"
fi
