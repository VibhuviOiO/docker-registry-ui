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
