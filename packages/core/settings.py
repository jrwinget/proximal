from functools import lru_cache
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    trellis_provider: str = "ollama"

    ollama_base_url: str | None = None
    ollama_model: str | None = None

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_model: str = "claude-3-haiku"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _check_env(self):
        import os

        # skip .env file check in test environment
        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return self

        env_path = Path(".env")
        if not env_path.exists():
            raise FileNotFoundError(
                ".env file not found - please create one with TRELLIS_PROVIDER and credentials."
            )

        prov = self.trellis_provider.lower()
        if prov == "ollama":
            if not self.ollama_base_url or not self.ollama_model:
                raise ValueError(
                    "OLLAMA_BASE_URL and OLLAMA_MODEL must be set for provider=ollama"
                )
        elif prov == "openai":
            if not self.openai_api_key or not self.openai_model:
                raise ValueError("OPENAI_API_KEY must be set for provider=openai")
        elif prov == "anthropic":
            if not self.anthropic_api_key or not self.anthropic_model:
                raise ValueError("ANTHROPIC_API_KEY must be set for provider=anthropic")
        else:
            raise ValueError(f"Unknown TRELLIS_PROVIDER '{self.trellis_provider}'")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
