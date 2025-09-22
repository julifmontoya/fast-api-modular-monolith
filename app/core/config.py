# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="sqlite:///./tickets.db")
    APP_NAME: str = "Smart API"
    APP_DESC: str = "A mini system with FastAPI"
    APP_VERSION: str = "1.0.0"
    ENV_: str | None = None  # optional

    # CORS origins
    CORS_ORIGINS: str | None = None

    # Pydantic v2 style config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
