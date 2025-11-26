import os
import json

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
                    Config.REGISTRIES = json.load(f)
                Config.USE_ENV_CONFIG = False
            except:
                pass
        
        # If no registries configured, use legacy single registry
        if not Config.REGISTRIES:
            Config.REGISTRIES = [{
                "name": "Default Registry",
                "api": Config.REGISTRY_URL,
                "isAuthEnabled": False,
                "user": "",
                "password": "",
                "apiToken": ""
            }]
        
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
            print(f"Failed to save config: {e}")
            return False

# Load registries on import
Config.load_registries()
