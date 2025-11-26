from abc import ABC, abstractmethod

class VulnerabilityScanner(ABC):
    """Base class for vulnerability scanners"""
    
    def __init__(self, scanner_url, timeout=300):
        self.scanner_url = scanner_url
        self.timeout = timeout
    
    @abstractmethod
    def scan_image(self, registry_url, repository, tag):
        """Scan an image and return vulnerability report"""
        pass
    
    @abstractmethod
    def get_report(self, scan_id):
        """Get scan report by ID"""
        pass
    
    @abstractmethod
    def health_check(self):
        """Check if scanner is available"""
        pass
