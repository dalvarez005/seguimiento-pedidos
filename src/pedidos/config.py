"""Configuración por variables de entorno (o archivo .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sin DATABASE_URL se usa SQLite local (desarrollo).
    database_url: str = "sqlite:///./pedidos.db"
    # IA (opcional). Se prueban en el orden de AI_ORDER; si uno falla, sigue el otro.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    anthropic_api_key: str = ""
    ai_model: str = "claude-haiku-5-5"
    ai_order: str = "gemini,anthropic"
    ai_timeout: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
