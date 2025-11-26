import requests
from .base import VulnerabilityScanner

class ClairScanner(VulnerabilityScanner):
    """Clair vulnerability scanner integration"""
    
    def scan_image(self, registry_url, repository, tag):
        try:
            response = requests.post(
                f"{self.scanner_url}/api/v1/index_report",
                json={"hash": f"{repository}:{tag}", "layers": []},
                timeout=self.timeout
            )
            
            if response.status_code == 201:
                return self._parse_clair_report(response.json())
            else:
                return {"error": f"Scan failed: HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _parse_clair_report(self, report):
        vulnerabilities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        return {
            "scanner": "clair",
            "summary": vulnerabilities,
            "total": sum(vulnerabilities.values()),
            "details": []
        }
    
    def get_report(self, scan_id):
        try:
            response = requests.get(f"{self.scanner_url}/api/v1/vulnerability_report/{scan_id}", timeout=10)
            if response.status_code == 200:
                return self._parse_clair_report(response.json())
        except:
            pass
        return {"error": "Report not found"}
    
    def health_check(self):
        try:
            response = requests.get(f"{self.scanner_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
