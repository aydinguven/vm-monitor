"""
VM Dashboard - Database Models
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class VM(db.Model):
    """Virtual Machine record."""
    __tablename__ = "vms"
    
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), unique=True, nullable=False, index=True)
    cloud_provider = db.Column(db.String(50), default="unknown")
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)  # v1.30.1 - Added index
    
    # Latest metrics (denormalized for quick dashboard access)
    cpu_avg = db.Column(db.Float, default=0)
    cpu_instant = db.Column(db.Float, default=0)
    cpu_count = db.Column(db.Integer, default=1)
    ram_total_gb = db.Column(db.Float, default=0)
    ram_used_gb = db.Column(db.Float, default=0)
    ram_percent = db.Column(db.Float, default=0)
    disk_usage = db.Column(db.JSON, default=dict)
    
    # OS Info
    os_name = db.Column(db.String(100))       # "Ubuntu 24.04.1 LTS"
    kernel = db.Column(db.String(100))        # "6.5.0-44-generic"
    arch = db.Column(db.String(20))           # "x86_64"
    
    # Network
    ip_internal = db.Column(db.String(45))    # IPv4 or IPv6
    ip_external = db.Column(db.String(45))
    
    # Runtime
    uptime_seconds = db.Column(db.Integer)
    agent_version = db.Column(db.String(20))  # e.g. "1.1"
    
    # Containers & Pods (JSON arrays)
    containers = db.Column(db.JSON)           # [{"name": "nginx", "image": "...", "status": "..."}]
    pods = db.Column(db.JSON)                 # [{"namespace": "...", "name": "...", "status": "..."}]
    
    # v1.20 - New metrics
    swap_percent = db.Column(db.Float, default=0)
    network_bytes_sent = db.Column(db.BigInteger, default=0)
    network_bytes_recv = db.Column(db.BigInteger, default=0)
    pending_updates = db.Column(db.Integer, default=0)
    
    # v1.20 - Security
    open_ports = db.Column(db.JSON)           # [{"port": 22, "process": "sshd"}]
    ssh_failed_attempts = db.Column(db.Integer, default=0)
    
    # v1.20 - Processes
    top_processes = db.Column(db.JSON)        # [{"name": "python", "cpu": 15.2, "ram": 8.5}]
    
    # v1.48 - Latency (dashboard-side ping)
    latency_ms = db.Column(db.Float)          # Ping latency in milliseconds (None = not measured)
    latency_updated_at = db.Column(db.DateTime)  # When latency was last updated
    
    # Relationship to metrics history
    metrics = db.relationship("Metric", backref="vm", lazy="dynamic", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        now = datetime.utcnow()
        last_seen = self.last_seen or now # Fallback to now to avoid crash
        seconds_ago = int((now - last_seen).total_seconds())
        
        return {
            "id": self.id,
            "hostname": self.hostname,
            "cloud_provider": self.cloud_provider,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": last_seen.isoformat(),
            "cpu_avg": self.cpu_avg or 0,
            "cpu_instant": self.cpu_instant or 0,
            "cpu_count": self.cpu_count or 1,
            "ram_total_gb": self.ram_total_gb or 0,
            "ram_used_gb": self.ram_used_gb or 0,
            "ram_percent": self.ram_percent or 0,
            "disk_usage": self.disk_usage or {},
            # Computed status (offline if no data for 5 minutes)
            "online": seconds_ago < 300,
            "seconds_ago": seconds_ago,
            # OS & Network
            "os_name": self.os_name,
            "kernel": self.kernel,
            "arch": self.arch,
            "ip_internal": self.ip_internal,
            "ip_external": self.ip_external,
            "uptime_seconds": self.uptime_seconds,
            "agent_version": self.agent_version,
            "containers": self.containers or [],
            "pods": self.pods or [],
            # v1.20 - New metrics
            "swap_percent": self.swap_percent or 0,
            "network_bytes_sent": self.network_bytes_sent or 0,
            "network_bytes_recv": self.network_bytes_recv or 0,
            "pending_updates": self.pending_updates or 0,
            "open_ports": self.open_ports or [],
            "ssh_failed_attempts": self.ssh_failed_attempts or 0,
            "top_processes": self.top_processes or [],
            # v1.48 - Latency
            "latency_ms": self.latency_ms,
            "latency_updated_at": self.latency_updated_at.isoformat() if self.latency_updated_at else None
        }
    
    def to_list_dict(self):
        """Lightweight dict for list view - excludes heavy JSON fields."""
        now = datetime.utcnow()
        last_seen = self.last_seen or now
        seconds_ago = int((now - last_seen).total_seconds())
        
        return {
            "hostname": self.hostname,
            "cloud_provider": self.cloud_provider,
            "last_seen": last_seen.isoformat(),
            "cpu_avg": self.cpu_avg or 0,
            "cpu_instant": self.cpu_instant or 0,
            "cpu_count": self.cpu_count or 1,
            "ram_total_gb": self.ram_total_gb or 0,
            "ram_used_gb": self.ram_used_gb or 0,
            "ram_percent": self.ram_percent or 0,
            "disk_usage": self.disk_usage or {},
            "online": seconds_ago < 300,
            "seconds_ago": seconds_ago,
            "os_name": self.os_name,
            "agent_version": self.agent_version,
            "pending_updates": self.pending_updates or 0,
            # v1.48 - Latency
            "latency_ms": self.latency_ms,
        }


class Metric(db.Model):
    """Historical metric data point."""
    __tablename__ = "metrics"
    
    id = db.Column(db.Integer, primary_key=True)
    vm_id = db.Column(db.Integer, db.ForeignKey("vms.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    cpu_avg = db.Column(db.Float)
    cpu_instant = db.Column(db.Float)
    ram_percent = db.Column(db.Float)
    disk_usage = db.Column(db.JSON)
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "cpu_avg": self.cpu_avg,
            "cpu_instant": self.cpu_instant,
            "ram_percent": self.ram_percent,
            "disk_usage": self.disk_usage or {}
        }


class Command(db.Model):
    """Queued commands for execution on agents."""
    __tablename__ = "commands"

    id = db.Column(db.Integer, primary_key=True)
    vm_id = db.Column(db.Integer, db.ForeignKey("vms.id"), nullable=False, index=True)
    command = db.Column(db.String(50))
    args = db.Column(db.String(255))
    status = db.Column(db.String(20), default="pending")  # pending, running, completed, failed
    output = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "command": self.command,
            "args": self.args,
            "status": self.status,
            "output": self.output,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }

