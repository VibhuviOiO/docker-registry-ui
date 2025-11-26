from flask import Blueprint, render_template, jsonify, request
from .config import Config
from .data_store import get_registries, get_registry_by_name, cache_repositories, get_cached_repositories
from .registry import (
    format_size, fetch_repositories, fetch_repository_tags,
    fetch_tag_details, delete_tag, delete_repository, get_auth
)
import logging
import requests

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

@main_bp.route("/")
def index():
    from flask import current_app
    registries = get_registries()
    return render_template('index.html',
                          registries=registries,
                          read_only=Config.READ_ONLY,
                          version=current_app.config.get('VERSION', '1.0.0'),
                          built_by=Config.BUILT_BY)

@api_bp.route("/registries")
def api_registries():
    """Get list of configured registries"""
    registries = get_registries()
    # Don't expose credentials
    safe_registries = []
    for reg in registries:
        vuln_scan = reg.get("vulnerabilityScan", {})
        safe_registries.append({
            "name": reg["name"],
            "api": reg["api"],
            "url": reg.get("api", "").replace("http://", "").replace("https://", ""),
            "isAuthEnabled": reg.get("isAuthEnabled", False),
            "default": reg.get("default", False),
            "bulkOperationsEnabled": reg.get("bulkOperationsEnabled", False),
            "vulnerabilityScan": {
                "enabled": vuln_scan.get("enabled", False),
                "scanner": vuln_scan.get("scanner", "trivy"),
                "scannerUrl": vuln_scan.get("scannerUrl", "")
            }
        })
    return jsonify({"registries": safe_registries})

@api_bp.route("/repositories/<registry_name>")
def api_repositories(registry_name):
    """Get repositories for a specific registry"""
    logger.info(f"Fetching repositories for registry: {registry_name}")
    registry = get_registry_by_name(registry_name)
    if not registry:
        logger.warning(f"Registry not found: {registry_name}")
        return jsonify({"error": "Registry not found"}), 404
    
    # Always fetch fresh data (no caching)
    auth = get_auth(registry)
    repos, error = fetch_repositories(registry["api"], auth)
    
    if error:
        logger.error(f"Error fetching repositories from {registry_name}: {error}")
        return jsonify({"error": error}), 500
    
    logger.info(f"Found {len(repos)} repositories in {registry_name}")
    return jsonify({"repositories": repos})

@api_bp.route("/tags/<registry_name>/<path:repo>")
def api_tags(registry_name, repo):
    """Get tags for a repository"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"error": "Registry not found"}), 404
    
    auth = get_auth(registry)
    tags = fetch_repository_tags(registry["api"], repo, auth)
    
    return jsonify({"tags": tags})

@api_bp.route("/tag-details/<registry_name>/<path:repo>/<tag>")
def api_tag_details(registry_name, repo, tag):
    """Get details for a specific tag"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"error": "Registry not found"}), 404
    
    auth = get_auth(registry)
    details = fetch_tag_details(registry["api"], repo, tag, auth)
    
    return jsonify(details)

@api_bp.route("/delete/tag/<registry_name>/<path:repo>/<tag>", methods=["DELETE"])
def api_delete_tag(registry_name, repo, tag):
    """Delete a tag"""
    if Config.READ_ONLY:
        logger.warning(f"Delete attempt in read-only mode: {repo}:{tag}")
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"success": False, "error": "Registry not found"}), 404
    
    logger.info(f"Deleting tag {repo}:{tag} from {registry_name}")
    auth = get_auth(registry)
    success, error = delete_tag(registry["api"], repo, tag, auth)
    
    if success:
        logger.info(f"Successfully deleted {repo}:{tag}")
        return jsonify({"success": True})
    else:
        logger.error(f"Failed to delete {repo}:{tag}: {error}")
        return jsonify({"success": False, "error": error})

@api_bp.route("/delete/repo/<registry_name>/<path:repo>", methods=["DELETE"])
def api_delete_repo(registry_name, repo):
    """Delete entire repository"""
    if Config.READ_ONLY:
        logger.warning(f"Repository delete attempt in read-only mode: {repo}")
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"success": False, "error": "Registry not found"}), 404
    
    logger.info(f"Deleting repository {repo} from {registry_name}")
    auth = get_auth(registry)
    success, error, deleted, total = delete_repository(registry["api"], repo, auth)
    
    if success:
        logger.info(f"Successfully deleted {repo}: {deleted}/{total} tags")
        return jsonify({"success": True, "deleted": deleted, "total": total})
    else:
        logger.error(f"Failed to delete {repo}: {error}")
        return jsonify({"success": False, "error": error})

@api_bp.route("/bulk-operation", methods=["POST"])
def api_bulk_operation():
    """Execute bulk cleanup operation"""
    if Config.READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    data = request.json
    registry_name = data.get("registry")
    
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"success": False, "error": "Registry not found"}), 404
    
    if not registry.get("bulkOperationsEnabled", False):
        return jsonify({"success": False, "error": "Bulk operations not enabled for this registry"}), 403
    
    registry_name = data.get("registry")
    repo_pattern = data.get("repoPattern", "*")
    older_than_days = data.get("olderThanDays")
    keep_min = data.get("keepMin", 0)
    tag_pattern = data.get("tagPattern")
    dry_run = data.get("dryRun", True)
    
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"success": False, "error": "Registry not found"}), 404
    
    auth = get_auth(registry)
    repos, error = fetch_repositories(registry["api"], auth)
    
    if error:
        return jsonify({"success": False, "error": error}), 500
    
    import re
    from datetime import datetime, timedelta
    
    # Filter repos by pattern
    if repo_pattern and repo_pattern != "*":
        pattern = repo_pattern.replace("*", ".*")
        repos = [r for r in repos if re.match(pattern, r)]
    
    results = []
    for repo in repos:
        tags = fetch_repository_tags(registry["api"], repo, auth)
        tags_to_delete = []
        
        for tag in tags:
            details = fetch_tag_details(registry["api"], repo, tag, auth)
            
            # Check tag pattern
            if tag_pattern and not re.match(tag_pattern, tag):
                continue
            
            # Check age
            if older_than_days and details.get("created"):
                created = datetime.fromisoformat(details["created"].replace("Z", "+00:00"))
                cutoff = datetime.now(created.tzinfo) - timedelta(days=older_than_days)
                if created > cutoff:
                    continue
            
            tags_to_delete.append(tag)
        
        # Keep minimum tags
        if keep_min > 0 and len(tags_to_delete) > len(tags) - keep_min:
            tags_to_delete = tags_to_delete[:len(tags) - keep_min]
        
        if tags_to_delete:
            results.append({"repo": repo, "tags": tags_to_delete, "count": len(tags_to_delete)})
            
            if not dry_run:
                for tag in tags_to_delete:
                    delete_tag(registry["api"], repo, tag, auth)
    
    return jsonify({"success": True, "results": results, "dryRun": dry_run})

@api_bp.route("/registry/bulk-operations", methods=["POST"])
def api_toggle_bulk_operations():
    """Toggle bulk operations for a registry"""
    if Config.READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    data = request.json
    registry_name = data.get("registry")
    enabled = data.get("enabled", False)
    
    from .data_store import update_registry_bulk_ops
    success = update_registry_bulk_ops(registry_name, enabled)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Failed to update registry"}), 500

@api_bp.route("/registry/config", methods=["POST"])
def api_update_registry_config():
    """Update registry configuration"""
    if Config.READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    data = request.json
    registry_name = data.get("registry")
    
    from .data_store import update_registry_config
    success = update_registry_config(registry_name, data)
    
    if success:
        if Config.USE_ENV_CONFIG:
            return jsonify({"success": True, "message": "Configuration updated in memory. Using environment variable - changes will be lost on restart. Update REGISTRIES env var to persist."})
        else:
            return jsonify({"success": True, "message": "Configuration saved to file and persisted."})
    else:
        return jsonify({"success": False, "error": "Failed to update registry"}), 500

@api_bp.route("/scan/<registry_name>/<path:repo>/<tag>")
def api_scan_image(registry_name, repo, tag):
    """Scan image for vulnerabilities"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"error": "Registry not found"}), 404
    
    vuln_scan = registry.get("vulnerabilityScan", {})
    if not vuln_scan.get("enabled"):
        return jsonify({"error": "Vulnerability scanning not enabled for this registry"}), 400
    
    try:
        from .scanners.factory import get_scanner
        scanner = get_scanner(vuln_scan.get("scanner", "trivy"), vuln_scan.get("scannerUrl"))
        
        registry_url = registry["api"].replace("http://", "").replace("https://", "")
        result = scanner.scan_image(registry_url, repo, tag)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Scan error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/test-registry", methods=["POST"])
def api_test_registry():
    """Test registry connection"""
    data = request.json
    api = data.get("api")
    
    if not api:
        return jsonify({"success": False, "error": "API URL required"}), 400
    
    try:
        auth = None
        if data.get("isAuthEnabled"):
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(data.get("user"), data.get("password"))
        
        response = requests.get(f"{api}/v2/_catalog", auth=auth, timeout=5)
        
        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"HTTP {response.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@api_bp.route("/registry/create", methods=["POST"])
def api_create_registry():
    """Create new registry"""
    if Config.READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    registry = request.json
    
    if not registry.get("name") or not registry.get("api"):
        return jsonify({"success": False, "error": "Name and API URL required"}), 400
    
    # If this is the first registry or marked as default, unset other defaults
    if registry.get("default") or len(Config.REGISTRIES) == 0:
        for reg in Config.REGISTRIES:
            reg["default"] = False
        registry["default"] = True
    
    Config.REGISTRIES.append(registry)
    
    if Config.save_registries():
        return jsonify({"success": True, "message": "Registry created and saved to file"})
    else:
        return jsonify({"success": True, "message": "Registry created (in-memory only - using env config)"})

@api_bp.route("/test-scanner", methods=["POST"])
def api_test_scanner():
    """Test scanner connection"""
    data = request.json
    url = data.get("url")
    scanner_type = data.get("scanner", "trivy")
    
    if not url:
        return jsonify({"success": False, "error": "Scanner URL required"}), 400
    
    try:
        if scanner_type == "trivy":
            response = requests.get(f"{url}/healthz", timeout=5)
        else:
            response = requests.get(f"{url}/health", timeout=5)
        
        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"HTTP {response.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@api_bp.route("/registry/vuln-scan", methods=["POST"])
def api_update_vuln_scan():
    """Update vulnerability scanning configuration"""
    if Config.READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    data = request.json
    registry_name = data.get("registry")
    vuln_config = data.get("vulnerabilityScan")
    
    from .data_store import update_registry_config
    success = update_registry_config(registry_name, {"vulnerabilityScan": vuln_config})
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Failed to update registry"}), 500

@api_bp.route("/scan-all/<registry_name>", methods=["POST"])
def api_scan_all(registry_name):
    """Scan all images in registry based on auto-scan rules"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"success": False, "error": "Registry not found"}), 404
    
    vuln_scan = registry.get("vulnerabilityScan", {})
    if not vuln_scan.get("enabled"):
        return jsonify({"success": False, "error": "Vulnerability scanning not enabled"}), 400
    
    try:
        from .scanners.factory import get_scanner
        import re
        
        scanner = get_scanner(vuln_scan.get("scanner", "trivy"), vuln_scan.get("scannerUrl"))
        auth = get_auth(registry)
        repos, error = fetch_repositories(registry["api"], auth)
        
        if error:
            return jsonify({"success": False, "error": error}), 500
        
        auto_scan_rules = vuln_scan.get("autoScanRules", [])
        scan_latest_only = vuln_scan.get("scanLatestOnly", 1)
        registry_url = registry["api"].replace("http://", "").replace("https://", "")
        scanned = 0
        
        for repo in repos:
            should_scan = not auto_scan_rules
            if auto_scan_rules:
                for rule in auto_scan_rules:
                    pattern = rule.replace("*", ".*")
                    if re.match(pattern, repo):
                        should_scan = True
                        break
            
            if not should_scan:
                continue
            
            tags = fetch_repository_tags(registry["api"], repo, auth)
            for tag in tags[:scan_latest_only]:
                scanner.scan_image(registry_url, repo, tag)
                scanned += 1
        
        return jsonify({"success": True, "scanned": scanned})
    except Exception as e:
        logger.error(f"Scan all error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/vulnerabilities/<registry_name>")
def api_vulnerabilities(registry_name):
    """Get vulnerability scan results"""
    return jsonify({"results": {}, "error": "Scan results storage not implemented yet"})

@api_bp.route("/analytics/<registry_name>")
def api_analytics(registry_name):
    """Get analytics for registry"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return jsonify({"error": "Registry not found"}), 404
    
    auth = get_auth(registry)
    repos, error = fetch_repositories(registry["api"], auth)
    
    if error:
        return jsonify({"error": error}), 500
    
    analytics = []
    total_tags = 0
    total_size = 0
    
    for repo in repos:
        tags = fetch_repository_tags(registry["api"], repo, auth)
        repo_size = 0
        
        for tag in tags:
            details = fetch_tag_details(registry["api"], repo, tag, auth)
            repo_size += details.get("size", 0)
        
        total_tags += len(tags)
        total_size += repo_size
        
        analytics.append({
            "repo": repo,
            "tags": len(tags),
            "size": repo_size,
            "avgSize": repo_size // len(tags) if len(tags) > 0 else 0
        })
    
    return jsonify({
        "analytics": analytics,
        "totalRepos": len(repos),
        "totalTags": total_tags,
        "totalSize": total_size,
        "avgSize": total_size // total_tags if total_tags > 0 else 0
    })
