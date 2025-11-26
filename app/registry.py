import requests
from requests.auth import HTTPBasicAuth
from .config import Config

def get_auth(registry):
    """Get authentication for registry"""
    if not registry.get("isAuthEnabled"):
        return None
    
    if registry.get("apiToken"):
        return {"Authorization": f"Bearer {registry['apiToken']}"}
    elif registry.get("user") and registry.get("password"):
        return HTTPBasicAuth(registry["user"], registry["password"])
    
    return None

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

def fetch_repositories(registry_api, auth=None):
    """Fetch repository list only (lightweight)"""
    try:
        headers = auth if isinstance(auth, dict) else {}
        auth_obj = auth if isinstance(auth, HTTPBasicAuth) else None
        
        r = requests.get(
            f"{registry_api}/v2/_catalog",
            headers=headers,
            auth=auth_obj,
            timeout=Config.TIMEOUT
        )
        
        if r.status_code == 200:
            repos = r.json().get("repositories", [])
            return sorted(repos), None
        else:
            return [], f"HTTP {r.status_code}"
    except Exception as e:
        return [], str(e)

def fetch_repository_tags(registry_api, repo, auth=None):
    """Fetch tags for a specific repository (on-demand)"""
    try:
        headers = auth if isinstance(auth, dict) else {}
        auth_obj = auth if isinstance(auth, HTTPBasicAuth) else None
        
        r = requests.get(
            f"{registry_api}/v2/{repo}/tags/list",
            headers=headers,
            auth=auth_obj,
            timeout=Config.TIMEOUT
        )
        
        if r.status_code != 200:
            return []
        
        tags = r.json().get("tags", []) or []
        return tags
    except:
        return []

def fetch_tag_details(registry_api, repo, tag, auth=None):
    """Fetch details for a specific tag (on-demand)"""
    try:
        auth_obj = auth if isinstance(auth, HTTPBasicAuth) else None
        
        # Try OCI index first (multi-platform)
        headers = {"Accept": "application/vnd.oci.image.index.v1+json"}
        if isinstance(auth, dict):
            headers.update(auth)
        
        r = requests.get(
            f"{registry_api}/v2/{repo}/manifests/{tag}",
            headers=headers,
            auth=auth_obj,
            timeout=Config.TIMEOUT
        )
        
        if r.status_code == 200:
            index = r.json()
            
            # If it's an OCI index, get the first platform manifest
            if "manifests" in index:
                for manifest_ref in index["manifests"]:
                    # Skip attestation manifests
                    if manifest_ref.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest":
                        continue
                    
                    # Get the actual manifest
                    manifest_digest = manifest_ref["digest"]
                    headers2 = {"Accept": "application/vnd.oci.image.manifest.v1+json"}
                    if isinstance(auth, dict):
                        headers2.update(auth)
                    
                    r2 = requests.get(
                        f"{registry_api}/v2/{repo}/manifests/{manifest_digest}",
                        headers=headers2,
                        auth=auth_obj,
                        timeout=Config.TIMEOUT
                    )
                    
                    if r2.status_code == 200:
                        manifest = r2.json()
                        size = sum(layer.get("size", 0) for layer in manifest.get("layers", []))
                        size += manifest.get("config", {}).get("size", 0)
                        
                        # Get created timestamp from config
                        created = None
                        config_digest = manifest.get("config", {}).get("digest")
                        if config_digest:
                            config_r = requests.get(
                                f"{registry_api}/v2/{repo}/blobs/{config_digest}",
                                headers=headers2,
                                auth=auth_obj,
                                timeout=Config.TIMEOUT
                            )
                            if config_r.status_code == 200:
                                config = config_r.json()
                                created = config.get("created")
                        
                        return {"tag": tag, "size": size, "digest": manifest_digest, "created": created, "manifest": manifest, "config": config if config_digest else {}}
        
        # Fallback to Docker v2 manifest
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        if isinstance(auth, dict):
            headers.update(auth)
        
        r = requests.get(
            f"{registry_api}/v2/{repo}/manifests/{tag}",
            headers=headers,
            auth=auth_obj,
            timeout=Config.TIMEOUT
        )
        
        if r.status_code == 200:
            manifest = r.json()
            digest = r.headers.get("Docker-Content-Digest", "")
            size = sum(layer.get("size", 0) for layer in manifest.get("layers", []))
            size += manifest.get("config", {}).get("size", 0)
            
            # Get created timestamp from config
            created = None
            config_digest = manifest.get("config", {}).get("digest")
            if config_digest:
                config_r = requests.get(
                    f"{registry_api}/v2/{repo}/blobs/{config_digest}",
                    headers=headers,
                    auth=auth_obj,
                    timeout=Config.TIMEOUT
                )
                if config_r.status_code == 200:
                    config = config_r.json()
                    created = config.get("created")
            
            return {"tag": tag, "size": size, "digest": digest, "created": created, "manifest": manifest, "config": config if config_digest else {}}
        
        return {"tag": tag, "size": 0, "digest": "", "created": None}
    except:
        return {"tag": tag, "size": 0, "digest": "", "created": None}


def delete_tag(registry_api, repo, tag, auth=None):
    """Delete a specific tag"""
    try:
        auth_obj = auth if isinstance(auth, HTTPBasicAuth) else None
        digest = None
        
        # Try multiple accept headers to get digest
        accept_headers = [
            "application/vnd.oci.image.index.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.docker.distribution.manifest.v1+json"
        ]
        
        for accept in accept_headers:
            headers = {"Accept": accept}
            if isinstance(auth, dict):
                headers.update(auth)
            
            manifest_r = requests.get(
                f"{registry_api}/v2/{repo}/manifests/{tag}",
                headers=headers,
                auth=auth_obj,
                timeout=Config.TIMEOUT
            )
            
            if manifest_r.status_code == 200:
                digest = manifest_r.headers.get("Docker-Content-Digest")
                if digest:
                    break
        
        if not digest:
            return False, "No digest found"
        
        # Delete by digest
        delete_headers = {}
        if isinstance(auth, dict):
            delete_headers.update(auth)
        
        delete_r = requests.delete(
            f"{registry_api}/v2/{repo}/manifests/{digest}",
            headers=delete_headers,
            auth=auth_obj,
            timeout=Config.TIMEOUT
        )
        
        if delete_r.status_code in [200, 202]:
            return True, None
        else:
            return False, f"HTTP {delete_r.status_code}"
    except Exception as e:
        return False, str(e)

def delete_repository(registry_api, repo, auth=None):
    """Delete entire repository"""
    try:
        tags = fetch_repository_tags(registry_api, repo, auth)
        deleted = 0
        
        for tag in tags:
            success, _ = delete_tag(registry_api, repo, tag, auth)
            if success:
                deleted += 1
        
        return True, None, deleted, len(tags)
    except Exception as e:
        return False, str(e), 0, 0
