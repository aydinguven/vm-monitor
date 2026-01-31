"""
VM Dashboard - Flask Application
"""

import atexit
import csv
import io
import logging
import os
from datetime import datetime, timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request, g, redirect, url_for, flash
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import (
    API_KEY,
    CLEANUP_INTERVAL_MINUTES,
    METRIC_RETENTION_HOURS,
    SECRET_KEY,
    SQLALCHEMY_DATABASE_URI,
    VM_OFFLINE_THRESHOLD,
    SMS_RECIPIENT,
    SMS_DASHBOARD_URL,
    ALERT_WARNING_THRESHOLD,
    ALERT_CRITICAL_THRESHOLD,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    PERMANENT_SESSION_LIFETIME,
    REMEMBER_COOKIE_DURATION,
)
from models import Command, Metric, VM, User, db
from sms_providers import send_sms, send_notification
from general_config import get_general_config

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True # Force reload templates

# Session security settings
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE
app.config["SESSION_COOKIE_HTTPONLY"] = SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
app.config["PERMANENT_SESSION_LIFETIME"] = PERMANENT_SESSION_LIFETIME
app.config["REMEMBER_COOKIE_DURATION"] = REMEMBER_COOKIE_DURATION

db.init_app(app)
migrate = Migrate(app, db)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'


# --------------------------
# Access Logging Setup
# --------------------------

# Cross-platform log directory (same as instance folder)
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
os.makedirs(LOG_DIR, exist_ok=True)
ACCESS_LOG_FILE = os.path.join(LOG_DIR, "access.log")

# Configure access logger
access_logger = logging.getLogger("access")
access_logger.setLevel(logging.INFO)
access_handler = RotatingFileHandler(ACCESS_LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
access_handler.setFormatter(logging.Formatter("%(message)s"))
access_logger.addHandler(access_handler)

@app.before_request
def log_request_start():
    """Record request start time."""
    g.start_time = datetime.now()

@app.after_request
def log_access(response):
    """Log each request after it completes."""
    # Skip static files and API endpoints to reduce noise
    if not request.path.startswith('/static') and not request.path.startswith('/api/push'):
        duration = (datetime.now() - g.start_time).total_seconds() * 1000 if hasattr(g, 'start_time') else 0
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '-')[:100]  # Truncate long UAs
        
        log_line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {client_ip} | {request.method} {request.path} | {response.status_code} | {duration:.0f}ms | {user_agent}"
        access_logger.info(log_line)
    return response


# --------------------------
# Flask-Login User Loader
# --------------------------

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))


# --------------------------
# Authentication Decorators
# --------------------------

def require_api_key(f):
    """Decorator to require API key for agent endpoints (strict API key only)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from config import FEATURE_AUTH_ENABLED
        
        # If auth is disabled globally, allow access
        if not FEATURE_AUTH_ENABLED:
            return f(*args, **kwargs)
        
        key = request.headers.get("X-API-Key")
        if key != API_KEY:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated


def require_auth(f):
    """Decorator to require either session auth OR API key (for management endpoints)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from config import FEATURE_AUTH_ENABLED
        
        # If auth is disabled globally, allow all access
        if not FEATURE_AUTH_ENABLED:
            return f(*args, **kwargs)
        
        # Check if user is logged in via session (Flask-Login)
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        
        # Otherwise, check for API key
        key = request.headers.get("X-API-Key")
        if key == API_KEY:
            return f(*args, **kwargs)
        
        # Neither session nor API key valid
        return jsonify({"error": "Authentication required. Please login or provide API key."}), 401
    return decorated


# --------------------------
# Cleanup Scheduler
# --------------------------

def cleanup_old_metrics():
    """Remove metrics older than retention period."""
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(hours=METRIC_RETENTION_HOURS)
        deleted = Metric.query.filter(Metric.timestamp < cutoff).delete()
        db.session.commit()
        if deleted:
            app.logger.info(f"Cleaned up {deleted} old metric records")


def cleanup_stale_vms():
    """Remove VMs that haven't reported in 180 days."""
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=180)
        stale_vms = VM.query.filter(VM.last_seen < cutoff).all()
        for vm in stale_vms:
            app.logger.info(f"Removing stale VM: {vm.hostname} (last seen: {vm.last_seen})")
            db.session.delete(vm)
        if stale_vms:
            db.session.commit()
            app.logger.info(f"Cleaned up {len(stale_vms)} stale VMs")


def send_sms_alert():
    """Send SMS alert summarizing current alerts and warnings."""
    # Check feature flag (hot-reload)
    from config import is_feature_enabled, get_sms_recipient, get_sms_dashboard_url
    
    if not is_feature_enabled("sms", True):
        return  # SMS feature disabled
    
    recipient = get_sms_recipient()
    dashboard_url = get_sms_dashboard_url()
    
    if not recipient:
        return  # SMS not configured
    
    with app.app_context():
        vms = VM.query.all()
        
        alert_types = set()  # CPU, RAM, Disk with ≥90%
        warning_types = set()  # CPU, RAM, Disk with ≥80% but <90%
        alert_count = 0
        warning_count = 0
        
        for vm in vms:
            # Check CPU
            if vm.cpu_avg >= ALERT_CRITICAL_THRESHOLD:
                alert_types.add("CPU")
                alert_count += 1
            elif vm.cpu_avg >= ALERT_WARNING_THRESHOLD:
                warning_types.add("CPU")
                warning_count += 1
            
            # Check RAM
            if vm.ram_percent >= ALERT_CRITICAL_THRESHOLD:
                alert_types.add("RAM")
                alert_count += 1
            elif vm.ram_percent >= ALERT_WARNING_THRESHOLD:
                warning_types.add("RAM")
                warning_count += 1
            
            # Check Disk (any partition)
            if vm.disk_usage:
                max_disk = max((d.get("percent", 0) for d in vm.disk_usage.values()), default=0)
                if max_disk >= ALERT_CRITICAL_THRESHOLD:
                    alert_types.add("Disk")
                    alert_count += 1
                elif max_disk >= ALERT_WARNING_THRESHOLD:
                    warning_types.add("Disk")
                    warning_count += 1
        
        # Only send if there are alerts or warnings
        if alert_count == 0 and warning_count == 0:
            app.logger.info("SMS Alert: No alerts or warnings, skipping SMS")
            return
        
        # Build message
        parts = []
        if alert_count > 0:
            parts.append(f"{alert_count} alerts ({', '.join(sorted(alert_types))})")
        if warning_count > 0:
            parts.append(f"{warning_count} warnings ({', '.join(sorted(warning_types))})")
        
        message = f"You have {', '.join(parts)}. {dashboard_url}"
        
        app.logger.info(f"Sending notification alert: {message}")
        result = send_notification(message, recipient)
        if result.get("success"):
            app.logger.info(f"Notification sent: {result.get('sent')}/{result.get('sent') + result.get('failed', 0)} providers succeeded")
        else:
            app.logger.error(f"Notification failed: {result}")


# Load timezone from config (default to Turkey if not set)
timezone = get_general_config("timezone", "Europe/Istanbul")
scheduler = BackgroundScheduler(timezone=timezone)
scheduler.add_job(
    func=cleanup_old_metrics,
    trigger="interval",
    minutes=CLEANUP_INTERVAL_MINUTES,
    id="cleanup_metrics"
)
scheduler.add_job(
    func=cleanup_stale_vms,
    trigger="interval",
    hours=24,  # Run once daily
    id="cleanup_stale_vms"
)

# SMS Alert schedule - read times from sms_config.json (v1.46)
from sms_config import get_sms_schedule_times
sms_times = get_sms_schedule_times()
for hour, minute in sms_times:
    scheduler.add_job(
        func=send_sms_alert,
        trigger="cron",
        hour=hour,
        minute=minute,
        id=f"sms_alert_{hour:02d}{minute:02d}"
    )

scheduler.start()
atexit.register(lambda: scheduler.shutdown())


# --------------------------
# API Endpoints
# --------------------------

@app.route("/api/send-sms", methods=["POST"])
@require_auth
def trigger_sms():
    """Manually trigger SMS alert."""
    from config import get_sms_recipient
    
    recipient = get_sms_recipient()
    if not recipient:
        return jsonify({"success": False, "error": "SMS not configured. Edit instance/sms_config.json"}), 400
    
    # Call the same function used by scheduler
    send_sms_alert()
    return jsonify({"success": True, "message": f"SMS sent to {recipient}"})


@app.route("/api/send-telegram", methods=["POST"])
@require_auth
def trigger_telegram():
    """Manually trigger Telegram test notification."""
    from sms_config import get_sms_config
    
    provider = get_sms_config("provider", "")
    providers = get_sms_config("providers", [])
    
    # Check if telegram is enabled (single provider mode or multi-provider mode)
    telegram_enabled = provider == "telegram" or "telegram" in [p.lower() for p in providers if isinstance(p, str)]
    relay_enabled = provider == "relay" or "relay" in [p.lower() for p in providers if isinstance(p, str)]
    
    if telegram_enabled:
        bot_token = get_sms_config("telegram.bot_token", "")
        
        # Support both chat_id (string or array) and chat_ids (array)
        chat_ids = get_sms_config("telegram.chat_ids", [])
        single_id = get_sms_config("telegram.chat_id", "")
        
        # Handle chat_id being a list or string
        if isinstance(single_id, list):
            chat_ids = single_id
        elif single_id and not chat_ids:
            chat_ids = [single_id]
        
        if not bot_token or not chat_ids:
            return jsonify({"success": False, "error": "Telegram not configured. Edit instance/sms_config.json"}), 400
        
        # Build summary message
        vms = VM.query.all()
        online_count = sum(1 for vm in vms if (datetime.utcnow() - vm.last_seen).total_seconds() < VM_OFFLINE_THRESHOLD)
        offline_count = len(vms) - online_count
        
        alert_count = 0
        warning_count = 0
        for vm in vms:
            if vm.cpu_avg >= 90 or vm.ram_percent >= 90:
                alert_count += 1
            elif vm.cpu_avg >= 80 or vm.ram_percent >= 80:
                warning_count += 1
            if vm.disk_usage:
                max_disk = max((d.get("percent", 0) for d in vm.disk_usage.values()), default=0)
                if max_disk >= 90:
                    alert_count += 1
                elif max_disk >= 80:
                    warning_count += 1
        
        # Format message
        status_emoji = "🟢" if alert_count == 0 and warning_count == 0 else ("🔴" if alert_count > 0 else "🟡")
        lines = [
            f"{status_emoji} *VM Monitor Summary*",
            f"📊 {online_count} online, {offline_count} offline"
        ]
        if alert_count > 0:
            lines.append(f"🚨 {alert_count} critical alerts")
        if warning_count > 0:
            lines.append(f"⚠️ {warning_count} warnings")
        if alert_count == 0 and warning_count == 0:
            lines.append("✅ All systems healthy")
        
        message = "\n".join(lines)
        
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        success_count = 0
        last_error = None
        
        for chat_id in chat_ids:
            try:
                response = requests.post(url, json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }, timeout=30)
                result = response.json()
                if result.get("ok"):
                    success_count += 1
                else:
                    last_error = result.get("description", "Unknown error")
            except Exception as e:
                last_error = str(e)
        
        if success_count > 0:
            return jsonify({"success": True, "message": f"Sent to {success_count}/{len(chat_ids)} recipients"})
        else:
            return jsonify({"success": False, "error": last_error or "Failed to send"}), 400
    
    elif relay_enabled:
        relay_url = get_sms_config("relay.url", "")
        relay_api_key = get_sms_config("relay.api_key", "")
        if not relay_url or not relay_api_key:
            return jsonify({"success": False, "error": "Relay not configured. Edit instance/sms_config.json"}), 400
        
        # Send via relay service
        import requests
        chat_ids = get_sms_config("relay.chat_ids", [])
        if not chat_ids:
            return jsonify({"success": False, "error": "No chat_ids configured for relay"}), 400
        
        try:
            response = requests.post(
                f"{relay_url}/send/batch",
                json={
                    "template": "test",
                    "chat_ids": chat_ids,
                    "variables": {}
                },
                headers={"X-API-Key": relay_api_key},
                timeout=30
            )
            result = response.json()
            if result.get("success"):
                return jsonify({"success": True, "message": f"Sent to {result.get('successful', 0)} recipients"})
            else:
                return jsonify({"success": False, "error": result.get("error", "Unknown error")}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    else:
        return jsonify({"success": False, "error": f"Provider '{provider}' does not support Telegram. Use 'telegram' or 'relay' provider."}), 400


@app.route("/api/sms-config")
@require_auth
def get_sms_config_api():
    """Get current SMS configuration (sensitive fields masked)."""
    from sms_config import get_full_config
    return jsonify(get_full_config())


@app.route("/api/agent/version")
def get_agent_version():
    """Get the latest available agent version."""
    agent_path = os.path.join(app.root_path, "static", "downloads", "agent.py")
    if not os.path.exists(agent_path):
        return jsonify({"error": "Agent download not available"}), 404
        
    version = "0.0.0"
    try:
        with open(agent_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith('AGENT_VERSION = "'):
                    version = line.split('"')[1]
                    break
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    return jsonify({
        "version": version,
        "download_url": "/static/downloads/agent.py",
        "requirements_url": "/static/downloads/requirements.txt"
    })


@app.route("/api/sms-config", methods=["POST"])
@require_auth
def save_sms_config_api():
    """Save SMS configuration. Expects JSON body with config fields."""
    from sms_config import save_sms_config, get_full_config
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Missing JSON body"}), 400
    
    # Validate required fields
    if "provider" not in data:
        return jsonify({"success": False, "error": "Missing 'provider' field"}), 400
    
    if save_sms_config(data):
        return jsonify({"success": True, "message": "SMS config saved", "config": get_full_config()})
    else:
        return jsonify({"success": False, "error": "Failed to save config"}), 500


@app.route("/api/features")
@require_auth
def get_features_api():
    """Get current feature flags."""
    from config import is_feature_enabled, _load_features, _FEATURES_FILE
    import json
    
    # Get all features from file if exists, else return defaults
    file_features = _load_features()
    
    features = {
        "commands": is_feature_enabled("commands", True),
        "sms": is_feature_enabled("sms", True),
        "alerts": is_feature_enabled("alerts", True),
        "containers": is_feature_enabled("containers", True),
        "pods": is_feature_enabled("pods", True),
        "auto_update": is_feature_enabled("auto_update", True),
        "latency": is_feature_enabled("latency", False),  # v1.48
    }
    
    return jsonify({
        "features": features,
        "config_file": str(_FEATURES_FILE),
        "config_exists": _FEATURES_FILE.exists()
    })


@app.route("/api/features", methods=["POST"])
@require_auth
def save_features_api():
    """Save feature flags. Expects JSON body with feature flags."""
    from config import _FEATURES_FILE
    import json
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Missing JSON body"}), 400
    
    try:
        _FEATURES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_FEATURES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        # Clear cache
        from config import _load_features
        global _features_cache, _features_mtime
        
        return jsonify({"success": True, "message": "Features saved", "features": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/schedule")
@require_auth
def view_schedule():
    """View scheduled SMS jobs and next run times."""
    from datetime import datetime
    import pytz
    
    turkey_tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(turkey_tz)
    
    jobs = []
    for job in scheduler.get_jobs():
        if job.id.startswith("sms_alert"):
            next_run = job.next_run_time
            if next_run:
                next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")
            else:
                next_run_str = "Not scheduled"
            jobs.append({
                "id": job.id,
                "next_run": next_run_str,
                "trigger": str(job.trigger)
            })
    
    return jsonify({
        "timezone": "Europe/Istanbul (Turkey)",
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "sms_recipient": SMS_RECIPIENT or "NOT SET",
        "scheduled_jobs": jobs
    })

@app.route("/api/metrics", methods=["POST"])
@require_api_key
def receive_metrics():
    """Receive metrics from an agent."""
    data = request.get_json()
    
    if not data or "hostname" not in data:
        return jsonify({"error": "Missing hostname"}), 400
    
    hostname = data["hostname"]
    
    # Find or create VM record
    vm = VM.query.filter_by(hostname=hostname).first()
    if not vm:
        vm = VM(hostname=hostname)
        db.session.add(vm)
    
    # Update VM with latest metrics
    vm.cloud_provider = data.get("cloud_provider", vm.cloud_provider)
    vm.last_seen = datetime.utcnow()
    vm.cpu_avg = data.get("cpu_avg", 0)
    vm.cpu_instant = data.get("cpu_instant", 0)
    vm.cpu_count = data.get("cpu_count", 1)
    vm.ram_total_gb = data.get("ram_total_gb", 0)
    vm.ram_used_gb = data.get("ram_used_gb", 0)
    vm.ram_percent = data.get("ram_percent", 0)
    vm.disk_usage = data.get("disk_usage", {})
    
    # OS & Network fields
    vm.os_name = data.get("os_name")
    vm.kernel = data.get("kernel")
    vm.arch = data.get("arch")
    vm.ip_internal = data.get("ip_internal")
    vm.ip_external = data.get("ip_external")
    vm.uptime_seconds = data.get("uptime_seconds")
    vm.agent_version = data.get("agent_version")
    vm.containers = data.get("containers", [])
    vm.pods = data.get("pods", [])
    
    # v1.20 - New metrics
    vm.swap_percent = data.get("swap_percent", 0)
    network_io = data.get("network_io", {})
    vm.network_bytes_sent = network_io.get("bytes_sent", 0)
    vm.network_bytes_recv = network_io.get("bytes_recv", 0)
    vm.pending_updates = data.get("pending_updates", 0)
    vm.open_ports = data.get("open_ports", [])
    vm.ssh_failed_attempts = data.get("ssh_failed_attempts", 0)
    vm.top_processes = data.get("top_processes", [])
    
    # v1.48 - Agent-side latency (HTTP RTT)
    if "latency_ms" in data:
        vm.latency_ms = data["latency_ms"]
        vm.latency_updated_at = datetime.utcnow()
    if "http_rtt_ms" in data:
        vm.http_rtt_ms = data["http_rtt_ms"]
    
    # Store historical metric
    metric = Metric(
        vm=vm,
        cpu_avg=vm.cpu_avg,
        cpu_instant=vm.cpu_instant,
        ram_percent=vm.ram_percent,
        disk_usage=vm.disk_usage
    )
    db.session.add(metric)
    
    # Check for pending commands
    pending_cmds = Command.query.filter_by(vm_id=vm.id, status="pending").all()
    commands_to_send = []
    
    for cmd in pending_cmds:
        commands_to_send.append({
            "id": cmd.id,
            "command": cmd.command,
            "args": cmd.args
        })
        # Mark as sent/running so we don't send again
        cmd.status = "sent"
        
    db.session.commit()
    
    response_data = {"status": "ok", "hostname": hostname}
    if commands_to_send:
        response_data["commands"] = commands_to_send
        
    return jsonify(response_data)


@app.route("/api/vms", methods=["GET"])
@require_auth
def list_vms():
    """List all VMs with their latest metrics. Supports pagination."""
    # v1.30.1 - Pagination for 1000+ VMs
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 100, type=int)
    per_page = min(per_page, 500)  # Cap at 500 per page
    
    # Fast query with pagination
    pagination = VM.query.order_by(VM.hostname).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Use lightweight dict (excludes containers, pods, processes)
    result = [vm.to_list_dict() for vm in pagination.items]
    
    # If client wants pagination info, return wrapped response
    if request.args.get("paginated"):
        return jsonify({
            "vms": result,
            "total": pagination.total,
            "pages": pagination.pages,
            "page": page,
            "per_page": per_page
        })
    
    return jsonify(result)


@app.route("/api/vms/<hostname>", methods=["GET"])
@require_auth
def get_vm(hostname):
    """Get detailed info for a specific VM, including history."""
    vm = VM.query.filter_by(hostname=hostname).first()
    if not vm:
        return jsonify({"error": "VM not found"}), 404
    
    # Time Range Logic (v1.29.1 - Fixed to use actual time filtering)
    range_arg = request.args.get("range", "1h")
    now = datetime.utcnow()
    
    # Define time ranges
    time_ranges = {
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "15d": timedelta(days=15),
        "30d": timedelta(days=30),
    }
    
    delta = time_ranges.get(range_arg, timedelta(hours=1))
    start_time = now - delta
    
    # v1.30.1 - Performance optimized: limit fetch, downsample in Python
    max_points_map = {
        "5m": 30,
        "15m": 45,
        "1h": 60,
        "24h": 100,
        "7d": 100,
        "15d": 100,
        "30d": 100,
    }
    max_points = max_points_map.get(range_arg, 60)
    
    # Fetch with limit to avoid loading huge datasets
    # For short ranges, data is dense - limit is fine
    # For long ranges, we accept showing most recent portion only
    metrics = vm.metrics.filter(
        Metric.timestamp >= start_time
    ).order_by(Metric.timestamp.desc()).limit(max_points * 2).all()
    
    # Reverse to chronological order and downsample if needed
    metrics = list(reversed(metrics))
    if len(metrics) > max_points:
        step = max(1, len(metrics) // max_points)
        metrics = metrics[::step]
    
    result = vm.to_dict()
    result["history"] = [m.to_dict() for m in metrics]
    
    return jsonify(result)


@app.route("/api/vms/<hostname>", methods=["DELETE"])
@require_auth
def delete_vm(hostname):
    """Delete a VM and all its metrics."""
    vm = VM.query.filter_by(hostname=hostname).first()
    if not vm:
        return jsonify({"error": "VM not found"}), 404
    
    db.session.delete(vm)
    db.session.commit()
    
    return jsonify({"status": "deleted", "hostname": hostname})


@app.route("/api/vms/<hostname>/command", methods=["POST"])
@require_auth
def queue_command(hostname):
    """Queue a command for execution on a VM."""
    vm = VM.query.filter_by(hostname=hostname).first()
    if not vm:
        return jsonify({"error": "VM not found"}), 404
    
    data = request.json
    command = data.get("command")
    args = data.get("args", "")
    
    if not command:
        return jsonify({"error": "Missing command"}), 400
        
    cmd = Command(
        vm_id=vm.id,
        command=command,
        args=args,
        status="pending"
    )
    db.session.add(cmd)
    db.session.commit()
    
    return jsonify({"status": "queued", "id": cmd.id})


@app.route("/api/commands/<int:cmd_id>/result", methods=["POST"])
def command_result(cmd_id):
    """Receive command execution result from agent."""
    cmd = Command.query.get(cmd_id)
    if not cmd:
        return jsonify({"error": "Command not found"}), 404
        
    data = request.json
    cmd.status = data.get("status", "completed")
    cmd.output = data.get("output", "")
    cmd.executed_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"status": "success"})


@app.route("/api/commands/<int:cmd_id>", methods=["GET"])
@require_auth
def get_command_status(cmd_id):
    """Get command status and output."""
    cmd = Command.query.get(cmd_id)
    if not cmd:
        return jsonify({"error": "Command not found"}), 404
        
    return jsonify(cmd.to_dict())


# --------------------------
# Authentication Routes
# --------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    # If already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False) == 'on'
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Account is disabled. Contact administrator.', 'error')
                return render_template('login.html')
            
            # Login successful
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Redirect to originally requested page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            return render_template('login.html')
    
    # GET request - show login form
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# --------------------------
# Web UI
# --------------------------

@app.route("/")
def dashboard():
    """Render the dashboard UI."""
    from config import FEATURE_AUTH_ENABLED
    
    # Only require login if authentication is enabled
    if FEATURE_AUTH_ENABLED and not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    version = int(datetime.utcnow().timestamp())
    return render_template("index.html", version=version)


@app.route("/changelog")
def changelog():
    """Render the changelog page."""
    from config import FEATURE_AUTH_ENABLED
    if FEATURE_AUTH_ENABLED and not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template("changelog.html")


@app.route("/health")
def health():
    """Health check (no DB)."""
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()}), 200


@app.route("/api/export")
def export_data():
    """Export all VMs as JSON or CSV."""
    from config import FEATURE_AUTH_ENABLED
    if FEATURE_AUTH_ENABLED and not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401
    fmt = request.args.get("format", "json").lower()
    vms = VM.query.order_by(VM.hostname).all()
    
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        # Header
        writer.writerow([
            "hostname", "cloud_provider", "os_name", "ip_internal", "ip_external",
            "cpu_avg", "cpu_count", "ram_percent", "ram_total_gb", "swap_percent",
            "pending_updates", "ssh_failed_attempts", "agent_version", "last_seen"
        ])
        # Data
        for vm in vms:
            writer.writerow([
                vm.hostname, vm.cloud_provider, vm.os_name, vm.ip_internal, vm.ip_external,
                vm.cpu_avg, vm.cpu_count, vm.ram_percent, vm.ram_total_gb, vm.swap_percent,
                vm.pending_updates, vm.ssh_failed_attempts, vm.agent_version,
                vm.last_seen.isoformat() if vm.last_seen else None
            ])
        
        response = app.response_class(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=vms_export.csv"}
        )
        return response
    
    # Default: JSON
    return jsonify([vm.to_dict() for vm in vms])


@app.route("/logs")
def view_logs():
    """View access logs (most recent first)."""
    from config import FEATURE_AUTH_ENABLED
    if FEATURE_AUTH_ENABLED and not current_user.is_authenticated:
        return redirect(url_for('login'))
    lines = request.args.get("lines", 100, type=int)
    lines = min(lines, 1000)  # Cap at 1000 lines
    
    log_entries = []
    if os.path.exists(ACCESS_LOG_FILE):
        try:
            with open(ACCESS_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                log_entries = all_lines[-lines:][::-1]  # Reverse for newest first
        except Exception as e:
            log_entries = [f"Error reading log: {e}"]
    else:
        log_entries = ["No log file yet."]
    
    # Simple HTML page
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Access Logs - VM Dashboard</title>
        <style>
            body { font-family: monospace; background: #1e1e1e; color: #d4d4d4; padding: 20px; }
            h1 { color: #569cd6; }
            .log-line { padding: 4px 0; border-bottom: 1px solid #333; white-space: nowrap; overflow-x: auto; }
            .controls { margin-bottom: 20px; }
            a { color: #4ec9b0; }
            select, button { padding: 8px 16px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <h1>Access Logs</h1>
        <div class="controls">
            <a href="/">← Back to Dashboard</a> |
            <a href="/logs?lines=50">Last 50</a> |
            <a href="/logs?lines=100">Last 100</a> |
            <a href="/logs?lines=500">Last 500</a> |
            <a href="/logs?lines=1000">Last 1000</a>
        </div>
        <div class="log-container">
    """
    for line in log_entries:
        html += f'<div class="log-line">{line.strip()}</div>\n'
    html += """
        </div>
    </body>
    </html>
    """
    return html


# --------------------------
# App Initialization
# --------------------------

# Schema is managed by migrate_db.py during deployment
# with app.app_context():
#     db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

