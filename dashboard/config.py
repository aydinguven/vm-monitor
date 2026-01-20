"""
VM Dashboard - Configuration
Copy this file to config.py and customize for your environment.
"""

import os

# Flask settings
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-in-production")
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# Database
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///vm_metrics.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False

# API Authentication
API_KEY = os.getenv("VM_DASHBOARD_API_KEY", "changeme")

# Metrics settings
METRIC_RETENTION_HOURS = int(os.getenv("METRIC_RETENTION_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "60"))

# VM offline threshold (seconds since last metric)
VM_OFFLINE_THRESHOLD = int(os.getenv("VM_OFFLINE_THRESHOLD", "120"))

# SMS Alerts Configuration - loaded from instance/sms_config.json or env vars
# See sms_config.py for details
from sms_config import get_sms_config

def get_sms_recipient():
    """Get SMS recipient (supports hot-reload from config file)."""
    return get_sms_config("recipient", "")

def get_sms_dashboard_url():
    """Get SMS dashboard URL (supports hot-reload from config file)."""
    return get_sms_config("dashboard_url", "https://your-dashboard.com")

# For backward compatibility (static values at import time)
SMS_PROVIDER = get_sms_config("provider", "disabled")
SMS_RECIPIENT = get_sms_recipient()
SMS_DASHBOARD_URL = get_sms_dashboard_url()

# Alert thresholds (percent)
ALERT_WARNING_THRESHOLD = int(os.getenv("ALERT_WARNING_THRESHOLD", "80"))
ALERT_CRITICAL_THRESHOLD = int(os.getenv("ALERT_CRITICAL_THRESHOLD", "90"))


# =============================================================================
# Feature Flags - Enable/disable features via config file or env vars
# Config file: instance/features.json
# =============================================================================

import json
from pathlib import Path

_FEATURES_FILE = Path(__file__).parent / "instance" / "features.json"
_features_cache = None
_features_mtime = 0


def _load_features() -> dict:
    """Load feature flags from file with caching."""
    global _features_cache, _features_mtime
    
    if not _FEATURES_FILE.exists():
        return {}
    
    try:
        current_mtime = _FEATURES_FILE.stat().st_mtime
        if _features_cache is not None and current_mtime == _features_mtime:
            return _features_cache
        
        with open(_FEATURES_FILE, "r", encoding="utf-8") as f:
            _features_cache = json.load(f)
            _features_mtime = current_mtime
            return _features_cache
    except Exception:
        return {}


def is_feature_enabled(feature: str, default: bool = True) -> bool:
    """
    Check if a feature is enabled.
    
    Priority:
    1. instance/features.json
    2. Environment variable (FEATURE_<NAME>=true/false)
    3. Default value
    
    Available features:
    - commands: Remote command execution
    - sms: SMS alerts
    - alerts: Alert/warning detection
    - containers: Container discovery
    - pods: Kubernetes pod discovery
    - auto_update: Agent auto-updates
    """
    features = _load_features()
    
    # Check config file first
    if feature.lower() in features:
        return bool(features[feature.lower()])
    
    # Check environment variable
    env_val = os.getenv(f"FEATURE_{feature.upper()}", "").lower()
    if env_val in ("true", "1", "yes"):
        return True
    if env_val in ("false", "0", "no"):
        return False
    
    return default


# Default feature flags (all enabled by default)
FEATURE_COMMANDS = is_feature_enabled("commands", True)
FEATURE_SMS = is_feature_enabled("sms", True)
FEATURE_ALERTS = is_feature_enabled("alerts", True)
FEATURE_CONTAINERS = is_feature_enabled("containers", True)
FEATURE_PODS = is_feature_enabled("pods", True)
FEATURE_AUTO_UPDATE = is_feature_enabled("auto_update", True)

