"""Configuración por variables de entorno (o archivo .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sin DATABASE_URL se usa SQLite local (desarrollo).
    database_url: str = "sqlite:///./pedidos.db"
    anthropic_api_key: str = ""
    ai_model: str = "claude-haiku-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
