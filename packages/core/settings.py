from functools import lru_cache
from pathlib import Path
from pydantic import model_validator, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    provider_name: str = Field(
        "ollama",
        validation_alias=AliasChoices("PROVIDER_NAME", "PROVIDER_NAME"),
    )
    ollama_base_url: str | None = None
    ollama_model: str | None = None

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_model: str = "claude-3-haiku"

    # api authentication (optional - if not set, api is open)
    proximal_api_key: str | None = None

    # api server configuration
    api_host: str = "0.0.0.0"
    api_port: int = 7315
    api_workers: int = 1

    # session configuration
    session_timeout_hours: int = 1
    max_clarifications: int = 2

    # redis configuration (optional - for distributed sessions)
    redis_url: str | None = None

    # llm configuration
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 3
    llm_retry_min_wait: int = 4
    llm_retry_max_wait: int = 10

    # rate limiting configuration
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 10

    # logging configuration
    log_level: str = "INFO"

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
                ".env file not found - please create one with PROVIDER_NAME and credentials."
            )

        prov = self.provider_name.lower()
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
            raise ValueError(f"Unknown PROVIDER_NAME '{self.provider_name}'")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
