from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_host: str = "http://ollama:11434"
    ollama_model_primary: str = "phi3:mini"
    ollama_model_fallback: str = "llama3.2:1b"
    anthropic_api_key: str = ""
    anthropic_model_primary: str = "claude-sonnet-5"
    anthropic_model_fallback: str = "claude-haiku-4-5-20251001"
    backend_url: str = "http://backend:8000"
    database_url: str = "sqlite:////app/data/research.db"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
