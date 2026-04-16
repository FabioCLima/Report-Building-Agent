from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    model_name: str = Field(default="gpt-4o", alias="MODEL_NAME")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")
    session_storage_path: str = Field(default="./sessions", alias="SESSION_STORAGE_PATH")
    logs_dir: str = Field(default="./logs", alias="LOGS_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )
