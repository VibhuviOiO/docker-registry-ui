import requests
from .base import VulnerabilityScanner

class TrivyScanner(VulnerabilityScanner):
    """Trivy vulnerability scanner integration"""
    
    def scan_image(self, registry_url, repository, tag):
        """Scan image using Trivy server"""
        try:
            image_ref = f"{registry_url}/{repository}:{tag}"
            
            response = requests.post(
                f"{self.scanner_url}/scan",
                json={"image": image_ref, "scanners": ["vuln"], "format": "json"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return self._parse_trivy_report(response.json())
            else:
                return {"error": f"Scan failed: HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _parse_trivy_report(self, report):
        """Parse Trivy JSON report"""
        vulnerabilities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        details = []
        
        for result in report.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                severity = vuln.get("Severity", "UNKNOWN")
                vulnerabilities[severity] = vulnerabilities.get(severity, 0) + 1
                details.append({
                    "id": vuln.get("VulnerabilityID"),
                    "severity": severity,
                    "package": vuln.get("PkgName"),
                    "version": vuln.get("InstalledVersion"),
                    "fixedVersion": vuln.get("FixedVersion"),
                    "title": vuln.get("Title")
                })
        
        return {
            "scanner": "trivy",
            "summary": vulnerabilities,
            "total": sum(vulnerabilities.values()),
            "details": details
        }
    
    def get_report(self, scan_id):
        return {"error": "Trivy doesn't support report retrieval"}
    
    def health_check(self):
        try:
            response = requests.get(f"{self.scanner_url}/healthz", timeout=5)
            return response.status_code == 200
        except:
            return False
