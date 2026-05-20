from .config import Config
import json
import os
import glob
import sqlite3
from datetime import datetime as dt, timedelta

# Simple in-memory cache for repositories (no background updates)
registry_cache = {}
scan_results = {}


def _ensure_db():
    db_path = Config.DB_PATH
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_results (
                registry_name TEXT NOT NULL,
                repo TEXT NOT NULL,
                tag TEXT NOT NULL,
                scanned_at TEXT,
                cache_expires_at TEXT,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (registry_name, repo, tag)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS massive_scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registry_name TEXT NOT NULL,
                run_at TEXT NOT NULL,
                source TEXT,
                timezone TEXT,
                dry_run INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                total_images INTEGER DEFAULT 0,
                total_tags INTEGER DEFAULT 0,
                total_scans INTEGER DEFAULT 0,
                skipped INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                critical INTEGER DEFAULT 0,
                high INTEGER DEFAULT 0,
                medium INTEGER DEFAULT 0,
                low INTEGER DEFAULT 0,
                summary_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_massive_scan_runs_registry_runat
            ON massive_scan_runs (registry_name, run_at DESC)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _upsert_scan_result_sqlite(registry_name, repo, tag, normalized):
    _ensure_db()
    conn = sqlite3.connect(Config.DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO scan_results (
                registry_name, repo, tag, scanned_at, cache_expires_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(registry_name, repo, tag) DO UPDATE SET
                scanned_at=excluded.scanned_at,
                cache_expires_at=excluded.cache_expires_at,
                payload_json=excluded.payload_json
            """,
            (
                registry_name,
                repo,
                tag,
                normalized.get("scannedAt"),
                normalized.get("cacheExpiresAt"),
                json.dumps(normalized),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _load_scan_results_sqlite(registry_name):
    _ensure_db()
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT repo, tag, payload_json, cache_expires_at
            FROM scan_results
            WHERE registry_name = ?
            """,
            (registry_name,),
        ).fetchall()
    finally:
        conn.close()

    loaded = {}
    for row in rows:
        try:
            result = json.loads(row["payload_json"])
            key = f"{row['repo']}:{row['tag']}"
            loaded[key] = result
        except Exception:
            continue
    return loaded


def _load_scan_results_files(registry_name):
    loaded = {}
    data_dir = (
        os.path.dirname(Config.CONFIG_FILE) if Config.CONFIG_FILE else "/app/data"
    )
    scan_files = glob.glob(os.path.join(data_dir, "*_*.json"))

    for scan_file in scan_files:
        filename = os.path.basename(scan_file)
        if filename.startswith("scan_results_") or filename == "registries.config.json":
            continue
        try:
            with open(scan_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            # Filter by registry_name to ensure we only load results for the requested registry
            # For backward compatibility: if registry field is missing, include the result
            # (legacy files don't have the registry field)
            result_registry = result.get("registry")
            if result_registry and result_registry != registry_name:
                continue
            repo = result.get("repo")
            tag = result.get("tag")
            if repo and tag:
                key = f"{repo}:{tag}"
                loaded[key] = result
        except Exception:
            continue
    return loaded


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
                    "bulkOperationsEnabled": False,
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
                reg["vulnerabilityScan"]["enabled"] = config["vulnerabilityScan"].get(
                    "enabled", False
                )
                reg["vulnerabilityScan"]["scanner"] = config["vulnerabilityScan"].get(
                    "scanner", "trivy"
                )
                reg["vulnerabilityScan"]["scannerUrl"] = config[
                    "vulnerabilityScan"
                ].get("scannerUrl", "")
                reg["vulnerabilityScan"]["autoScan"] = config["vulnerabilityScan"].get(
                    "autoScan", False
                )
            # Handle auth configuration
            if "auth" in config:
                reg["auth"] = config["auth"]
            elif (
                "isAuthEnabled" in config
                or "user" in config
                or "password" in config
                or "apiToken" in config
            ):
                # Convert old format to new format
                if config.get("isAuthEnabled"):
                    if config.get("apiToken"):
                        reg["auth"] = {
                            "type": "bearer",
                            "token": config.get("apiToken", ""),
                        }
                    else:
                        reg["auth"] = {
                            "type": "basic",
                            "username": config.get("user", ""),
                            "password": config.get("password", ""),
                        }
                else:
                    # Auth disabled - remove auth if present
                    reg.pop("auth", None)
                # Remove old fields
                reg.pop("isAuthEnabled", None)
                reg.pop("user", None)
                reg.pop("password", None)
                reg.pop("apiToken", None)
            Config.save_registries()
            return True
    return False


def store_scan_results(registry_name, repo, tag, result, ttl_hours=24):
    """Store vulnerability scan results"""
    from datetime import datetime

    # --- Unified scan result schema ---
    import copy

    schema_version = 1
    now = datetime.now().isoformat()
    # Compose cache key: registry/repo/tag@digest (digest may be missing at this stage)
    digest = result.get("digest") or result.get("imageDigest") or None
    cache_key = f"{repo}:{tag}"
    # Compose normalized result
    normalized = {
        "schemaVersion": schema_version,
        "scanner": result.get("scanner", "unknown"),
        "scannedAt": now,
        "registry": registry_name,
        "repo": repo,
        "tag": tag,
        "digest": digest,
        "summary": result.get("summary", {}),
        "total": result.get("total", 0),
        "details": result.get("details", []),
        "layers": result.get("layers", []),
        "baseImageExposure": result.get("baseImageExposure", None),
        "raw": copy.deepcopy(result),
    }
    # Store in memory with TTL
    if registry_name not in scan_results:
        scan_results[registry_name] = {}
    normalized["cacheTTL"] = ttl_hours
    normalized["cacheExpiresAt"] = None
    if ttl_hours > 0:
        expires = dt.fromisoformat(now) + timedelta(hours=ttl_hours)
        normalized["cacheExpiresAt"] = expires.isoformat()
    scan_results[registry_name][cache_key] = normalized

    # Persist to SQLite (primary persistence)
    try:
        _upsert_scan_result_sqlite(registry_name, repo, tag, normalized)
    except Exception as e:
        print(f"Failed to upsert scan result into SQLite: {e}")

    # Persist to per-image file only (legacy, for now)
    data_dir = (
        os.path.dirname(Config.CONFIG_FILE) if Config.CONFIG_FILE else "/app/data"
    )
    os.makedirs(data_dir, exist_ok=True)
    image_file = os.path.join(data_dir, f"{repo.replace('/', '_')}_{tag}.json")
    try:
        with open(image_file, "w") as f:
            json.dump(normalized, f, indent=2)
        print(f"Saved scan to: {image_file}")
    except Exception as e:
        print(f"Failed to save scan to {image_file}: {e}")


def get_scan_results(registry_name, force_refresh=False, ttl_hours=24):
    """Get all scan results for a registry from SQLite, with file fallback."""

    if force_refresh or registry_name not in scan_results:
        scan_results[registry_name] = {}

    # Load from SQLite first
    try:
        sqlite_results = _load_scan_results_sqlite(registry_name)
        scan_results[registry_name].update(sqlite_results)
    except Exception as e:
        print(f"Failed to load from SQLite for {registry_name}: {e}")

    # Fallback to file-based results for backward compatibility
    file_results = _load_scan_results_files(registry_name)
    for key, value in file_results.items():
        if key not in scan_results[registry_name]:
            scan_results[registry_name][key] = value

    print(f"Loaded {len(scan_results[registry_name])} scan results for {registry_name}")
    # Invalidate cache if expired or digest changed (soft/hard)
    results = scan_results[registry_name]
    valid_results = {}
    for key, res in results.items():
        expires = res.get("cacheExpiresAt")
        if force_refresh:
            continue
        if expires:
            try:
                if dt.fromisoformat(expires) < dt.now():
                    continue  # TTL expired
            except Exception:
                pass
        # (Digest check: handled at scan time)
        valid_results[key] = res
    return valid_results


def store_massive_scan_run(registry_name, run_summary):
    """Persist one massive scan run summary for historical trends."""
    _ensure_db()
    now = dt.now().isoformat()
    summary = run_summary or {}

    conn = sqlite3.connect(Config.DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO massive_scan_runs (
                registry_name, run_at, source, timezone,
                dry_run, success, total_images, total_tags, total_scans,
                skipped, errors, critical, high, medium, low, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                registry_name,
                summary.get("runAt") or now,
                summary.get("source", "manual"),
                summary.get("timezone"),
                1 if summary.get("dryRun", False) else 0,
                1 if summary.get("success", True) else 0,
                int(summary.get("totalImages", 0) or 0),
                int(summary.get("totalTags", 0) or 0),
                int(summary.get("totalScans", 0) or 0),
                int(summary.get("skipped", 0) or 0),
                int(summary.get("errors", 0) or 0),
                int(summary.get("critical", 0) or 0),
                int(summary.get("high", 0) or 0),
                int(summary.get("medium", 0) or 0),
                int(summary.get("low", 0) or 0),
                json.dumps(summary),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_massive_scan_run_history(registry_name, limit=30):
    """Return latest massive scan runs for one registry."""
    _ensure_db()
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT run_at, source, timezone, dry_run, success,
                   total_images, total_tags, total_scans,
                   skipped, errors, critical, high, medium, low,
                   summary_json
            FROM massive_scan_runs
            WHERE registry_name = ?
            ORDER BY run_at DESC, id DESC
            LIMIT ?
            """,
            (registry_name, int(limit)),
        ).fetchall()
    finally:
        conn.close()

    history = []
    for row in rows:
        try:
            payload = json.loads(row["summary_json"]) if row["summary_json"] else {}
        except Exception:
            payload = {}
        history.append(
            {
                "runAt": row["run_at"],
                "source": row["source"],
                "timezone": row["timezone"],
                "dryRun": bool(row["dry_run"]),
                "success": bool(row["success"]),
                "totalImages": row["total_images"],
                "totalTags": row["total_tags"],
                "totalScans": row["total_scans"],
                "skipped": row["skipped"],
                "errors": row["errors"],
                "critical": row["critical"],
                "high": row["high"],
                "medium": row["medium"],
                "low": row["low"],
                "summary": payload,
            }
        )
    return history
