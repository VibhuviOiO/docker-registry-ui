import os
import logging
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import Config
from .data_store import (
    get_registries, get_registry_by_name, cache_repositories, get_cached_repositories,
    create_scan_job, get_scan_job, update_scan_job, store_scan_results
)
from .registry import (
    format_size, fetch_repositories, fetch_repository_tags,
    fetch_tag_details, delete_tag, delete_repository, get_auth
)

logger = logging.getLogger(__name__)

main_router = APIRouter()
api_router = APIRouter()

# Configure Jinja2 templates and provide a Flask-compatible url_for helper for
# the existing templates (they use url_for('static', filename='...')).
templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)


def _url_for(name, **kwargs):
    if name == "static":
        return f"/static/{kwargs['filename']}"
    return f"/{name}"


templates.env.globals["url_for"] = _url_for

# Limit concurrent scans so heavy operations don't starve the registry or workers.
# Additional scan requests are queued and executed when a slot frees up.
SCAN_WORKERS = int(getattr(Config, 'SCAN_WORKERS', 2))
scan_executor = ThreadPoolExecutor(max_workers=SCAN_WORKERS, thread_name_prefix="trivy-scan-")

# Retry configuration for scans that fail due to transient registry contention
# (e.g. a concurrent docker push/pull is modifying the image).
SCAN_RETRIES = int(getattr(Config, 'SCAN_RETRIES', 3))
SCAN_RETRY_DELAY = int(getattr(Config, 'SCAN_RETRY_DELAY', 5))


@main_router.get("/", response_class=HTMLResponse)
def index(request: Request):
    registries = get_registries()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "registries": registries,
            "read_only": Config.READ_ONLY,
            "version": request.app.state.VERSION,
            "built_by": Config.BUILT_BY,
        },
    )


@api_router.get("/registries")
def api_registries():
    """Get list of configured registries"""
    registries = get_registries()
    # Don't expose credentials
    safe_registries = []
    for reg in registries:
        # Handle both string and dictionary formats
        if isinstance(reg, str):
            safe_registries.append({
                "name": reg,
                "api": "http://registry:5000",  # Default for development
                "url": "registry:5000",
                "isAuthEnabled": False,
                "default": True,
                "bulkOperationsEnabled": False,
                "vulnerabilityScan": {
                    "enabled": False,
                    "scanner": "trivy",
                    "scannerUrl": ""
                }
            })
        else:
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
    return {"registries": safe_registries}


@api_router.get("/repositories/{registry_name}")
def api_repositories(registry_name: str):
    """Get repositories for a specific registry"""
    logger.info(f"Fetching repositories for registry: {registry_name}")
    registry = get_registry_by_name(registry_name)
    if not registry:
        logger.warning(f"Registry not found: {registry_name}")
        return JSONResponse({"error": "Registry not found"}, status_code=404)

    # Always fetch fresh data (no caching)
    auth = get_auth(registry)
    repos, error = fetch_repositories(registry["api"], auth)

    if error:
        logger.error(f"Error fetching repositories from {registry_name}: {error}")
        return JSONResponse({"error": error}, status_code=500)

    logger.info(f"Found {len(repos)} repositories in {registry_name}")
    return {"repositories": repos}


@api_router.get("/tags/{registry_name}/{repo:path}")
def api_tags(registry_name: str, repo: str):
    """Get tags for a repository"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"error": "Registry not found"}, status_code=404)

    auth = get_auth(registry)
    tags = fetch_repository_tags(registry["api"], repo, auth)

    return {"tags": tags}


@api_router.get("/tag-details/{registry_name}/{repo:path}/{tag}")
def api_tag_details(registry_name: str, repo: str, tag: str):
    """Get details for a specific tag"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"error": "Registry not found"}, status_code=404)

    auth = get_auth(registry)
    details = fetch_tag_details(registry["api"], repo, tag, auth)

    return details


@api_router.delete("/delete/tag/{registry_name}/{repo:path}/{tag}")
def api_delete_tag(registry_name: str, repo: str, tag: str):
    """Delete a tag"""
    if Config.READ_ONLY:
        logger.warning(f"Delete attempt in read-only mode: {repo}:{tag}")
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"success": False, "error": "Registry not found"}, status_code=404)

    logger.info(f"Deleting tag {repo}:{tag} from {registry_name}")
    auth = get_auth(registry)
    success, error = delete_tag(registry["api"], repo, tag, auth)

    if success:
        logger.info(f"Successfully deleted {repo}:{tag}")
        return {"success": True}
    else:
        logger.error(f"Failed to delete {repo}:{tag}: {error}")
        return JSONResponse({"success": False, "error": error}, status_code=500)


@api_router.delete("/delete/repo/{registry_name}/{repo:path}")
def api_delete_repo(registry_name: str, repo: str):
    """Delete entire repository"""
    if Config.READ_ONLY:
        logger.warning(f"Repository delete attempt in read-only mode: {repo}")
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"success": False, "error": "Registry not found"}, status_code=404)

    logger.info(f"Deleting repository {repo} from {registry_name}")
    auth = get_auth(registry)
    success, error, deleted, total = delete_repository(registry["api"], repo, auth)

    if success:
        logger.info(f"Successfully deleted {repo}: {deleted}/{total} tags")
        return {"success": True, "deleted": deleted, "total": total}
    else:
        logger.error(f"Failed to delete {repo}: {error}")
        return JSONResponse({"success": False, "error": error}, status_code=500)


@api_router.post("/bulk-operation")
def api_bulk_operation(data: dict = Body(...)):
    """Execute bulk cleanup operation"""
    if Config.READ_ONLY:
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry_name = data.get("registry")

    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"success": False, "error": "Registry not found"}, status_code=404)

    registry_name = data.get("registry")
    repo_pattern = data.get("repoPattern", "*")
    older_than_days = data.get("olderThanDays")
    keep_min = data.get("keepMin", 0)
    tag_pattern = data.get("tagPattern")
    dry_run = data.get("dryRun", True)

    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"success": False, "error": "Registry not found"}, status_code=404)

    auth = get_auth(registry)
    repos, error = fetch_repositories(registry["api"], auth)

    if error:
        return JSONResponse({"success": False, "error": error}, status_code=500)

    import re

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

    return {"success": True, "results": results, "dryRun": dry_run}


@api_router.post("/registry/bulk-operations")
def api_toggle_bulk_operations(data: dict = Body(...)):
    """Toggle bulk operations for a registry"""
    if Config.READ_ONLY:
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry_name = data.get("registry")
    enabled = data.get("enabled", False)

    from .data_store import update_registry_bulk_ops
    success = update_registry_bulk_ops(registry_name, enabled)

    if success:
        return {"success": True}
    else:
        return JSONResponse({"success": False, "error": "Failed to update registry"}, status_code=500)


@api_router.post("/registry/config")
def api_update_registry_config(data: dict = Body(...)):
    """Update registry configuration"""
    if Config.READ_ONLY:
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry_name = data.get("registry")

    from .data_store import update_registry_config
    success = update_registry_config(registry_name, data)

    if success:
        if Config.USE_ENV_CONFIG:
            return {"success": True, "message": "Configuration updated in memory. Using environment variable - changes will be lost on restart. Update REGISTRIES env var to persist."}
        else:
            return {"success": True, "message": "Configuration saved to file and persisted."}
    else:
        return JSONResponse({"success": False, "error": "Failed to update registry"}, status_code=500)


def _run_scan_job(job_id, registry, repo, tag):
    """Background scan worker with retry for transient registry contention."""
    update_scan_job(job_id, status="in_progress")
    try:
        from .scanners.trivy import TrivyScanner

        scanner = TrivyScanner("builtin", 300)
        registry_url = registry["api"]
        result = None
        last_error = None

        for attempt in range(1, SCAN_RETRIES + 1):
            logger.info(f"[Scan {job_id}] Scanning {registry_url}/{repo}:{tag} (attempt {attempt}/{SCAN_RETRIES})")
            result = scanner.scan_image(registry_url, repo, tag)

            if isinstance(result, dict) and result.get("error"):
                last_error = result["error"]
                logger.warning(f"[Scan {job_id}] Attempt {attempt} failed: {last_error}")
                if attempt < SCAN_RETRIES:
                    time.sleep(SCAN_RETRY_DELAY * attempt)
                    continue
            else:
                break

        if isinstance(result, dict) and result.get("error"):
            logger.error(f"[Scan {job_id}] Failed after {SCAN_RETRIES} attempts: {result['error']}")
            update_scan_job(job_id, status="failed", error=result["error"])
        else:
            logger.info(f"[Scan {job_id}] Completed")
            store_scan_results(registry["name"], repo, tag, result)
            update_scan_job(job_id, status="completed", result=result)
    except Exception as e:
        logger.error(f"[Scan {job_id}] Error: {str(e)}")
        update_scan_job(job_id, status="failed", error=str(e))


@api_router.get("/scan/{registry_name}/{repo:path}/{tag}")
def api_scan_image(registry_name: str, repo: str, tag: str, background_tasks: BackgroundTasks):
    """Queue an async vulnerability scan"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"error": "Registry not found"}, status_code=404)

    job_id = create_scan_job(registry_name, repo, tag)
    background_tasks.add_task(_run_scan_job, job_id, registry, repo, tag)

    logger.info(f"Queued scan job {job_id} for {registry_name}/{repo}:{tag}")
    return {"scanId": job_id, "status": "queued"}


@api_router.get("/scan-status/{scan_id}")
def api_scan_status(scan_id: str):
    """Get status of an async scan job"""
    job = get_scan_job(scan_id)
    if not job:
        return JSONResponse({"error": "Scan job not found"}, status_code=404)

    return {
        "scanId": job["id"],
        "status": job["status"],
        "registry": job["registry_name"],
        "repo": job["repo"],
        "tag": job["tag"],
        "result": job["result"],
        "error": job["error"]
    }


@api_router.post("/test-registry")
def api_test_registry(data: dict = Body(...)):
    """Test registry connection"""
    api = data.get("api")

    if not api:
        return JSONResponse({"success": False, "error": "API URL required"}, status_code=400)

    try:
        auth = None
        if data.get("isAuthEnabled"):
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(data.get("user"), data.get("password"))

        response = requests.get(f"{api}/v2/_catalog", auth=auth, timeout=5)

        if response.status_code == 200:
            return {"success": True}
        else:
            return JSONResponse({"success": False, "error": f"HTTP {response.status_code}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@api_router.post("/registry/create")
def api_create_registry(data: dict = Body(...)):
    """Create new registry"""
    if Config.READ_ONLY:
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry = data

    if not registry.get("name") or not registry.get("api"):
        return JSONResponse({"success": False, "error": "Name and API URL required"}, status_code=400)

    # If this is the first registry or marked as default, unset other defaults
    if registry.get("default") or len(Config.REGISTRIES) == 0:
        for reg in Config.REGISTRIES:
            reg["default"] = False
        registry["default"] = True

    Config.REGISTRIES.append(registry)

    if Config.save_registries():
        return {"success": True, "message": "Registry created and saved to file"}
    else:
        return {"success": True, "message": "Registry created (in-memory only - using env config)"}


@api_router.post("/test-scanner")
def api_test_scanner(data: dict = Body(...)):
    """Test scanner connection"""
    url = data.get("url")
    scanner_type = data.get("scanner", "trivy")

    if not url:
        return JSONResponse({"success": False, "error": "Scanner URL required"}, status_code=400)

    try:
        if scanner_type == "trivy":
            response = requests.get(f"{url}/healthz", timeout=5)
        else:
            response = requests.get(f"{url}/health", timeout=5)

        if response.status_code == 200:
            return {"success": True}
        else:
            return JSONResponse({"success": False, "error": f"HTTP {response.status_code}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@api_router.post("/registry/vuln-scan")
def api_update_vuln_scan(data: dict = Body(...)):
    """Update vulnerability scanning configuration"""
    if Config.READ_ONLY:
        return JSONResponse({"success": False, "error": "Read-only mode"}, status_code=403)

    registry_name = data.get("registry")
    vuln_config = data.get("vulnerabilityScan")

    from .data_store import update_registry_config
    success = update_registry_config(registry_name, {"vulnerabilityScan": vuln_config})

    if success:
        return {"success": True}
    else:
        return JSONResponse({"success": False, "error": "Failed to update registry"}, status_code=500)


@api_router.post("/scan-all/{registry_name}")
def api_scan_all(registry_name: str):
    """Scan all images in registry based on auto-scan rules"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"success": False, "error": "Registry not found"}, status_code=404)

    vuln_scan = registry.get("vulnerabilityScan", {})
    if not vuln_scan.get("enabled"):
        return JSONResponse({"success": False, "error": "Vulnerability scanning not enabled"}, status_code=400)

    try:
        from .scanners.factory import get_scanner
        from .data_store import store_scan_results
        import re

        scanner = get_scanner(vuln_scan.get("scanner", "trivy"), vuln_scan.get("scannerUrl"))
        auth = get_auth(registry)
        repos, error = fetch_repositories(registry["api"], auth)

        if error:
            return JSONResponse({"success": False, "error": error}, status_code=500)

        auto_scan_rules = vuln_scan.get("autoScanRules", [])
        scan_latest_only = vuln_scan.get("scanLatestOnly", 1)
        registry_url = registry["api"]
        scanned = 0

        logger.info(f"Starting scan-all for {registry_name}, {len(repos)} repos")

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
                logger.info(f"Scanning {repo}:{tag}")
                result = scanner.scan_image(registry_url, repo, tag)
                logger.debug(f"Scan result for {repo}:{tag}: {result}")
                store_scan_results(registry_name, repo, tag, result)
                scanned += 1

        logger.info(f"Scan-all completed: {scanned} images scanned")
        return {"success": True, "scanned": scanned}
    except Exception as e:
        logger.error(f"Scan all error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@api_router.get("/vulnerabilities/{registry_name}")
def api_vulnerabilities(registry_name: str):
    """Get vulnerability scan results"""
    from .data_store import get_scan_results
    results = get_scan_results(registry_name)
    return {"results": results}


@api_router.get("/analytics/{registry_name}")
def api_analytics(registry_name: str):
    """Get analytics for registry"""
    registry = get_registry_by_name(registry_name)
    if not registry:
        return JSONResponse({"error": "Registry not found"}, status_code=404)

    auth = get_auth(registry)
    repos, error = fetch_repositories(registry["api"], auth)

    if error:
        return JSONResponse({"error": error}, status_code=500)

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

    return {
        "analytics": analytics,
        "totalRepos": len(repos),
        "totalTags": total_tags,
        "totalSize": total_size,
        "avgSize": total_size // total_tags if total_tags > 0 else 0
    }
