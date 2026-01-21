#!/bin/bash
# Run VM Monitor Demo
# This creates a demo database and launches the dashboard

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

# Generate demo data
echo "🔧 Generating demo data..."
python "$SCRIPT_DIR/generate_demo_data.py"

# Copy config files to instance dir
mkdir -p "$PROJECT_ROOT/dashboard/instance"
cp "$SCRIPT_DIR/config.json" "$PROJECT_ROOT/dashboard/instance/"
cp "$SCRIPT_DIR/features.json" "$PROJECT_ROOT/dashboard/instance/"
cp "$SCRIPT_DIR/sms_config.json" "$PROJECT_ROOT/dashboard/instance/"

# Copy demo database
cp "$SCRIPT_DIR/demo_db.sqlite" "$PROJECT_ROOT/dashboard/instance/"

# Update database URL in config to point to instance dir
cat > "$PROJECT_ROOT/dashboard/instance/config.json" <<EOF
{
  "secret_key": "demo-secret-key-not-for-production",
  "api_key": "demo-api-key",
  "database_url": "sqlite:///instance/demo_db.sqlite",
  "timezone": "UTC"
}
EOF

echo ""
echo "✅ Demo ready!"
echo ""
echo "📌 Starting dashboard at: http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

# Run dashboard
cd "$PROJECT_ROOT/dashboard"
python app.py
