from flask import Flask
from .config import Config
from .logger import setup_logging
from .version import __version__
import logging

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    app.config['VERSION'] = __version__
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Docker Registry UI")
    
    from .routes import main_bp, api_bp
    from .health import health_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(health_bp)
    
    logger.info(f"Configured {len(Config.REGISTRIES)} registries")
    logger.info(f"Read-only mode: {Config.READ_ONLY}")
    
    return app
