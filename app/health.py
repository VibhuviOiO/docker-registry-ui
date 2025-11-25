from flask import Blueprint, jsonify
import requests
from .config import Config

health_bp = Blueprint('health', __name__)

@health_bp.route("/health/live")
def liveness():
    """Liveness probe - is the app running?"""
    return jsonify({"status": "alive"}), 200

@health_bp.route("/health/ready")
def readiness():
    """Readiness probe - can the app serve traffic?"""
    try:
        # Check if we can access registries
        registries = Config.REGISTRIES
        if not registries:
            return jsonify({"status": "not ready", "reason": "no registries configured"}), 503
        
        return jsonify({"status": "ready", "registries": len(registries)}), 200
    except Exception as e:
        return jsonify({"status": "not ready", "reason": str(e)}), 503

@health_bp.route("/health")
def health():
    """Combined health check"""
    return jsonify({
        "status": "healthy",
        "registries": len(Config.REGISTRIES),
        "read_only": Config.READ_ONLY
    }), 200
