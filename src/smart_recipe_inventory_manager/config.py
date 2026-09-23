from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	"""Configuration loaded from environment variables or .env."""

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)

	ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
	llm_model: str = Field(default="gemma4:12b", alias="LLM_MODEL")
	vlm_model: str = Field(default="qwen3-vl:4b", alias="VLM_MODEL")
	embedding_model: str = Field(default="embeddinggemma", alias="EMBEDDING_MODEL")
	ollama_timeout_seconds: float = Field(default=120.0, alias="OLLAMA_TIMEOUT_SECONDS")
	gradio_host: str = Field(default="0.0.0.0", alias="GRADIO_HOST")
	gradio_port: int = Field(default=7860, alias="GRADIO_PORT")
	database_url: str | None = Field(default=None, alias="DATABASE_URL")
	vector_db_path: str = Field(default="/app/data/vector_store", alias="VECTOR_DB_PATH")


@lru_cache
def get_settings() -> Settings:
	"""Return one immutable application configuration instance."""
	return Settings()


settings = get_settings()
