import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_key = os.getenv("SUPABASE_KEY", "").strip()
        self.environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        self.auto_confirm_email = os.getenv("AUTO_CONFIRM_EMAIL", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        raw_origins = os.getenv("CORS_ORIGINS", "").strip()
        self.cors_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret-change-me").strip()
        self.internal_job_token = os.getenv("INTERNAL_JOB_TOKEN", "dev-internal-token-change-me").strip()
        self.oauth_redirect_url = os.getenv("OAUTH_REDIRECT_URL", "http://localhost:3000/auth/callback").strip()
        self.database_read_url = os.getenv("DATABASE_READ_URL", "").strip()
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        self._check_secrets()

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def _check_secrets(self) -> None:
        if self.supabase_key.startswith("sb_publishable_"):
            logger.warning("SUPABASE_KEY is a publishable key; the API must use service_role/secret")
        if self.is_production and self.auto_confirm_email:
            raise RuntimeError("AUTO_CONFIRM_EMAIL must be false in production")
        if self.is_production and self.webhook_secret.startswith("dev-"):
            raise RuntimeError("Set WEBHOOK_SECRET in production")
        if self.is_production and self.internal_job_token.startswith("dev-"):
            raise RuntimeError("Set INTERNAL_JOB_TOKEN in production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
