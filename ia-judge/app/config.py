from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    LLM_API_KEY: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "llama3.2:1b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
