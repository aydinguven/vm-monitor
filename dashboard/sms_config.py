"""
SMS Configuration - Loads SMS settings from config file or environment variables.

Config file location: instance/sms_config.json
Falls back to environment variables if file doesn't exist.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Config file path (same folder as database)
CONFIG_DIR = Path(__file__).parent / "instance"
CONFIG_FILE = CONFIG_DIR / "sms_config.json"

# Cache for config (reloaded on each access to support hot-reload)
_config_cache: Optional[Dict[str, Any]] = None
_config_mtime: float = 0


def _load_config() -> Dict[str, Any]:
    """Load config from file, with caching based on file modification time."""
    global _config_cache, _config_mtime
    
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        current_mtime = CONFIG_FILE.stat().st_mtime
        if _config_cache is not None and current_mtime == _config_mtime:
            return _config_cache
        
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
            _config_mtime = current_mtime
            logger.info(f"Loaded SMS config from {CONFIG_FILE}")
            return _config_cache
    except Exception as e:
        logger.error(f"Error loading SMS config: {e}")
        return {}


def get_sms_config(key: str, default = ""):
    """
    Get SMS configuration value.
    
    Priority:
    1. Config file (instance/sms_config.json)
    2. Environment variable
    3. Default value
    
    Key mapping:
    - "provider" -> SMS_PROVIDER env var
    - "recipient" -> SMS_RECIPIENT env var
    - "dashboard_url" -> SMS_DASHBOARD_URL env var
    - "twilio.account_sid" -> TWILIO_ACCOUNT_SID env var
    - "twilio.auth_token" -> TWILIO_AUTH_TOKEN env var
    - "twilio.from_number" -> TWILIO_FROM_NUMBER env var
    - etc.
    """
    config = _load_config()
    
    # Try config file first
    if config:
        # Handle nested keys like "twilio.account_sid"
        parts = key.split(".")
        value = config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break
        
        if value is not None:
            return value
    
    # Fall back to environment variable (only for string values)
    env_key = _key_to_env(key)
    return os.getenv(env_key, default)


def _key_to_env(key: str) -> str:
    """Convert config key to environment variable name."""
    mapping = {
        "provider": "SMS_PROVIDER",
        "recipient": "SMS_RECIPIENT",
        "dashboard_url": "SMS_DASHBOARD_URL",
        "twilio.account_sid": "TWILIO_ACCOUNT_SID",
        "twilio.auth_token": "TWILIO_AUTH_TOKEN",
        "twilio.from_number": "TWILIO_FROM_NUMBER",
        "textbelt.api_key": "TEXTBELT_API_KEY",
        "iletimerkezi.api_key": "ILETIMERKEZI_API_KEY",
        "iletimerkezi.api_hash": "ILETIMERKEZI_API_HASH",
        "iletimerkezi.sender": "ILETIMERKEZI_SENDER",
        "telegram.bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram.chat_id": "TELEGRAM_CHAT_ID",
        "relay.url": "RELAY_URL",
        "relay.api_key": "RELAY_API_KEY",
        "relay.template": "RELAY_TEMPLATE",
    }
    return mapping.get(key, key.upper().replace(".", "_"))


def save_sms_config(config: Dict[str, Any]) -> bool:
    """Save SMS configuration to file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Saved SMS config to {CONFIG_FILE}")
        
        # Clear cache to force reload
        global _config_cache, _config_mtime
        _config_cache = None
        _config_mtime = 0
        
        return True
    except Exception as e:
        logger.error(f"Error saving SMS config: {e}")
        return False


def get_sms_schedule_times() -> list:
    """
    Get SMS schedule times from config.
    
    Returns list of (hour, minute) tuples.
    Example config: {"schedule": {"times": ["09:00", "11:30", "14:30", "17:00"]}}
    
    Falls back to default times if not configured.
    """
    config = _load_config()
    default_times = [(8, 30), (12, 0), (13, 30), (17, 0)]
    
    if not config:
        return default_times
    
    schedule = config.get("schedule", {})
    times_config = schedule.get("times", [])
    
    if not times_config:
        return default_times
    
    times = []
    for time_str in times_config:
        try:
            if ":" in time_str:
                parts = time_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    times.append((hour, minute))
                else:
                    logger.warning(f"Invalid time value: {time_str}")
            else:
                # Just hour number
                hour = int(time_str)
                if 0 <= hour <= 23:
                    times.append((hour, 0))
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid time format '{time_str}': {e}")
    
    return times if times else default_times


def get_full_config() -> Dict[str, Any]:
    """Get the full configuration (for API endpoints)."""
    config = _load_config()
    
    # If no config file, build from env vars
    if not config:
        config = {
            "provider": os.getenv("SMS_PROVIDER", "disabled"),
            "recipient": os.getenv("SMS_RECIPIENT", ""),
            "dashboard_url": os.getenv("SMS_DASHBOARD_URL", "https://your-dashboard.com"),
            "twilio": {
                "account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
                "auth_token": "",  # Never expose auth token
                "from_number": os.getenv("TWILIO_FROM_NUMBER", "")
            },
            "textbelt": {
                "api_key": ""  # Never expose API key
            },
            "iletimerkezi": {
                "api_key": "",  # Never expose
                "api_hash": "",  # Never expose
                "sender": os.getenv("ILETIMERKEZI_SENDER", "")
            }
        }
    else:
        # Mask sensitive fields
        config = json.loads(json.dumps(config))  # Deep copy
        if "twilio" in config:
            if "auth_token" in config["twilio"]:
                config["twilio"]["auth_token"] = "***" if config["twilio"]["auth_token"] else ""
        if "textbelt" in config:
            if "api_key" in config["textbelt"]:
                config["textbelt"]["api_key"] = "***" if config["textbelt"]["api_key"] else ""
        if "iletimerkezi" in config:
            if "api_key" in config["iletimerkezi"]:
                config["iletimerkezi"]["api_key"] = "***" if config["iletimerkezi"]["api_key"] else ""
            if "api_hash" in config["iletimerkezi"]:
                config["iletimerkezi"]["api_hash"] = "***" if config["iletimerkezi"]["api_hash"] else ""
        if "telegram" in config:
            if "bot_token" in config["telegram"]:
                config["telegram"]["bot_token"] = "***" if config["telegram"]["bot_token"] else ""
    
    return config

