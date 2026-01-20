"""
General Configuration - Loads general settings from config file.

Config file location: instance/config.json
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Config file path (same folder as database)
CONFIG_DIR = Path(__file__).parent / "instance"
CONFIG_FILE = CONFIG_DIR / "config.json"

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
            logger.info(f"Loaded general config from {CONFIG_FILE}")
            return _config_cache
    except Exception as e:
        logger.error(f"Error loading general config: {e}")
        return {}


def get_general_config(key: str, default: Any = None) -> Any:
    """
    Get general configuration value.
    
    Priority:
    1. Config file (instance/config.json)
    2. Default value
    """
    config = _load_config()
    return config.get(key, default)
