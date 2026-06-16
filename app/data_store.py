from .config import Config
import uuid
import logging

logger = logging.getLogger(__name__)

# Simple in-memory cache for repositories (no background updates)
registry_cache = {}
scan_results = {}
scan_jobs = {}

def _scan_job_path(job_id):
    """Get file path for a scan job"""
    import os
    jobs_dir = os.path.join(Config.DATA_DIR, "scan_jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    return os.path.join(jobs_dir, f"{job_id}.json")

def _load_scan_job(job_id):
    """Load scan job from disk"""
    import json
    import os
    path = _scan_job_path(job_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None

def _save_scan_job(job):
    """Save scan job to disk"""
    import json
    import os
    path = _scan_job_path(job["id"])
    temp_path = path + ".tmp"
    try:
        with open(temp_path, 'w') as f:
            json.dump(job, f, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        logger.error(f"Failed to save scan job {job['id']}: {e}")

def create_scan_job(registry_name, repo, tag):
    """Create a new async scan job"""
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "registry_name": registry_name,
        "repo": repo,
        "tag": tag,
        "status": "in_progress",
        "result": None,
        "error": None
    }
    _save_scan_job(job)
    # Keep in-memory copy as well for fast access
    scan_jobs[job_id] = job
    return job_id

def get_scan_job(job_id):
    """Get scan job by ID (from memory or disk)"""
    job = scan_jobs.get(job_id)
    if job:
        return job
    return _load_scan_job(job_id)

def update_scan_job(job_id, status=None, result=None, error=None):
    """Update scan job status and result"""
    job = get_scan_job(job_id)
    if not job:
        return False
    if status is not None:
        job["status"] = status
    if result is not None:
        job["result"] = result
    if error is not None:
        job["error"] = error
    _save_scan_job(job)
    scan_jobs[job_id] = job
    return True

def get_registries():
    """Get list of configured registries"""
    return Config.REGISTRIES

def get_registry_by_name(name):
    """Get registry config by name"""
    for reg in Config.REGISTRIES:
        # Handle both string and dictionary formats
        if isinstance(reg, str):
            if reg == name:
                return {
                    "name": reg,
                    "api": "http://registry:5000",  # Default for development
                    "isAuthEnabled": False,
                    "default": True,
                    "bulkOperationsEnabled": False
                }
        else:
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
    
    # Persist to per-image file under configured data directory
    data_dir = Config.DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    
    image_file = os.path.join(data_dir, f"{repo.replace('/', '_')}_{tag}.json")
    try:
        with open(image_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved scan to: {image_file}")
    except Exception as e:
        logger.error(f"Failed to save scan to {image_file}: {e}")

def get_scan_results(registry_name):
    """Get all scan results for a registry from individual image files"""
    import json
    import os
    import glob
    
    if registry_name not in scan_results:
        scan_results[registry_name] = {}
    
    data_dir = Config.DATA_DIR
    
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
            logger.error(f"Failed to load {scan_file}: {e}")
    
    logger.info(f"Loaded {len(scan_results[registry_name])} scan results for {registry_name}")
    return scan_results.get(registry_name, {})
