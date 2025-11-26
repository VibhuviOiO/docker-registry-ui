from .config import Config

# Simple in-memory cache for repositories (no background updates)
registry_cache = {}
scan_results = {}

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
                reg["vulnerabilityScan"]["autoScan"] = config["vulnerabilityScan"].get("autoScan", False)
            Config.save_registries()
            return True
    return False

def store_scan_results(registry_name, repo, tag, result):
    """Store vulnerability scan results"""
    from datetime import datetime
    import json
    import os
    
    result["repo"] = repo
    result["tag"] = tag
    result["scannedAt"] = datetime.now().isoformat()
    
    # Store in memory
    if registry_name not in scan_results:
        scan_results[registry_name] = {}
    key = f"{repo}:{tag}"
    scan_results[registry_name][key] = result
    
    # Persist to per-image file only
    data_dir = os.path.dirname(Config.CONFIG_FILE) if Config.CONFIG_FILE else '/app/data'
    os.makedirs(data_dir, exist_ok=True)
    
    image_file = os.path.join(data_dir, f"{repo.replace('/', '_')}_{tag}.json")
    try:
        with open(image_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Saved scan to: {image_file}")
    except Exception as e:
        print(f"Failed to save scan to {image_file}: {e}")

def get_scan_results(registry_name):
    """Get all scan results for a registry from individual image files"""
    import json
    import os
    import glob
    
    if registry_name not in scan_results:
        scan_results[registry_name] = {}
    
    data_dir = os.path.dirname(Config.CONFIG_FILE) if Config.CONFIG_FILE else '/app/data'
    
    # Load all individual scan files
    scan_files = glob.glob(os.path.join(data_dir, "*_*.json"))
    for scan_file in scan_files:
        filename = os.path.basename(scan_file)
        # Skip registry config files
        if filename.startswith('scan_results_') or filename == 'registries.config.json':
            continue
        
        try:
            with open(scan_file, 'r') as f:
                result = json.load(f)
                repo = result.get('repo')
                tag = result.get('tag')
                if repo and tag:
                    key = f"{repo}:{tag}"
                    scan_results[registry_name][key] = result
        except Exception as e:
            print(f"Failed to load {scan_file}: {e}")
    
    print(f"Loaded {len(scan_results[registry_name])} scan results for {registry_name}")
    return scan_results.get(registry_name, {})
