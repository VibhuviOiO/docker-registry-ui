import os
import json
import logging

from .logger import setup_logging

# Configure JSON logging as early as possible so that even import-time
# messages are emitted in JSON format.
setup_logging()
logger = logging.getLogger(__name__)

class Config:
    # Legacy single registry support
    REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry.vibhuvioio.com")
    READ_ONLY = os.getenv("READ_ONLY", "true").lower() == "true"
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
    TIMEOUT = int(os.getenv("TIMEOUT", "10"))
    BUILT_BY = os.getenv("BUILT_BY", "Vibhuvi OiO")
    
    # Multi-registry support
    REGISTRIES = []
    CONFIG_FILE = os.getenv("CONFIG_FILE", "/app/registries.config.json")
    USE_ENV_CONFIG = False
    
    # Data and cache directories
    DATA_DIR = os.getenv("DATA_DIR", "/app/data")
    TRIVY_CACHE_DIR = os.getenv("TRIVY_CACHE_DIR", "/root/.cache/trivy")
    
    # Concurrency limits
    UVICORN_WORKERS = int(os.getenv("UVICORN_WORKERS", "4"))
    SCAN_WORKERS = int(os.getenv("SCAN_WORKERS", "2"))
    
    # Scan retry policy: transient failures (e.g. concurrent push/pull) are retried
    SCAN_RETRIES = int(os.getenv("SCAN_RETRIES", "3"))
    SCAN_RETRY_DELAY = int(os.getenv("SCAN_RETRY_DELAY", "2"))
    
    @staticmethod
    def load_registries():
        """Load registries from environment or config file"""
        registries_json = os.getenv("REGISTRIES")
        
        if registries_json:
            try:
                Config.REGISTRIES = json.loads(registries_json)
                Config.USE_ENV_CONFIG = True
            except:
                pass
        
        # Try loading from file if env not set
        if not Config.REGISTRIES and os.path.exists(Config.CONFIG_FILE):
            try:
                with open(Config.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    # Handle both formats: {"registries": [...]} and [...]
                    if isinstance(data, dict) and "registries" in data:
                        Config.REGISTRIES = data["registries"]
                    elif isinstance(data, list):
                        Config.REGISTRIES = data
                    else:
                        Config.REGISTRIES = []
                Config.USE_ENV_CONFIG = False
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                pass
        
        # If no registries configured, use legacy single registry
        if not Config.REGISTRIES:
            Config.REGISTRIES = []
        
        return Config.REGISTRIES
    
    @staticmethod
    def save_registries():
        """Save registries to config file"""
        if Config.USE_ENV_CONFIG:
            return False
        
        try:
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump(Config.REGISTRIES, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

# Load registries on import
Config.load_registries()
