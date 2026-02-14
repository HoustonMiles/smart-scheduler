import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

ENV = os.getenv("ENV", "local")

if ENV == "production":
    load_dotenv(".env.production")
elif ENV == "local":
    load_dotenv(".env.local")
else:
    load_dotenv()

ENVIRONMENT = ENV
DEBUG = ENV != "production"

# PostgreSQL for ALL environments
DATABASE_URL = os.getenv("DATABASE_URL")

# Convert Railway's postgres:// to postgresql+asyncpg://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Validate DATABASE_URL is set
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# API URLs
if ENV == "production":
    API_BASE_URL = os.getenv("RAILWAY_URL", "https://smart-scheduler-production-3978.up.railway.app")
elif ENV == "local":
    API_BASE_URL = "http://localhost:8000"
else:
    API_BASE_URL = "http://localhost:8000"

GOOGLE_REDIRECT_URI = f"{API_BASE_URL}/callback"

# Scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# CORS Origins
ORIGINS = [
    "chrome-extension://*",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    API_BASE_URL,
]

# Backup settings
BACKUP_DIR = Path("./backups")

def ensure_backup_dir():
    """Create backup directory if it doesn't exist"""
    BACKUP_DIR.mkdir(exist_ok=True)
    return BACKUP_DIR

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Authentication constants
AUTH_SESSION_TIMEOUT_MINUTES = 10
MAX_AUTH_POLLS = 60
AUTH_POLL_INTERVAL_SECONDS = 2

def log_config():
    """Log configuration - call after logging setup"""
    try:
        from app.core.logging_config import logger
        logger.info(f"Environment: {ENVIRONMENT}")
        logger.info(f"Database: {DATABASE_URL[:30]}...")
        logger.info(f"Secret key loaded (length: {len(SECRET_KEY)}")
    except ImportError:
        pass
