import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class BaseConfig:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Session & Cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set True in Production
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    
    # Mail settings
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 2525))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "False").lower() in ("true", "1")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    
    # Scheduler
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "UTC"

class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///" + os.path.join(BASE_DIR, "instance/aura_pos.db"))

class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

class ProductionConfig(BaseConfig):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    
    @staticmethod
    def init_app(app):
        """Validate production config on startup."""
        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError(
                'SECRET_KEY environment variable must be set for production. '
                'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
            )

    # Require external URI for production, no default sqlite
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI")

config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}