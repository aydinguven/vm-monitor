#!/usr/bin/env python3
"""
Generate fake demo data for VM Monitor.
Creates a SQLite database with sample VMs in various states.
"""

import os
import sys
import random
from datetime import datetime, timedelta

# Add parent dashboard dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dashboard'))

from flask import Flask
from models import db, VM, Metric

# Demo VM configurations
DEMO_VMS = [
    {
        "hostname": "web-prod-01",
        "cloud_provider": "AWS",
        "os_name": "Ubuntu 24.04 LTS",
        "kernel": "6.5.0-44-generic",
        "arch": "x86_64",
        "cpu_count": 4,
        "ram_total_gb": 16.0,
        "cpu_range": (15, 35),  # Normal
        "ram_range": (40, 55),
        "containers": [
            {"name": "nginx", "image": "nginx:latest", "status": "Up 5 days", "ports": "80/tcp", "runtime": "docker"},
            {"name": "app", "image": "myapp:v2.1", "status": "Up 5 days", "ports": "3000/tcp", "runtime": "docker"},
        ],
    },
    {
        "hostname": "db-master",
        "cloud_provider": "Oracle Cloud",
        "os_name": "Oracle Linux 9.3",
        "kernel": "5.15.0-200.el9.x86_64",
        "arch": "x86_64",
        "cpu_count": 8,
        "ram_total_gb": 32.0,
        "cpu_range": (60, 75),  # Medium-high
        "ram_range": (75, 82),  # Warning level
        "containers": [],
    },
    {
        "hostname": "k8s-worker-1",
        "cloud_provider": "GCP",
        "os_name": "Rocky Linux 9.2",
        "kernel": "5.14.0-362.el9.x86_64",
        "arch": "x86_64",
        "cpu_count": 16,
        "ram_total_gb": 64.0,
        "cpu_range": (40, 60),
        "ram_range": (50, 65),
        "containers": [
            {"name": "kube-apiserver", "image": "k8s.gcr.io/kube-apiserver:v1.28", "status": "Up 12 days", "ports": "6443/tcp", "runtime": "containerd"},
        ],
        "pods": [
            {"namespace": "default", "name": "nginx-deployment-abc123", "status": "Running", "restarts": 0, "node": "k8s-worker-1"},
            {"namespace": "kube-system", "name": "coredns-5d4dd4b4", "status": "Running", "restarts": 1, "node": "k8s-worker-1"},
            {"namespace": "monitoring", "name": "prometheus-0", "status": "Running", "restarts": 0, "node": "k8s-worker-1"},
        ],
    },
    {
        "hostname": "backup-server",
        "cloud_provider": "Proxmox",
        "os_name": "Debian 12",
        "kernel": "6.1.0-18-amd64",
        "arch": "x86_64",
        "cpu_count": 2,
        "ram_total_gb": 8.0,
        "cpu_range": (5, 15),  # Low use
        "ram_range": (25, 35),
        "containers": [],
    },
    {
        "hostname": "monitor-critical",
        "cloud_provider": "VMware",
        "os_name": "CentOS 7.9",
        "kernel": "3.10.0-1160.el7.x86_64",
        "arch": "x86_64",
        "cpu_count": 4,
        "ram_total_gb": 8.0,
        "cpu_range": (88, 96),  # Critical!
        "ram_range": (91, 97),  # Critical!
        "containers": [],
    },
    {
        "hostname": "dev-box",
        "cloud_provider": "Hyper-V",
        "os_name": "Windows Server 2022",
        "kernel": "10.0.20348",
        "arch": "AMD64",
        "cpu_count": 8,
        "ram_total_gb": 32.0,
        "cpu_range": (20, 45),
        "ram_range": (55, 70),
        "containers": [
            {"name": "sql-server", "image": "mcr.microsoft.com/mssql/server:2022", "status": "Up 2 days", "ports": "1433/tcp", "runtime": "docker"},
        ],
    },
    {
        "hostname": "edge-node-asia",
        "cloud_provider": "Azure",
        "os_name": "Ubuntu 22.04 LTS",
        "kernel": "5.15.0-91-generic",
        "arch": "aarch64",
        "cpu_count": 2,
        "ram_total_gb": 4.0,
        "cpu_range": (30, 50),
        "ram_range": (60, 75),
        "containers": [],
    },
    {
        "hostname": "storage-nas",
        "cloud_provider": "Bare Metal",
        "os_name": "TrueNAS SCALE",
        "kernel": "6.1.42-truenas",
        "arch": "x86_64",
        "cpu_count": 4,
        "ram_total_gb": 16.0,
        "cpu_range": (10, 25),
        "ram_range": (35, 50),
        "containers": [],
    },
]


def generate_demo_db(db_path: str):
    """Generate a demo database with fake VMs."""
    
    # Create Flask app context
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Clear existing data
        VM.query.delete()
        Metric.query.delete()
        db.session.commit()
        
        now = datetime.utcnow()
        
        for vm_config in DEMO_VMS:
            cpu_low, cpu_high = vm_config.get("cpu_range", (20, 50))
            ram_low, ram_high = vm_config.get("ram_range", (30, 60))
            
            cpu_avg = random.uniform(cpu_low, cpu_high)
            cpu_instant = random.uniform(cpu_low, cpu_high)
            ram_percent = random.uniform(ram_low, ram_high)
            ram_used = vm_config["ram_total_gb"] * (ram_percent / 100)
            
            # Create VM
            vm = VM(
                hostname=vm_config["hostname"],
                cloud_provider=vm_config["cloud_provider"],
                os_name=vm_config["os_name"],
                kernel=vm_config["kernel"],
                arch=vm_config["arch"],
                cpu_count=vm_config["cpu_count"],
                ram_total_gb=vm_config["ram_total_gb"],
                cpu_avg=round(cpu_avg, 1),
                cpu_instant=round(cpu_instant, 1),
                ram_percent=round(ram_percent, 1),
                ram_used_gb=round(ram_used, 2),
                disk_usage={
                    "/": {"total_gb": 100, "used_gb": random.randint(20, 80), "percent": random.randint(20, 80)},
                    "/home": {"total_gb": 500, "used_gb": random.randint(50, 400), "percent": random.randint(10, 80)},
                },
                first_seen=now - timedelta(days=random.randint(5, 60)),
                last_seen=now - timedelta(seconds=random.randint(5, 120)),
                ip_internal=f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}",
                ip_external=f"203.0.113.{random.randint(1, 254)}",
                uptime_seconds=random.randint(86400, 86400 * 30),
                agent_version="1.49",
                latency_ms=vm_config.get("latency_ms", random.uniform(10, 80)),
                http_rtt_ms=vm_config.get("latency_ms", random.uniform(50, 250)) + random.uniform(20, 100),
                latency_updated_at=now,
                containers=vm_config.get("containers", []),
                pods=vm_config.get("pods", []),
                swap_percent=random.uniform(0, 20),
                network_bytes_sent=random.randint(100000000, 10000000000),
                network_bytes_recv=random.randint(100000000, 10000000000),
                pending_updates=random.choice([0, 0, 0, 2, 5, 12]),
                open_ports=[
                    {"port": 22, "process": "sshd"},
                    {"port": 80, "process": "nginx"},
                ] if "web" in vm_config["hostname"] else [{"port": 22, "process": "sshd"}],
                ssh_failed_attempts=random.choice([0, 0, 3, 15, 47]),
                top_processes=[
                    {"name": "python", "pid": 1234, "cpu": random.uniform(1, 15), "ram": random.uniform(1, 10)},
                    {"name": "nginx", "pid": 5678, "cpu": random.uniform(0.5, 5), "ram": random.uniform(0.5, 3)},
                    {"name": "node", "pid": 9012, "cpu": random.uniform(0.5, 8), "ram": random.uniform(1, 5)},
                ],
            )
            db.session.add(vm)
            db.session.flush()  # Get the ID
            
            # Generate historical metrics (last 24 hours)
            for hours_ago in range(24, 0, -1):
                for minutes in [0, 15, 30, 45]:
                    timestamp = now - timedelta(hours=hours_ago, minutes=minutes)
                    metric = Metric(
                        vm_id=vm.id,
                        timestamp=timestamp,
                        cpu_avg=round(random.uniform(cpu_low * 0.8, cpu_high * 1.1), 1),
                        cpu_instant=round(random.uniform(cpu_low * 0.8, cpu_high * 1.2), 1),
                        ram_percent=round(random.uniform(ram_low * 0.9, ram_high * 1.05), 1),
                        disk_usage=vm.disk_usage,
                    )
                    db.session.add(metric)
            
            print(f"  ✓ Created VM: {vm_config['hostname']} ({vm_config['cloud_provider']})")
        
        db.session.commit()
        print(f"\n✅ Generated {len(DEMO_VMS)} demo VMs with 24h of historical data")


if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(__file__), "demo_db.sqlite")
    print("🔧 Generating demo database...")
    generate_demo_db(db_path)
    print(f"📁 Database saved to: {db_path}")
