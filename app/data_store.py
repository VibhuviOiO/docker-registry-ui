from .config import Config

# Simple in-memory cache for repositories (no background updates)
registry_cache = {}

def get_registries():
    """Get list of configured registries"""
    return Config.REGISTRIES

def get_registry_by_name(name):
    """Get registry config by name"""
    for reg in Config.REGISTRIES:
        if reg["name"] == name:
            return reg
    return None

def cache_repositories(registry_name, repos):
    """Cache repository list"""
    registry_cache[registry_name] = repos

def get_cached_repositories(registry_name):
    """Get cached repository list"""
    return registry_cache.get(registry_name, [])

def update_registry_bulk_ops(registry_name, enabled):
    """Update bulk operations setting for a registry"""
    for reg in Config.REGISTRIES:
        if reg["name"] == registry_name:
            reg["bulkOperationsEnabled"] = enabled
            Config.save_registries()
            return True
    return False

def update_registry_config(registry_name, config):
    """Update registry configuration"""
    for reg in Config.REGISTRIES:
        if reg["name"] == registry_name:
            reg["bulkOperationsEnabled"] = config.get("bulkOperationsEnabled", False)
            if "vulnerabilityScan" in config:
                if "vulnerabilityScan" not in reg:
                    reg["vulnerabilityScan"] = {}
                reg["vulnerabilityScan"]["enabled"] = config["vulnerabilityScan"].get("enabled", False)
                reg["vulnerabilityScan"]["scanner"] = config["vulnerabilityScan"].get("scanner", "trivy")
                reg["vulnerabilityScan"]["scannerUrl"] = config["vulnerabilityScan"].get("scannerUrl", "")
                reg["vulnerabilityScan"]["autoScanRules"] = config["vulnerabilityScan"].get("autoScanRules", [])
                reg["vulnerabilityScan"]["scanLatestOnly"] = config["vulnerabilityScan"].get("scanLatestOnly", 1)
            Config.save_registries()
            return True
    return False
