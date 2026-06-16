import os
import requests
import logging
from .base import VulnerabilityScanner

logger = logging.getLogger(__name__)

# Trivy's filesystem cache does not support concurrent scans from multiple
# processes. Use an advisory file lock so only one Trivy invocation runs at a
# time across all uvicorn workers.
TRIVY_LOCK_FILE = os.path.join(os.getenv("DATA_DIR", "/app/data"), ".trivy_scan.lock")

# fcntl is only available on Unix; on Windows the lock helpers become no-ops.
try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


def _acquire_trivy_lock():
    if not _HAS_FCNTL:
        return None
    os.makedirs(os.path.dirname(TRIVY_LOCK_FILE), exist_ok=True)
    fd = os.open(TRIVY_LOCK_FILE, os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_trivy_lock(fd):
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class TrivyScanner(VulnerabilityScanner):
    """Trivy vulnerability scanner integration"""
    
    def scan_image(self, registry_url, repository, tag):
        """Scan image using Trivy CLI"""
        try:
            import subprocess
            import json
            
            registry_host = registry_url.replace('http://', '').replace('https://', '')
            image_ref = f"{registry_host}/{repository}:{tag}"

            # Detect remote Trivy server mode. The scanner_url comes from the
            # registry's vulnerabilityScan.scannerUrl config. "builtin" or empty
            # means run Trivy locally.
            remote_server = None
            if self.scanner_url and self.scanner_url not in ("builtin", ""):
                remote_server = self.scanner_url

            logger.debug(f"[TRIVY] Scanning image: {image_ref} (server={remote_server or 'local'})")

            # Run trivy client to scan the image.
            # --scanners vuln avoids the slower secret scanner and its stderr noise.
            # --quiet suppresses progress tables.
            cmd = [
                "trivy", "image",
                "--scanners", "vuln",
                "--format", "json",
                "--insecure",
                "--timeout", "5m",
                "--quiet",
            ]

            if remote_server:
                cmd.extend(["--server", remote_server])

            cmd.append(image_ref)

            # Local Trivy CLI shares a filesystem cache and cannot run concurrently.
            # A remote Trivy server handles its own cache locking, so skip the lock.
            if remote_server:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            else:
                lock_fd = _acquire_trivy_lock()
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                finally:
                    _release_trivy_lock(lock_fd)

            logger.debug(f"[TRIVY] Exit code: {result.returncode}")

            # Some Trivy versions emit results to stdout even when the exit code
            # is non-zero (e.g. policy checks). Try to parse stdout first.
            if result.stdout:
                try:
                    report = json.loads(result.stdout)
                    if report.get("Results") is not None:
                        return self._parse_trivy_report(report)
                except json.JSONDecodeError:
                    pass

            if result.returncode == 0:
                if result.stdout:
                    try:
                        report = json.loads(result.stdout)
                        return self._parse_trivy_report(report)
                    except json.JSONDecodeError:
                        pass
                # Empty stdout with exit 0 means no vulnerabilities
                return self._parse_trivy_report({})

            error_msg = result.stderr.strip() if result.stderr else "No output"
            # Log the full stderr so the real failure is visible; truncate only
            # the string returned to the API caller to keep payloads small.
            logger.error(f"[TRIVY] Error (exit {result.returncode}): {error_msg}")
            public_msg = error_msg.split('\n')[-1].strip() if error_msg else "No output"
            if len(public_msg) > 200:
                public_msg = public_msg[:200] + "..."
            return {"error": f"Scan failed: {public_msg}"}
        except subprocess.TimeoutExpired:
            return {"error": "Scan timeout after 5 minutes"}
        except Exception as e:
            logger.error(f"[TRIVY] Exception: {str(e)}")
            return {"error": str(e)}
    
    def _parse_trivy_report(self, report):
        """Parse Trivy JSON report"""
        vulnerabilities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        details = []
        layers = []
        
        for result in report.get("Results", []):
            target = result.get("Target", "")
            layer_vulns = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            layer_details = []
            
            for vuln in result.get("Vulnerabilities", []):
                severity = vuln.get("Severity", "UNKNOWN")
                vulnerabilities[severity] = vulnerabilities.get(severity, 0) + 1
                layer_vulns[severity] = layer_vulns.get(severity, 0) + 1
                
                layer_info = vuln.get("Layer", {})
                vuln_detail = {
                    "id": vuln.get("VulnerabilityID"),
                    "severity": severity,
                    "package": vuln.get("PkgName"),
                    "version": vuln.get("InstalledVersion"),
                    "fixedVersion": vuln.get("FixedVersion"),
                    "title": vuln.get("Title"),
                    "layer": layer_info.get("Digest", "")[:12] if layer_info else ""
                }
                details.append(vuln_detail)
                layer_details.append(vuln_detail)
            
            if layer_details:
                layers.append({
                    "target": target,
                    "digest": target.split(":")[-1][:12] if ":" in target else "",
                    "summary": layer_vulns,
                    "total": sum(layer_vulns.values()),
                    "vulnerabilities": layer_details
                })
        
        return {
            "scanner": "trivy",
            "summary": vulnerabilities,
            "total": sum(vulnerabilities.values()),
            "details": details,
            "layers": layers
        }
    
    def get_report(self, scan_id):
        return {"error": "Trivy doesn't support report retrieval"}
    
    def health_check(self):
        # Local builtin mode: just verify the trivy binary is callable.
        if not self.scanner_url or self.scanner_url == "builtin":
            try:
                import subprocess
                subprocess.run(["trivy", "--version"], capture_output=True, check=True, timeout=5)
                return True
            except Exception:
                return False

        # Remote server mode: hit the Trivy server /healthz endpoint.
        try:
            response = requests.get(f"{self.scanner_url}/healthz", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
