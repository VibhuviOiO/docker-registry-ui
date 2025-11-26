import requests
from .base import VulnerabilityScanner

class TrivyScanner(VulnerabilityScanner):
    """Trivy vulnerability scanner integration"""
    
    def scan_image(self, registry_url, repository, tag):
        """Scan image using Trivy CLI"""
        try:
            import subprocess
            import json
            
            registry_host = registry_url.replace('http://', '').replace('https://', '')
            image_ref = f"{registry_host}/{repository}:{tag}"
            
            print(f"[TRIVY] Scanning image: {image_ref}")
            
            # Run trivy client to scan the image
            cmd = [
                "trivy", "image",
                "--format", "json",
                "--insecure",
                "--timeout", "5m",
                image_ref
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            print(f"[TRIVY] Exit code: {result.returncode}")
            
            if result.returncode == 0 and result.stdout:
                report = json.loads(result.stdout)
                return self._parse_trivy_report(report)
            else:
                error_msg = result.stderr if result.stderr else "No output"
                print(f"[TRIVY] Error: {error_msg[:500]}")
                return {"error": f"Scan failed: {error_msg[:200]}"}
        except subprocess.TimeoutExpired:
            return {"error": "Scan timeout after 5 minutes"}
        except Exception as e:
            print(f"[TRIVY] Exception: {str(e)}")
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
        try:
            response = requests.get(f"{self.scanner_url}/healthz", timeout=5)
            return response.status_code == 200
        except:
            return False
