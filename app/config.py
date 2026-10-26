"""Central configuration. All secrets (JWT secret, AI keys) are read ONLY here, from the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # repo-root .env, regardless of the directory the process starts in


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "")) or default
    except ValueError:
        return default


class Settings:
    is_prod = os.getenv("APP_ENV", os.getenv("NODE_ENV", "development")) == "production"
    port = _int("PORT", 3001)
    jwt_secret = os.getenv("JWT_SECRET") or "dev-only-secret-change-me-0123456789"
    jwt_expires_hours = _int("JWT_EXPIRES_HOURS", 12)
    db_path = os.getenv("DB_PATH", "./data/bookleaf.db")
    cors_origin = os.getenv("CORS_ORIGIN", "")  # empty = same-origin only (client is served by FastAPI)
    login_rate_limit = _int("LOGIN_RATE_LIMIT", 10)  # attempts per minute per IP

    # AI
    ai_provider = os.getenv("AI_PROVIDER", "anthropic").lower()  # anthropic | openai
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    ai_model = os.getenv("AI_MODEL", "")
    ai_timeout_s = _int("AI_TIMEOUT_MS", 15000) / 1000
    breaker_threshold = _int("AI_BREAKER_THRESHOLD", 3)
    breaker_cooldown_s = _int("AI_BREAKER_COOLDOWN_MS", 60000) / 1000

    # Business rules from the BookLeaf Knowledge Base
    payout_threshold = 1000
    payout_window_days = 45
    seed_author_password = "Author@123"
    seed_admin_password = "Admin@123"


settings = Settings()

if settings.is_prod and (not os.getenv("JWT_SECRET") or len(os.getenv("JWT_SECRET", "")) < 16):
    raise RuntimeError("JWT_SECRET must be set (min 16 chars) in production")
