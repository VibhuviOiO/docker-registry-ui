from .trivy import TrivyScanner
from .clair import ClairScanner

def get_scanner(scanner_type, scanner_url, timeout=300):
    """Factory to create scanner instances"""
    scanners = {"trivy": TrivyScanner, "clair": ClairScanner}
    
    scanner_class = scanners.get(scanner_type.lower())
    if not scanner_class:
        raise ValueError(f"Unknown scanner type: {scanner_type}")
    
    return scanner_class(scanner_url, timeout)
