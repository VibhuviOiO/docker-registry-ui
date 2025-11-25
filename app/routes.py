from flask import Blueprint, render_template, jsonify, request
from .config import Config
from .data_store import get_registries, get_registry_by_name, cache_repositories, get_cached_repositories
from .registry import (
    format_size, fetch_repositories, fetch_repository_tags,
    fetch_tag_details, delete_tag, delete_repository, get_auth
)
import logging

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
        safe_registries.append({
            "name": reg["name"],
            "api": reg["api"],
            "isAuthEnabled": reg.get("isAuthEnabled", False)
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
