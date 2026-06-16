from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .logger import setup_logging
from .version import __version__
import logging


def create_app():
    from .config import Config

    app = FastAPI(title="Docker Registry UI", version=__version__)
    app.state.VERSION = __version__

    # Mount static files at /static (same URL path as the legacy Flask app)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Setup logging (idempotent: safe to call after uvicorn --log-config)
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Docker Registry UI")

    from .routes import main_router, api_router
    from .health import health_router

    app.include_router(main_router)
    app.include_router(api_router, prefix="/api")
    app.include_router(health_router)

    logger.info(f"Configured {len(Config.REGISTRIES)} registries")
    logger.info(f"Read-only mode: {Config.READ_ONLY}")

    return app
