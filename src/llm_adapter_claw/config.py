"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8080, description="Server port")
    log_level: str = Field(default="info", description="Logging level")

    # LLM Provider settings
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Upstream LLM API base URL",
    )
    llm_api_key: str = Field(default="", description="Upstream LLM API key")
    llm_model: str = Field(default="gpt-4", description="Default LLM model")

    # Proxy settings
    request_timeout: int = Field(default=120, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Max retries for failed requests")

    # Memory settings
    memory_enabled: bool = Field(default=True, description="Enable semantic memory")
    vector_db_path: str = Field(
        default="./memory_store/vss.db",
        description="Path to vector database",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="Sentence transformer model for embeddings",
    )
    embedding_device: str = Field(default="cpu", description="Device for embeddings")
    max_memory_results: int = Field(default=3, description="Max memory results to retrieve")

    # Context optimization settings
    optimization_enabled: bool = Field(default=True, description="Enable context optimization")
    preserve_last_n_messages: int = Field(
        default=2,
        description="Always preserve last N user messages",
    )
    max_history_tokens: int = Field(
        default=2000,
        description="Max tokens for history context",
    )
    system_prompt_cleanup: bool = Field(
        default=True,
        description="Enable System Prompt cleanup",
    )

    # Safety settings
    circuit_breaker_threshold: int = Field(
        default=5,
        description="Failures before circuit breaker opens",
    )
    circuit_breaker_timeout: int = Field(
        default=60,
        description="Seconds before circuit breaker retries",
    )

    @property
    def vector_db_full_path(self) -> Path:
        """Get full path to vector database."""
        return Path(self.vector_db_path).resolve()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
