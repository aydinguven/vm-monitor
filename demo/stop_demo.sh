#!/bin/bash
# Stop VM Monitor Demo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🛑 Stopping VM Monitor Demo..."

# Stop gunicorn
if [ -f "$SCRIPT_DIR/demo.pid" ]; then
    kill $(cat "$SCRIPT_DIR/demo.pid") 2>/dev/null && echo "   ✓ Dashboard stopped"
    rm -f "$SCRIPT_DIR/demo.pid"
else
    pkill -f "gunicorn.*demo_app" 2>/dev/null && echo "   ✓ Dashboard stopped"
fi

# Stop simulator
if [ -f "$SCRIPT_DIR/simulator.pid" ]; then
    kill $(cat "$SCRIPT_DIR/simulator.pid") 2>/dev/null && echo "   ✓ Simulator stopped"
    rm -f "$SCRIPT_DIR/simulator.pid"
else
    pkill -f "simulate_data.py" 2>/dev/null && echo "   ✓ Simulator stopped"
fi

echo ""
echo "✅ Demo stopped"
