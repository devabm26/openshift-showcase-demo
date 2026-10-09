"""
Configuration management for the thoughts dashboard.

Loads all settings from environment variables.
Fails fast on startup if required configuration is missing.

Spec: specs/architecture/web_application.spec (Configuration Management)
Spec: specs/security/secrets_management.spec
"""
import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Application configuration loaded from environment variables."""

    # --- Database (REQUIRED) ---
    DB_HOST: str = os.environ.get("DB_HOST", "")
    DB_NAME: str = os.environ.get("DB_NAME", "")
    DB_USER: str = os.environ.get("DB_USER", "")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")
    DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))

    # --- Connection Pool ---
    DB_POOL_MIN: int = int(os.environ.get("DB_POOL_MIN", "1"))
    DB_POOL_MAX: int = int(os.environ.get("DB_POOL_MAX", "10"))
    DB_TIMEOUT: int = int(os.environ.get("DB_TIMEOUT", "30"))

    # --- Flask ---
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # --- Session security ---
    SESSION_COOKIE_SECURE: bool = not DEBUG
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME: int = 3600

    # --- WTF CSRF ---
    WTF_CSRF_ENABLED: bool = True

    @classmethod
    def validate(cls) -> None:
        """
        Validate required configuration at startup.
        Raises ValueError with descriptive message if any required variable is missing.
        Spec: specs/architecture/web_application.spec (Configuration Management)
        """
        required = {
            "DB_HOST": cls.DB_HOST,
            "DB_NAME": cls.DB_NAME,
            "DB_USER": cls.DB_USER,
            "DB_PASSWORD": cls.DB_PASSWORD,
            "SECRET_KEY": cls.SECRET_KEY,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Required environment variables not set: {', '.join(missing)}. "
                "Set them before starting the application."
            )
        # Log that config was loaded (NOT values — spec REQ: never log secrets)
        logger.info(
            "Configuration validated: DB_HOST=%s DB_NAME=%s DB_PORT=%s",
            cls.DB_HOST,
            cls.DB_NAME,
            cls.DB_PORT,
        )
