"""
Application entry point and factory for the thoughts dashboard.

Startup sequence (per specs/architecture/web_application.spec):
  1. Load environment variables
  2. Configure logging
  3. Validate required configuration
  4. Initialise Flask app
  5. Initialise database connection pool
  6. Register security middleware (CSRF, security headers)
  7. Register routes
  8. Register error handlers

Spec: specs/architecture/web_application.spec
Spec: specs/security/web_security.spec
"""
import logging
import os
import sys

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

# ---------------------------------------------------------------------------
# 1. Load environment variables from .env file (if present — dev only)
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# 2. Configure structured logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("FLASK_DEBUG", "").lower() == "true" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    Application factory.

    Returns:
        Configured Flask application instance.

    Raises:
        ValueError: If required environment variables are not set.
        SystemExit: If database pool cannot be created.
    """
    # 3. Validate configuration (fail fast)
    from src.config import Config
    Config.validate()

    # 4. Initialise Flask
    flask_app = Flask(__name__, template_folder="templates", static_folder="static")
    flask_app.config.from_object(Config)

    # Explicit secret key check — belt-and-braces (web_security.spec REQ-14)
    if not flask_app.config.get("SECRET_KEY"):
        raise ValueError("SECRET_KEY must be set via environment variable")

    # 5. Initialise database (stored in app.extensions for route access)
    from src.database import DatabaseConnection
    try:
        db = DatabaseConnection(config=Config)
        flask_app.extensions["db"] = db
        logger.info("Database connection pool ready")
    except Exception as exc:
        logger.critical("Cannot start application — database unavailable: %s", exc)
        sys.exit(1)

    # 6a. CSRF protection — required for all state-changing requests (REQ-7)
    csrf = CSRFProtect(flask_app)

    # Health check is read-only GET — exempt from CSRF (REQ-9)
    from src.routes import bp, health  # noqa: F401
    csrf.exempt(health)

    # 6b. Security headers on every response (web_security.spec REQ-1)
    @flask_app.after_request
    def set_security_headers(response):  # type: ignore[return]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        if not flask_app.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # 7. Register routes
    flask_app.register_blueprint(bp)

    # 8. Error handlers (web_application.spec — generic messages, no leaks)
    @flask_app.errorhandler(400)
    def bad_request(error):
        logger.warning("Bad request: %s", error)
        return render_template("error.html", message="Bad request"), 400

    @flask_app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="Page not found"), 404

    @flask_app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error: %s", error)
        return render_template("error.html", message="An internal error occurred"), 500

    # Graceful shutdown: close connection pool
    @flask_app.teardown_appcontext
    def close_db(exception=None):  # noqa: ANN001
        db_conn = flask_app.extensions.get("db")
        if db_conn and exception:
            logger.error("Teardown due to exception: %s", exception)

    logger.info("Application initialised successfully")
    return flask_app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    # Development only — Gunicorn is used in production (dockerfile.spec REQ-7)
    app.run(host="0.0.0.0", port=8080)
