"""Application configuration.

Environment variables are read once, at import time. Copy `.env.example` to
`.env` for local development, or set real environment variables in production.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
INSTANCE_DIR = BASE_DIR / "instance"

try:  # optional: load backend/.env when python-dotenv is available
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:  # pragma: no cover
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # ------------------------------------------------------------------ core
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    _default_sqlite = (INSTANCE_DIR / "smart_rooms.db").as_posix()
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or f"sqlite:///{_default_sqlite}"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {"timeout": 30} if (os.getenv("DATABASE_URL") or "sqlite").startswith("sqlite") else {},
    }

    # ------------------------------------------------------------------ auth
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=env_int("INACTIVITY_MINUTES", 15))
    SESSION_REFRESH_EACH_REQUEST = True

    # --------------------------------------------------------------- display
    # In production set DISPLAY_REQUIRE_TOKEN=true. The console then issues a
    # signed, read-only link for the kiosk screen.
    DISPLAY_REQUIRE_TOKEN = env_bool("DISPLAY_REQUIRE_TOKEN", False)
    DISPLAY_TOKEN_MAX_AGE_SEC = env_int("DISPLAY_TOKEN_MAX_AGE_SEC", 60 * 60 * 24 * 30)
    BUILDING_NAME = os.getenv("BUILDING_NAME", "Building A")
    BUILDING_LABEL = os.getenv("BUILDING_LABEL", "LECTURE ROOMS")

    # ----------------------------------------------------------------- audio
    AUDIO_ENABLED = env_bool("AUDIO_ENABLED", True)
    # browser | log | command | pyttsx3
    TTS_ADAPTER = os.getenv("TTS_ADAPTER", "browser")
    TTS_COMMAND = os.getenv("TTS_COMMAND", "")
    AUDIO_SECONDS_PER_ROOM = float(os.getenv("AUDIO_SECONDS_PER_ROOM", "2.4"))
    AUDIO_SECONDS_OVERHEAD = float(os.getenv("AUDIO_SECONDS_OVERHEAD", "1.0"))

    # ------------------------------------------------------------- bootstrap
    AUTO_INIT_DB = env_bool("AUTO_INIT_DB", True)
    AUTO_SEED = env_bool("AUTO_SEED", True)
    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@123")
    DEFAULT_OFFICER_USERNAME = os.getenv("DEFAULT_OFFICER_USERNAME", "otieno")
    DEFAULT_OFFICER_PASSWORD = os.getenv("DEFAULT_OFFICER_PASSWORD", "Officer@123")

    # --------------------------------------------------------------- testing
    TESTING = False
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 1024 * 1024
