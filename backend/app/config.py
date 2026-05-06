from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["gemini", "groq", "ollama"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="KUWENTA_",
        extra="ignore",
    )

    app_env: Literal["development", "production", "test"] = "development"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    database_url: str = "sqlite+aiosqlite:///./data/kuwenta.db"

    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    llm_provider_categorization: ProviderName = "gemini"
    llm_provider_qa: ProviderName = "gemini"
    llm_provider_ocr: ProviderName = "gemini"
    llm_provider_insights: ProviderName = "gemini"

    gemini_rate_limit_per_min: int = 8  # below Gemini 2.5 Flash free-tier 10/min ceiling

    receipt_storage_dir: str = "./data/receipts"


@lru_cache
def get_settings() -> Settings:
    return Settings()
