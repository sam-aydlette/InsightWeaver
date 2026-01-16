"""
InsightWeaver Web Server
Flask application for the local web UI
"""

import logging
import os
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, redirect, url_for
from flask_cors import CORS

logger = logging.getLogger(__name__)


def init_database():
    """Initialize database tables if they don't exist."""
    try:
        from ..database.connection import create_tables

        create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")


def create_app(config: dict | None = None) -> Flask:
    """
    Create and configure the Flask application

    Args:
        config: Optional configuration overrides

    Returns:
        Configured Flask application
    """
    # Get the web directory for templates and static files
    web_dir = Path(__file__).parent

    app = Flask(
        __name__,
        template_folder=str(web_dir / "templates"),
        static_folder=str(web_dir / "static"),
    )

    # Default configuration
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
        DEBUG=os.environ.get("DEBUG", "false").lower() == "true",
    )

    # Apply any custom config
    if config:
        app.config.update(config)

    # Enable CORS for local development
    CORS(app)

    # Auto-initialize database on first run
    init_database()

    # Register blueprints (routes)
    from .routes import brief, dashboard, forecast, settings, setup, trust

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(setup.bp, url_prefix="/setup")
    app.register_blueprint(brief.bp, url_prefix="/brief")
    app.register_blueprint(forecast.bp, url_prefix="/forecast")
    app.register_blueprint(trust.bp, url_prefix="/trust")
    app.register_blueprint(settings.bp, url_prefix="/settings")

    # Root redirect - check if setup is needed
    @app.route("/")
    def index():
        # Check if setup is needed (no API key or no user profile)
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        profile_path = Path("config/user_profile.json")

        if not api_key or not profile_path.exists():
            return redirect(url_for("setup.welcome"))

        return redirect(url_for("dashboard.index"))

    logger.info("InsightWeaver web app created")
    return app


def run_server(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
    """
    Run the Flask development server

    Args:
        host: Host to bind to (default: localhost only)
        port: Port to run on (default: 5000)
        open_browser: Whether to open browser automatically
    """
    app = create_app()

    # Open browser after a short delay
    if open_browser:
        url = f"http://{host}:{port}"

        def open_browser_tab():
            webbrowser.open(url)

        Timer(1.5, open_browser_tab).start()
        logger.info(f"Opening browser to {url}")

    logger.info(f"Starting InsightWeaver web server on {host}:{port}")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
