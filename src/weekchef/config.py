"""Application settings from environment."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = "postgresql://localhost:5432/mydb"
    recipes_table: str = "recipies_db"

    google_calendar_enabled: bool = False
    google_client_secrets_file: str = "client_secrets.json"
    google_token_path: str = ".google_token.json"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_calendar_id: str = "primary"
    calendar_min_slot_minutes: int = 25
    calendar_max_slots_per_day: int = 12

    telegram_bot_token: str = ""

    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "LLM_API_KEY"),
    )
    llm_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENROUTER_BASE_URL"),
    )
    llm_model: str = "openai/gpt-4o-mini"
    llm_fallback_model: str = ""
    openrouter_http_referer: str = ""
    openrouter_app_title: str = "WeekChef"

    pipeline_version: str = "0.1.0"

    def effective_llm_base_url(self) -> str:
        return self.llm_base_url.strip() or DEFAULT_OPENROUTER_BASE_URL


def get_settings() -> Settings:
    return Settings()
