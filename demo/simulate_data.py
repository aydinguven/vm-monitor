#!/usr/bin/env python3
"""
Demo Data Simulator for VM Monitor.
Runs in the background and updates VM last_seen timestamps to keep them "online".
Also varies CPU/RAM values slightly to simulate real activity.
"""

import os
import sys
import time
import random
import signal
from datetime import datetime

# Add parent dashboard dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dashboard'))

from flask import Flask
from models import db, VM, Metric

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, '..', 'dashboard', 'instance', 'demo_db.sqlite')

running = True

def signal_handler(sig, frame):
    global running
    print("\n🛑 Stopping simulator...")
    running = False

def simulate_metrics():
    """Update VM metrics to simulate real activity."""
    
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    print(f"🔄 Demo Simulator started")
    print(f"   Database: {DB_PATH}")
    print(f"   Updating every 30 seconds...")
    print(f"   Press Ctrl+C to stop\n")
    
    while running:
        with app.app_context():
            vms = VM.query.all()
            now = datetime.utcnow()
            
            for vm in vms:
                # Update last_seen to keep VM "online"
                vm.last_seen = now
                
                # Vary CPU slightly (+/- 5%)
                variation = random.uniform(-5, 5)
                vm.cpu_avg = max(0, min(100, (vm.cpu_avg or 30) + variation))
                vm.cpu_instant = max(0, min(100, (vm.cpu_instant or 30) + variation * 1.5))
                
                # Vary RAM slightly (+/- 2%)
                ram_variation = random.uniform(-2, 2)
                vm.ram_percent = max(0, min(100, (vm.ram_percent or 50) + ram_variation))
                vm.ram_used_gb = vm.ram_total_gb * (vm.ram_percent / 100) if vm.ram_total_gb else 0
                
                # Add new metric point
                metric = Metric(
                    vm_id=vm.id,
                    timestamp=now,
                    cpu_avg=vm.cpu_avg,
                    cpu_instant=vm.cpu_instant,
                    ram_percent=vm.ram_percent,
                    disk_usage=vm.disk_usage
                )
                db.session.add(metric)
            
            db.session.commit()
            print(f"✓ Updated {len(vms)} VMs at {now.strftime('%H:%M:%S')}")
        
        # Sleep in small increments to allow clean shutdown
        for _ in range(30):
            if not running:
                break
            time.sleep(1)
    
    print("👋 Simulator stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("   Run generate_demo_data.py first")
        sys.exit(1)
    
    simulate_metrics()
