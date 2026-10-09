import os
import json
import logging

from .logger import setup_logging

# Configure JSON logging as early as possible so that even import-time
# messages are emitted in JSON format.
setup_logging()
logger = logging.getLogger(__name__)

class Config:
    # Read-only mode disables the destructive operations (deleting tags and
    # repositories, bulk cleanup). It must default to false: the first-run setup
    # wizard creates a registry through /api/registry/create, which is refused
    # while read-only, so a true default left a fresh install unable to be
    # configured at all. Set READ_ONLY=true when exposing the UI publicly.
    READ_ONLY = os.getenv("READ_ONLY", "false").lower() == "true"
    TIMEOUT = int(os.getenv("TIMEOUT", "10"))
    BUILT_BY = os.getenv("BUILT_BY", "Vibhuvi OiO")
    
    # Multi-registry support
    REGISTRIES = []
    # Empty means "not set": the location is then resolved by config_file()
    # to sit inside DATA_DIR, which is the directory the quick start mounts.
    CONFIG_FILE = os.getenv("CONFIG_FILE", "")
    # Where the image used to look before the default moved into DATA_DIR.
    # Honoured only when it exists and nothing newer does.
    LEGACY_CONFIG_FILE = "/app/registries.config.json"
    USE_ENV_CONFIG = False
    
    # Data and cache directories
    DATA_DIR = os.getenv("DATA_DIR", "/app/data")
    # Passed to the Trivy CLI as --cache-dir, so the documented knob is real.
    TRIVY_CACHE_DIR = os.getenv("TRIVY_CACHE_DIR", "/root/.cache/trivy")
    
    # Concurrency limits
    UVICORN_WORKERS = int(os.getenv("UVICORN_WORKERS", "4"))
    # Per uvicorn worker process; total concurrent scans is SCAN_WORKERS x workers.
    SCAN_WORKERS = int(os.getenv("SCAN_WORKERS", "2"))
    
    # Scan retry policy: transient failures (e.g. concurrent push/pull) are retried
    SCAN_RETRIES = int(os.getenv("SCAN_RETRIES", "3"))
    SCAN_RETRY_DELAY = int(os.getenv("SCAN_RETRY_DELAY", "2"))
    
    @staticmethod
    def config_file():
        """Where registries are read from and written to.

        Defaults to ``<DATA_DIR>/registries.config.json``. The quick start mounts
        only ``DATA_DIR``, so anything else means the setup wizard's configuration
        is written into the container filesystem and lost on restart.

        Precedence: an explicit ``CONFIG_FILE`` wins, then the new default if it
        already exists, then the old default if that exists (so deployments that
        mount ``/app/registries.config.json`` keep working), then the new default.
        """
        if Config.CONFIG_FILE:
            return Config.CONFIG_FILE

        default = os.path.join(Config.DATA_DIR, "registries.config.json")
        if os.path.exists(default):
            return default
        if os.path.exists(Config.LEGACY_CONFIG_FILE):
            return Config.LEGACY_CONFIG_FILE
        return default
    
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
        config_path = Config.config_file()
        if not Config.REGISTRIES and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
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
        
        config_path = Config.config_file()
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(Config.REGISTRIES, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

# Load registries on import
Config.load_registries()
