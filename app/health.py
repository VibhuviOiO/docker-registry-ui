from fastapi import APIRouter
from fastapi.responses import JSONResponse
from .config import Config

health_router = APIRouter()


@health_router.get("/health/live")
def liveness():
    """Liveness probe - is the app running?"""
    return {"status": "alive"}


@health_router.get("/health/ready")
def readiness():
    """Readiness probe - can the app serve traffic?"""
    try:
        # Check if we can access registries
        registries = Config.REGISTRIES
        if not registries:
            return JSONResponse({"status": "not ready", "reason": "no registries configured"}, status_code=503)

        return {"status": "ready", "registries": len(registries)}
    except Exception as e:
        return JSONResponse({"status": "not ready", "reason": str(e)}, status_code=503)


@health_router.get("/health")
def health():
    """Combined health check"""
    return {
        "status": "healthy",
        "registries": len(Config.REGISTRIES),
        "read_only": Config.READ_ONLY
    }
